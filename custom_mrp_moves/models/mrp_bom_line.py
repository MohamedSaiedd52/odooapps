# models/mrp_bom.py
from odoo import models, fields


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    source_location_id = fields.Many2one(
        'stock.location',
        string='Source Location',
        domain="[('usage','=','internal')]",
        help="Specific location to consume this component from. If not set, will use default picking type location."
    )