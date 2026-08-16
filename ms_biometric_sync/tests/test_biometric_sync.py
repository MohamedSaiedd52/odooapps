# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestBiometricSync(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Setup system parameters
        cls.env['ir.config_parameter'].sudo().set_param('ms_biometric_sync.token', 'test_secret_token')
        cls.env['ir.config_parameter'].sudo().set_param('ms_biometric_sync.timezone', 'Africa/Cairo')

        # Create a test employee
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Biometric Employee',
            'biometric_id': '8888'
        })

    def test_01_biometric_id_uniqueness(self):
        """Verify that biometric_id is enforced unique per employee."""
        # Creating another employee with the same biometric_id should fail
        with self.assertRaises(Exception):
            self.env['hr.employee'].create({
                'name': 'Duplicate Employee',
                'biometric_id': '8888'
            })

    def test_02_biometric_log_creation(self):
        """Verify that biometric logs can be created and compute name properly."""
        log = self.env['biometric.log'].create({
            'biometric_id': '8888',
            'punch_id': 1001,
            'device_serial': 'ZKTESTSERIAL',
            'punch_time': '2026-06-18 08:00:00',
            'employee_id': self.employee.id,
            'state': 'synced'
        })
        self.assertEqual(log.state, 'synced')
        self.assertIn('Test Biometric Employee', log.name)

        # Test duplicate constraint on device_serial + punch_id
        with self.assertRaises(Exception):
            self.env['biometric.log'].create({
                'biometric_id': '8888',
                'punch_id': 1001,
                'device_serial': 'ZKTESTSERIAL',
                'punch_time': '2026-06-18 08:05:00',
                'employee_id': self.employee.id,
                'state': 'synced'
            })
