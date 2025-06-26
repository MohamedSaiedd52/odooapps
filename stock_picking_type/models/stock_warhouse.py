from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.exceptions import MissingError, ValidationError, AccessError, UserError

class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    user_ids = fields.Many2many(
        comodel_name='res.users', string='Allowed Users',
        domain=lambda self: [('groups_id', 'in', self.env.ref('stock.group_stock_user').id)])
    restrict_location = fields.Boolean(string='Restrict Stock Location for this Warehouse')

    @api.onchange('restrict_location', 'user_ids')
    def _onchange_restrict_location(self):
        for rec in self.user_ids:
            if self.restrict_location:
                rec._origin.write({'restrict_location': True,'allowed_warehouse_ids': [(4, self._origin.id)]})
            elif not self.restrict_location:
                rec._origin.write({'restrict_location': True,'location_ids': False})

    def action_open_users_view(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Users',
            'view_mode': 'list,form',
            'res_model': 'res.users',
            'domain': [('id', 'in', [user.id for user in self.user_ids]),('groups_id', 'not in',[self.env.ref('base.group_system').id])]}
