# -*- coding: utf-8 -*-
import json

from odoo.tests.common import HttpCase, tagged

TOKEN = 'test_secret_token'


@tagged('post_install', '-at_install')
class TestBiometricSyncController(HttpCase):
    """End-to-end tests for the /api/biometric/sync JSON-RPC endpoint."""

    def setUp(self):
        super().setUp()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('ms_biometric_sync.token', TOKEN)
        icp.set_param('ms_biometric_sync.timezone', 'Africa/Cairo')
        self.employee = self.env['hr.employee'].create({
            'name': 'Controller Test Employee',
            'biometric_id': '7001',
        })

    def _sync(self, params):
        """POST a JSON-RPC envelope to the sync route and return its `result`."""
        response = self.url_open(
            '/api/biometric/sync',
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': params}),
            headers={'Content-Type': 'application/json'},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()['result']

    def _punch(self, punch_id, punch_time, biometric_id='7001'):
        return {
            'punch_id': punch_id,
            'device_serial': 'ZK_UNITTEST_01',
            'biometric_id': biometric_id,
            'punch_time': punch_time,
        }

    def test_10_missing_token_is_rejected(self):
        result = self._sync({'logs': [self._punch(1, '2026-06-18 08:00:00')]})
        self.assertEqual(result['status'], 'error')
        self.assertIn('Missing authentication token', result['message'])
        self.assertFalse(self.env['biometric.log'].search([('punch_id', '=', 1)]))

    def test_11_invalid_token_is_rejected(self):
        result = self._sync({
            'token': 'not-the-right-token',
            'logs': [self._punch(2, '2026-06-18 08:00:00')],
        })
        self.assertEqual(result['status'], 'error')
        self.assertIn('Invalid authentication token', result['message'])
        self.assertFalse(self.env['biometric.log'].search([('punch_id', '=', 2)]))

    def test_12_punches_pair_into_one_attendance(self):
        """A check-in punch opens an attendance, the next one closes it.

        This also guards the payload contract: the JSON-RPC dispatcher unpacks
        `params` into the endpoint kwargs, so reading the raw body would see the
        envelope instead of the token/logs.
        """
        result = self._sync({
            'token': TOKEN,
            'logs': [
                self._punch(101, '2026-06-18 08:00:00'),
                self._punch(102, '2026-06-18 17:00:00'),
            ],
        })
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['processed'], 2)
        self.assertEqual(result['errors'], 0)

        attendances = self.env['hr.attendance'].search([('employee_id', '=', self.employee.id)])
        self.assertEqual(len(attendances), 1)
        # Africa/Cairo is UTC+3 in June, and Odoo stores datetimes in UTC.
        self.assertEqual(str(attendances.check_in), '2026-06-18 05:00:00')
        self.assertEqual(str(attendances.check_out), '2026-06-18 14:00:00')

        logs = self.env['biometric.log'].search([('punch_id', 'in', [101, 102])])
        self.assertEqual(len(logs), 2)
        self.assertEqual(set(logs.mapped('state')), {'synced'})

    def test_13_replayed_punches_are_ignored(self):
        """Re-sending the same punches must not create duplicate attendances."""
        logs = [
            self._punch(201, '2026-06-18 08:00:00'),
            self._punch(202, '2026-06-18 17:00:00'),
        ]
        self._sync({'token': TOKEN, 'logs': logs})
        result = self._sync({'token': TOKEN, 'logs': logs})

        self.assertEqual(result['processed'], 0)
        self.assertEqual(result['ignored'], 2)
        self.assertEqual(
            self.env['hr.attendance'].search_count([('employee_id', '=', self.employee.id)]), 1)

    def test_14_unknown_biometric_id_is_logged_as_failed(self):
        """An unmapped device user is recorded, not silently dropped."""
        result = self._sync({
            'token': TOKEN,
            'logs': [self._punch(301, '2026-06-18 08:15:00', biometric_id='999999')],
        })
        self.assertEqual(result['errors'], 1)

        log = self.env['biometric.log'].search([('punch_id', '=', 301)])
        self.assertEqual(len(log), 1)
        self.assertEqual(log.state, 'failed')
        self.assertFalse(log.employee_id)
        self.assertIn('999999', log.note)

    def test_15_employee_matched_by_badge_id_fallback(self):
        """When no Biometric ID matches, the HR Badge ID (barcode) is tried."""
        badge_employee = self.env['hr.employee'].create({
            'name': 'Badge Only Employee',
            'barcode': 'BADGE7002',
        })
        result = self._sync({
            'token': TOKEN,
            'logs': [self._punch(401, '2026-06-18 09:00:00', biometric_id='BADGE7002')],
        })
        self.assertEqual(result['processed'], 1)

        log = self.env['biometric.log'].search([('punch_id', '=', 401)])
        self.assertEqual(log.state, 'synced')
        self.assertEqual(log.employee_id, badge_employee)
