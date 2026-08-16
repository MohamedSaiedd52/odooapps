from odoo import api, fields, models
from odoo.release import version_info


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    batch = fields.Boolean('Batch', default=False)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    if version_info[0] >= 19:
        # Odoo 19 renamed the second positional arg from `args` to `domain`
        @api.model
        def name_search(self, name='', domain=None, operator='ilike', limit=100):
            if self.env.context.get('default_is_batch') is True:
                domain = list(domain or []) + [('batch', '=', True)]
            return super().name_search(name=name, domain=domain, operator=operator, limit=limit)
    else:
        @api.model
        def name_search(self, name='', args=None, operator='ilike', limit=100):
            if self.env.context.get('default_is_batch') is True:
                args = list(args or []) + [('batch', '=', True)]
            return super().name_search(name=name, args=args, operator=operator, limit=limit)

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        if self.env.context.get('default_is_batch') is True:
            domain = list(domain or []) + [('batch', '=', True)]
        return super().web_search_read(domain, specification, offset=offset, limit=limit, order=order, count_limit=count_limit)
