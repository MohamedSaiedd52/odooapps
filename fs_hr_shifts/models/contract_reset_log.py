# -*- coding: utf-8 -*-

from odoo import models, fields


class ContractResetLog(models.Model):
    _name = "contract.reset.log"
    _description = "Keep original contract values"

    contract_id = fields.Many2one("hr.contract", string="Contract",
                                  required=True, ondelete="cascade")
    old_is_multi_shifts = fields.Boolean(string="Old Multi Shifts")
    old_work_entry_source = fields.Char(string="Old Work Entry Source")
