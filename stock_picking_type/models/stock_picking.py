# -*- coding: utf-8 -*-
from odoo import models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # Location/warehouse visibility for restricted users is enforced by the
    # ir.rule record rules defined in security/groups.xml. Returning a
    # "domain" key from an onchange is no longer supported in Odoo 16+.
