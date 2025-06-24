# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError

class ResUsers(models.Model):
    _inherit = 'res.users'

    picking_type_ids = fields.Many2many('stock.picking.type', string="Allowed Picking Types")
    # allow_enter_scrap = fields.Boolean(string="Allow Enter Scrap", compute='_compute_allow_enter_scrap')

    # def _compute_allow_enter_scrap(self):
    #     for user in self:
    #         user.allow_enter_scrap = user.has_group('stock.group_stock_user') and user.allow_enter_scrap
    #
    # def action_stock_scrap_visible(self):
    #     for user in self:
    #         if user.has_group('stock.group_stock_manager'):
    #             return True
    #         if user.has_group('stock.group_stock_user') and user.allow_enter_scrap:
    #             return True
    #     return False