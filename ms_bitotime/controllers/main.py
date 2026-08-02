# -*- coding: utf-8 -*-
import json
import logging
import zlib
from datetime import datetime

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class BioTimeWebhook(http.Controller):
    """Real-time push endpoint.

    A BioTime script / middleware can POST new punches the moment they happen
    instead of waiting for the nightly pull:

        POST /biotime/webhook
        Header:  X-Biotime-Token: <token from the server form>
        Body:    {"punches": [{"id": 123, "emp_code": "7",
                               "punch_time": "2026-08-01 09:00:00",
                               "terminal_sn": "ABC123",
                               "punch_state_display": "Check In"}]}

    `punch_time` must be in the BioTime server's timezone (the one set on the
    server form). `id` is optional — when missing, a deterministic id is
    derived from (emp_code, punch_time, terminal_sn) so retries never
    duplicate punches.
    """

    @http.route('/biotime/webhook', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False)
    def biotime_webhook(self, **kwargs):
        try:
            payload = json.loads(request.httprequest.get_data() or b'{}')
        except ValueError:
            return self._json_response({'error': 'invalid JSON'}, 400)

        token = request.httprequest.headers.get('X-Biotime-Token') \
            or payload.get('token')
        if not token:
            return self._json_response({'error': 'missing token'}, 401)

        config = request.env['biotime.config'].sudo().search([
            ('webhook_enabled', '=', True),
            ('webhook_token', '=', token)], limit=1)
        if not config:
            _logger.warning("BioTime webhook: rejected call with bad token")
            return self._json_response({'error': 'invalid token'}, 403)

        punches = payload.get('punches') or []
        if not isinstance(punches, list):
            return self._json_response({'error': "'punches' must be a list"}, 400)

        result = self._import_punches(config, punches)
        return self._json_response(result, 200)

    def _import_punches(self, config, punches):
        env = request.env
        Transaction = env['biotime.transaction'].sudo()
        Log = env['biotime.transaction.log'].sudo()
        terminals = {
            t.terminal_sn: t.id
            for t in env['biotime.terminal'].sudo().search(
                [('biotime_id', '=', config.id)])
        }

        imported, unmatched, skipped, rejected = 0, 0, 0, []
        times = []
        for punch in punches:
            emp_code = punch.get('emp_code')
            punch_time = punch.get('punch_time')
            if not emp_code or not punch_time:
                rejected.append(punch)
                continue
            try:
                punch_time_utc = datetime.strptime(
                    config.convert_to_utc(str(punch_time)[:19], config.tz),
                    '%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                rejected.append(punch)
                continue

            tx_id = punch.get('id') or zlib.crc32(
                ("%s|%s|%s" % (emp_code, punch_time,
                               punch.get('terminal_sn') or '')).encode())

            if Transaction.search_count([
                    ('transaction_id', '=', tx_id),
                    ('server_id', '=', config.id)]):
                skipped += 1
                continue

            employee = env['hr.employee'].sudo().search(
                [('zk_emp_code', '=', str(emp_code))], limit=1)
            vals = {
                'transaction_id': tx_id,
                'punch_time': punch_time_utc,
                'punch_state': punch.get('punch_state'),
                'punch_state_display': punch.get('punch_state_display'),
                'device_id': terminals.get(punch.get('terminal_sn')),
                'server_id': config.id,
            }
            if employee:
                Transaction.create(dict(vals, employee_id=employee.id,
                                        department=punch.get('department_name')))
                imported += 1
                times.append(punch_time_utc)
            else:
                Log.create(dict(vals,
                                emp_code=emp_code,
                                emp_name=punch.get('emp_name'),
                                department=punch.get('department_name'),
                                note='No matching employee found in Odoo (webhook)'))
                unmatched += 1

        if imported and config.auto_transfer:
            config.action_transfer_transition(
                from_date=min(times), to_date=max(times),
                raise_if_empty=False)

        _logger.info(
            "BioTime webhook (%s): %s imported, %s unmatched, %s duplicate, "
            "%s rejected", config.name, imported, unmatched, skipped,
            len(rejected))
        return {
            'status': 'ok',
            'imported': imported,
            'unmatched': unmatched,
            'duplicates': skipped,
            'rejected': len(rejected),
        }

    @staticmethod
    def _json_response(data, status):
        return request.make_response(
            json.dumps(data), status=status,
            headers=[('Content-Type', 'application/json')])
