from odoo import models


class ReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    def _prepare_picking_default_values(self):
        vals = super()._prepare_picking_default_values()
        # Always return to the original picking's source location
        # instead of the return operation type's default destination
        vals['location_dest_id'] = self.picking_id.location_id.id
        return vals

    def _prepare_move_default_values(self, return_line, new_picking):
        # Odoo 17 only: the return moves take their destination from the
        # wizard's "Return Location" field, not from the new picking header,
        # so the header fix above is not enough there. On 18/19 this wizard
        # method does not exist (moves read the new picking's destination)
        # and this override is never called.
        vals = super()._prepare_move_default_values(return_line, new_picking)
        vals['location_dest_id'] = self.picking_id.location_id.id
        return vals
