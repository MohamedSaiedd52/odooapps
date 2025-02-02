from odoo import models, fields, api
from odoo.modules import module as module_utils

class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    addon_path = fields.Char(string="Addon Path", compute="_compute_addon_path", readonly=True)

    @api.depends('name')
    def _compute_addon_path(self):
        for rec in self:
            try:
                # Try to get the addon path using the module's name
                path = module_utils.get_module_path(rec.name)
                rec.addon_path = path
            except Exception:
                rec.addon_path = "Path not found"
