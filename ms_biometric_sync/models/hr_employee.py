# -*- coding: utf-8 -*-
from odoo import models, fields

# Odoo 19 replaced _sql_constraints with models.Constraint; 17 and 18 have no such class.
_HAS_CONSTRAINT = hasattr(models, 'Constraint')

_BIOMETRIC_UNIQUE_MSG = 'The Biometric ID must be unique!'


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    biometric_id = fields.Char(
        string='Biometric ID',
        help='Enroll number or User ID of the employee on the fingerprint machine',
        index=True,
        copy=False
    )

    if _HAS_CONSTRAINT:
        _biometric_id_unique = models.Constraint(
            'unique(biometric_id)',
            _BIOMETRIC_UNIQUE_MSG,
        )
    else:
        _sql_constraints = [
            ('biometric_id_unique', 'unique(biometric_id)', _BIOMETRIC_UNIQUE_MSG),
        ]
