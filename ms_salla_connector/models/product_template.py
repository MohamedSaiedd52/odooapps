from odoo import fields, models, api
import logging
from .salla_api import SallaAPI

_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    salla_product_id = fields.Char(string='Salla Product ID', copy=False, readonly=True)
    salla_url = fields.Char(string='Salla URL', readonly=True)
    salla_metadata = fields.Text(string='Salla Metadata', readonly=True, help="Raw JSON data from Salla")

    def action_sync_from_salla(self):
        """
        Fetches products from Salla and creates/updates them in Odoo.
        """
        api_helper = SallaAPI(self.env)
        
        # Pagination loop
        page = 1
        has_more = True
        
        synced_count = 0
        
        while has_more:
            response = api_helper.get_products(page=page)
            if 'error' in response:
                _logger.error("Salla Sync Error: %s", response['error'])
                # Optionally post a message to the user
                break
                
            data = response.get('data', [])
            pagination = response.get('pagination', {})
            
            if not data:
                break
                
            for item in data:
                self._import_salla_product(item)
                synced_count += 1
                
            # Check pagination
            if pagination.get('currentPage') < pagination.get('totalPages', 0):
                page += 1
            else:
                has_more = False
                
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Salla Sync',
                'message': f"Synced {synced_count} products from Salla.",
                'type': 'success',
                'sticky': False,
            }
        }

    def _import_salla_product(self, data):
        """
        Creates or updates a product.template from Salla data.
        """
        salla_id = str(data.get('id'))
        name = data.get('name')
        price = float(data.get('price', {}).get('amount', 0.0))
        sku = data.get('sku') or ''
        description = data.get('description') or ''
        
        # Check standard mapped fields
        vals = {
            'name': name,
            'list_price': price,
            'default_code': sku,
            'description_sale': description,
            # 'detailed_type': 'product', # Defaulting to storable/consumable as per Odoo version, 18 uses 'product' usually
            'salla_url': data.get('urls', {}).get('customer', ''),
            'salla_metadata': str(data),
        }

        # Search by Salla ID first
        product = self.search([('salla_product_id', '=', salla_id)], limit=1)
        
        if product:
            product.write(vals)
        else:
            # Fallback: Search by SKU if no Salla ID (prevent duplicates on first sync)
            if sku:
                product = self.search([('default_code', '=', sku)], limit=1)
                if product:
                    vals['salla_product_id'] = salla_id
                    product.write(vals)
                    return # Updated existing by SKU
            
            # Create new
            vals['salla_product_id'] = salla_id
            if 'detailed_type' in self._fields:  # Odoo 17
                vals['detailed_type'] = 'product'
            else:                                # Odoo 18/19
                vals['type'] = 'consu'
                if 'is_storable' in self._fields:
                    vals['is_storable'] = True
            self.create(vals)
