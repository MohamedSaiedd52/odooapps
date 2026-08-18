# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    hijri_date_order = fields.Char(
        string="Hijri Order Date", compute='_compute_hijri_date_order')

    @api.depends('date_order', 'company_id.hijri_adjustment',
                 'company_id.hijri_format')
    def _compute_hijri_date_order(self):
        converter = self.env['ms.hijri.converter']
        for order in self:
            order.hijri_date_order = converter.format_date(
                order.date_order, company=order.company_id)
