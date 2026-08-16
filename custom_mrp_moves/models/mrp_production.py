# -*- coding: utf-8 -*-
from odoo import models, fields, api


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def _get_move_raw_values(self, product, product_uom_qty, product_uom, operation_id=False, bom_line=False):
        res = super()._get_move_raw_values(product, product_uom_qty, product_uom, operation_id, bom_line)

        if bom_line and bom_line.source_location_id:
            res['location_id'] = bom_line.source_location_id.id
            res['source_location_id'] = bom_line.source_location_id.id
        elif bom_line:
            res['source_location_id'] = False

        return res

    def _link_bom(self, bom):
        old_source_locations = {}
        for move in self.move_raw_ids:
            if move.bom_line_id and move.source_location_id:
                old_source_locations[move.bom_line_id.id] = move.source_location_id.id

        super()._link_bom(bom)

        for move in self.move_raw_ids:
            if move.bom_line_id:
                if move.bom_line_id.source_location_id:
                    move.write({
                        'source_location_id': move.bom_line_id.source_location_id.id,
                        'location_id': move.bom_line_id.source_location_id.id
                    })
                elif move.bom_line_id.id in old_source_locations:
                    old_location_id = old_source_locations[move.bom_line_id.id]
                    move.write({
                        'source_location_id': old_location_id,
                        'location_id': old_location_id
                    })