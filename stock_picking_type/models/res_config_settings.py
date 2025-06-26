import logging
from odoo import api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    group_user_warehouse_restriction = fields.Boolean(
        string="Restrict Stock Warehouse",
        implied_group='stock_picking_type.user_warehouse_restriction_group_user')

    @api.onchange('group_user_warehouse_restriction')
    def _onchange_group_user_warehouse_restriction(self):
        rule = self.env.ref('stock_picking_type.operation_type_rule_users', raise_if_not_found=False)
        if rule:
            rule.active = False
        try:
            warehouses = self.env['stock.warehouse'].search([])
            for warehouse in warehouses:
                if self.group_user_warehouse_restriction:
                    if not warehouse.user_ids:
                        warehouse.user_ids = [(6, 0, [self.env.user.id])]
                else:
                    warehouse.user_ids = [(5, 0, 0)]
        except AccessError as e:
            _logger.warning(f"Access error occurred: {e}")
        finally:
            if rule:
                rule.active = True
