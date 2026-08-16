from odoo import api, fields, models, _


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    is_batch = fields.Boolean('Is Batch', default=False, copy=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_batch') and (not vals.get('name', False) or vals['name'] == _('New')):
                vals['name'] = self.env['ir.sequence'].next_by_code('mrp.production.batch') or _('New')
        return super().create(vals_list)
