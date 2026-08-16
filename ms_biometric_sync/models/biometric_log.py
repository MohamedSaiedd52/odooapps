# -*- coding: utf-8 -*-
from odoo import models, fields, api

# Odoo 19 replaced _sql_constraints with models.Constraint; 17 and 18 have no such class.
_HAS_CONSTRAINT = hasattr(models, 'Constraint')

_PUNCH_UNIQUE_MSG = 'This punch log has already been synced!'


class BiometricLog(models.Model):
    _name = 'biometric.log'
    _description = 'Raw Biometric Punch Log'
    _order = 'punch_time desc'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', index=True)
    biometric_id = fields.Char(string='Biometric ID', required=True, index=True)
    punch_id = fields.Integer(string='Punch UID', required=True)
    device_serial = fields.Char(string='Device Serial', required=True, index=True)
    punch_time = fields.Datetime(string='Punch Time', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('synced', 'Synced'),
        ('failed', 'Failed')
    ], string='Status', default='draft', required=True, index=True)
    note = fields.Text(string='Note')

    if _HAS_CONSTRAINT:
        _device_punch_unique = models.Constraint(
            'unique(device_serial, punch_id)',
            _PUNCH_UNIQUE_MSG,
        )
    else:
        _sql_constraints = [
            ('device_punch_unique', 'unique(device_serial, punch_id)', _PUNCH_UNIQUE_MSG),
        ]

    @api.depends('employee_id', 'punch_time', 'biometric_id')
    def _compute_name(self):
        for record in self:
            emp_name = record.employee_id.name if record.employee_id else f"Unknown ({record.biometric_id})"
            record.name = f"Punch {record.punch_id} - {emp_name} @ {record.punch_time}"
