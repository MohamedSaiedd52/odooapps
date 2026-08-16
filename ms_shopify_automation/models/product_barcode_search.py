# -*- coding: utf-8 -*-
"""
Product Barcode Search Enhancement

Enhances product search to prioritize exact barcode / internal-reference
matches before falling back to the standard name search. Works on Odoo 17,
18 and 19:

- 17/18: ``name_search(name, args, ...)`` delegates to ``_name_search``.
- 19: ``_name_search`` was removed and ``name_search(name, domain, ...)``
  queries directly, so the override lives on ``name_search`` itself.
"""
from odoo import models, api

from .compat import VERSION

import logging

_logger = logging.getLogger(__name__)


class ProductProductBarcodeSearch(models.Model):
    """Override product.product to enhance barcode search functionality."""
    _inherit = 'product.product'

    @api.model
    def _barcode_priority_ids(self, name, domain, limit, order=None):
        """Return ids matching barcode/default_code by priority, or None."""
        for dom in ([('barcode', '=', name)],
                    [('default_code', '=', name)],
                    [('barcode', 'ilike', name)],
                    [('default_code', 'ilike', name)]):
            ids = self._search(dom + list(domain or []), limit=limit, order=order)
            if ids:
                return ids
        return None

    if VERSION >= 19:
        @api.model
        def name_search(self, name='', domain=None, operator='ilike', limit=100):
            if name:
                ids = self._barcode_priority_ids(name, domain, limit)
                if ids:
                    records = self.browse(ids)
                    return [(rec.id, rec.display_name) for rec in records.sudo()]
            return super().name_search(name, domain, operator, limit)
    else:
        @api.model
        def name_search(self, name='', args=None, operator='ilike', limit=100):
            if name:
                ids = self._barcode_priority_ids(name, args, limit)
                if ids:
                    records = self.browse(ids)
                    return [(rec.id, rec.display_name) for rec in records.sudo()]
            return super().name_search(name, args, operator, limit)

        @api.model
        def _name_search(self, name='', domain=None, operator='ilike', limit=None, order=None):
            if name:
                ids = self._barcode_priority_ids(name, domain, limit, order)
                if ids:
                    return ids
            return super()._name_search(name, domain, operator, limit, order)
