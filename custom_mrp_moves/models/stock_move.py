# -*- coding: utf-8 -*-
from odoo import models, fields, api


class StockMove(models.Model):
    _inherit = 'stock.move'

    source_location_id = fields.Many2one(
        'stock.location',
        string='Source Location Override',
        domain="[('usage','=','internal'), ('company_id', 'in', [company_id, False])]",
        help="If set, this location will be used instead of default picking type location for raw materials",
        check_company=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('source_location_id') and vals.get('raw_material_production_id'):
                vals['location_id'] = vals['source_location_id']
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('source_location_id'):
            raw_moves = self.filtered('raw_material_production_id')
            other_moves = self - raw_moves
            res = True
            if raw_moves:
                res = super(StockMove, raw_moves).write(
                    dict(vals, location_id=vals['source_location_id']))
            if other_moves:
                res = super(StockMove, other_moves).write(vals) and res
            return res
        return super().write(vals)
