from odoo import models, fields

class StockLocation(models.Model):
    _inherit = 'stock.location'

    allow_negative_stock = fields.Boolean(
        string="Allow Negative Stock",
        default=True,
        help="If unchecked, negative stock will not be allowed for this location."
    )
