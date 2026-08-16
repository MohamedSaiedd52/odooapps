# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
from odoo.release import version_info
import pytz
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

# Odoo 19 renamed the JSON-RPC route type; in 17/18 only 'json' exists.
_ROUTE_TYPE = 'jsonrpc' if version_info[0] >= 19 else 'json'

TOKEN_PARAM = 'ms_biometric_sync.token'
TIMEZONE_PARAM = 'ms_biometric_sync.timezone'


class BiometricSyncController(http.Controller):

    @http.route('/api/biometric/sync', type=_ROUTE_TYPE, auth='public', methods=['POST'], csrf=False)
    def sync_punches(self, token=None, logs=None, **kwargs):
        # The JSON-RPC dispatcher unpacks the payload's "params" member into these
        # keyword arguments, so there is no need to re-read the request body.
        logs = logs or []

        if not token:
            return {'status': 'error', 'message': 'Missing authentication token.'}

        # Retrieve expected token from System Parameters
        expected_token = request.env['ir.config_parameter'].sudo().get_param(TOKEN_PARAM)
        if not expected_token:
            return {'status': 'error', 'message': 'System Parameter %s is not configured.' % TOKEN_PARAM}

        if token != expected_token:
            return {'status': 'error', 'message': 'Invalid authentication token.'}

        processed_count = 0
        ignored_count = 0
        error_count = 0
        errors = []

        # Get timezone to convert machine datetime strings
        timezone_param = request.env['ir.config_parameter'].sudo().get_param(TIMEZONE_PARAM, 'Africa/Cairo')
        tz = pytz.timezone(timezone_param)

        for log_data in logs:
            punch_id = log_data.get('punch_id')
            device_serial = log_data.get('device_serial')
            biometric_id = str(log_data.get('biometric_id', ''))
            punch_time_str = log_data.get('punch_time')  # 'YYYY-MM-DD HH:MM:SS' format

            if not all([punch_id, device_serial, biometric_id, punch_time_str]):
                error_count += 1
                errors.append(f"Invalid log data: {log_data}")
                continue

            # Check if this punch has already been processed (prevent duplicates)
            existing_log = request.env['biometric.log'].sudo().search([
                ('device_serial', '=', device_serial),
                ('punch_id', '=', punch_id)
            ], limit=1)

            if existing_log:
                ignored_count += 1
                continue

            # Convert punch time from local timezone string to UTC datetime object for Odoo storage
            try:
                naive_time = datetime.strptime(punch_time_str, '%Y-%m-%d %H:%M:%S')
                local_time = tz.localize(naive_time)
                utc_time = local_time.astimezone(pytz.utc)
                # Format to standard string Odoo Datetime field expects
                utc_time_str = fields.Datetime.to_string(utc_time)
            except Exception as e:
                error_count += 1
                errors.append(f"Time parsing error for punch {punch_id}: {str(e)}")
                continue

            # Find matching employee (first by biometric_id, then fallback to barcode/Badge ID)
            employee = request.env['hr.employee'].sudo().search([
                ('biometric_id', '=', biometric_id)
            ], limit=1)
            if not employee:
                employee = request.env['hr.employee'].sudo().search([
                    ('barcode', '=', biometric_id)
                ], limit=1)

            # Create the biometric log record (using sudo to run as admin)
            log_record = request.env['biometric.log'].sudo().create({
                'biometric_id': biometric_id,
                'punch_id': punch_id,
                'device_serial': device_serial,
                'punch_time': utc_time_str,
                'employee_id': employee.id if employee else False,
                'state': 'draft',
            })

            if not employee:
                log_record.write({
                    'state': 'failed',
                    'note': f"No employee found with Biometric ID '{biometric_id}'"
                })
                error_count += 1
                continue

            # Now pair the punch into hr.attendance
            try:
                # Find the employee's last open attendance record (check_in set, but no check_out)
                open_attendance = request.env['hr.attendance'].sudo().search([
                    ('employee_id', '=', employee.id),
                    ('check_out', '=', False)
                ], order='check_in desc', limit=1)

                if open_attendance:
                    # Pair this punch as a check_out
                    # Check if check_out time is after check_in time to prevent overlapping/backwards ranges
                    if utc_time_str > fields.Datetime.to_string(open_attendance.check_in):
                        open_attendance.write({
                            'check_out': utc_time_str
                        })
                        log_record.write({
                            'state': 'synced',
                            'note': f"Checked out employee. Reference attendance ID: {open_attendance.id}"
                        })
                        processed_count += 1
                    else:
                        # Punch time is prior to or equal to check_in.
                        if utc_time_str == fields.Datetime.to_string(open_attendance.check_in):
                            log_record.write({
                                'state': 'failed',
                                'note': "Punch time is identical to the current check-in time. Ignored."
                            })
                            error_count += 1
                        else:
                            # Create a new attendance record
                            new_attendance = request.env['hr.attendance'].sudo().create({
                                'employee_id': employee.id,
                                'check_in': utc_time_str
                            })
                            log_record.write({
                                'state': 'synced',
                                'note': f"Created new check-in (prior to existing check-in). Attendance ID: {new_attendance.id}"
                            })
                            processed_count += 1
                else:
                    # Create a new attendance record (check-in)
                    new_attendance = request.env['hr.attendance'].sudo().create({
                        'employee_id': employee.id,
                        'check_in': utc_time_str
                    })
                    log_record.write({
                        'state': 'synced',
                        'note': f"Created new check-in. Attendance ID: {new_attendance.id}"
                    })
                    processed_count += 1

            except Exception as e:
                log_record.write({
                    'state': 'failed',
                    'note': f"Error creating/updating attendance: {str(e)}"
                })
                error_count += 1
                errors.append(f"DB Error for punch {punch_id}: {str(e)}")

        return {
            'status': 'success',
            'processed': processed_count,
            'ignored': ignored_count,
            'errors': error_count,
            'error_details': errors
        }
