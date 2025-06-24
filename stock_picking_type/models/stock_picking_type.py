from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.exceptions import MissingError, ValidationError, AccessError, UserError

class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'


    # def check_access_rights(self, operation, raise_exception=True):
    #     """ Override check_access_rights to respect picking_type_ids of the current user. """
    #     if not self:
    #         # Handle case where self is empty (no records)
    #         return False
    #
    #     self.ensure_one()  # Ensure there is exactly one record in self
    #
    #     res = super(StockPickingType, self).check_access_rights(operation, raise_exception=False)
    #     if res is False:
    #         return False
    #     if operation in ['read', 'write', 'unlink']:
    #         allowed_picking_types = self.env.user.picking_type_ids.ids
    #         if self.id not in allowed_picking_types:
    #             if raise_exception:
    #                 raise AccessError(_("You do not have the required permissions to access this picking type."))
    #             return False
    #     return True
    #
    # @api.model
    # def search(self, args, offset=0, limit=None, order=None, count=False):
    #     """ Override search to filter picking types based on user's picking_type_ids. """
    #     if not self.env.context.get('bypass_picking_type_check'):
    #         args = [('id', 'in', self.env.user.picking_type_ids.ids)] + list(args)
    #     return super(StockPickingType, self).search(args, offset, limit, order, count=count)
    #
    # @api.model
    # def read(self, fields=None, load='_classic_read'):
    #     """ Override read to filter picking types based on user's picking_type_ids. """
    #     if not self.env.context.get('bypass_picking_type_check') and fields:
    #         fields.append('id')
    #         allowed_picking_types = self.env.user.picking_type_ids.ids
    #         if self.id not in allowed_picking_types:
    #             return {}
    #     return super(StockPickingType, self).read(fields=fields, load=load)

