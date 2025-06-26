# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError

class ResUsers(models.Model):
    _inherit = 'res.users'
    picking_type_ids = fields.Many2many('stock.picking.type', string="Allowed Picking Types")
    restrict_location = fields.Boolean(string="Restrict Location")
    location_ids = fields.Many2many(comodel_name='stock.location', string='Restricted Locations')
    allowed_warehouse_ids = fields.Many2many(comodel_name='stock.warehouse', string='Allowed Warehouse')
    check_user = fields.Boolean(string="Check", compute='_compute_check_user')

    @api.model
    def create(self, vals):
        self.clear_caches()
        return super(ResUsers, self).create(vals)

    def write(self, vals):
        self.clear_caches()
        return super(ResUsers, self).write(vals)

    def _compute_check_user(self):
        restriction_group_id = self.env.ref(
            'stock_picking_type.user_warehouse_restriction_group_user').id
        for record in self:
            record.check_user = False
            if restriction_group_id in record.groups_id.mapped('id'):
                record.check_user = True
