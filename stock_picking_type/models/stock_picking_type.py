from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.exceptions import MissingError, ValidationError, AccessError, UserError

class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'



