from odoo import api, fields, models


class PosConfig(models.Model):
    """To add a field in pos config"""
    _inherit = 'pos.config'

    analytic_account_id = fields.Many2one('account.analytic.account',
                                          string="Analytic account",
                                          help="Add Analytic account for the current session")

    @api.model
    def _load_pos_data_fields(self, config):
        res = super()._load_pos_data_fields(config)
        # Base pos.load.mixin returns [], so we must explicitly list all needed fields
        # Including both standard POS fields and our custom analytic_account_id
        res += [
            # Custom field
            'analytic_account_id',
            # Core config fields
            'currency_id',
            'company_id',
            'use_pricelist',
            'pricelist_id',
            'trusted_config_ids',
            # Image display
            'show_product_images',
            'show_category_images',
            # Payment methods (required for ActionpadWidget)
            'payment_method_ids',
            'fast_payment_method_ids',
            'use_fast_payment',
            # Presets and discounts
            'use_presets',
            'manual_discount',
            # Restaurant mode
            'module_pos_restaurant',
            # Categories
            'limit_categories',
            'iface_available_categ_ids',
            # Other required fields
            'module_pos_hr',
            'iface_tipproduct',
        ]
        return res


