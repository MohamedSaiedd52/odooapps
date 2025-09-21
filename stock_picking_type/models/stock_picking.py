# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.exceptions import MissingError, ValidationError, AccessError, UserError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.onchange('location_id', 'location_dest_id')
    def _onchange_location_id(self):
        if self.env['ir.config_parameter'].sudo().get_param('stock_picking_type.group_user_warehouse_restriction'):
            return {
                'domain': {'location_id': [
                    ('warehouse_id.user_ids', 'in', self.env.user.id)],
                    'location_dest_id': [
                        ('warehouse_id.user_ids', 'in', self.env.user.id)]}}


