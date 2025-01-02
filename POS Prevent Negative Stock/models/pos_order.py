# -*- coding: utf-8 -*-
""" init object """
from odoo import fields, models, api, _ ,tools, SUPERUSER_ID
from odoo.exceptions import ValidationError,UserError
from datetime import datetime , date ,timedelta
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from dateutil.relativedelta import relativedelta
from odoo.fields import Datetime as fieldsDatetime
import calendar
from odoo import http
from odoo.http import request
from odoo import tools

import logging

LOGGER = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model
    def check_order_qty(self, order_vals):
        pos_session_id = order_vals.get('pos_session_id')
        if pos_session_id:
            message = _('The products with negative stock:- \n')
            session = self.env['pos.session'].browse(int(pos_session_id))
            config = session.config_id
            location = config.picking_type_id.default_location_src_id
            negative_case = False
            for line in order_vals.get('lines', []):
                line_vals = line[2]
                product_id = line_vals.get('product_id')
                product = self.env['product.product'].browse(product_id)
                line_qty = line_vals.get('qty', 0)
                if line_qty > 0 and product.type == 'product':
                    available_qty = self.env['stock.quant']._get_available_quantity(product, location, allow_negative=True)
                    if available_qty < line_qty:
                        message += _('product %s available quantity = %s \n') %(product.name, available_qty)
                        negative_case = True

            if negative_case:
                return {
                    "message": message,
                }
        return False
