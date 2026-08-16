from odoo import fields, models, api
import logging
from .salla_api import SallaAPI

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    salla_order_id = fields.Char(string='Salla Order ID', copy=False, readonly=True)
    salla_status = fields.Char(string='Salla Status', readonly=True)
    salla_raw_data = fields.Text(string='Salla Raw Data', readonly=True)
    
    def action_sync_orders_from_salla(self):
        """
        Fetches orders from Salla and creates them in Odoo.
        """
        api_helper = SallaAPI(self.env)
        
        page = 1
        has_more = True
        synced_count = 0
        
        while has_more:
            response = api_helper.get_orders(page=page)
            if 'error' in response:
                _logger.error("Salla Order Sync Error: %s", response['error'])
                break
                
            data = response.get('data', [])
            pagination = response.get('pagination', {})
            
            if not data:
                break
                
            for item in data:
                try:
                    self._import_salla_order(item)
                    synced_count += 1
                except Exception as e:
                    _logger.error(f"Failed to import Salla Order {item.get('id')}: {e}")
                
            # Check pagination
            if pagination.get('currentPage') < pagination.get('totalPages', 0):
                page += 1
            else:
                has_more = False
                
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Salla Order Sync',
                'message': f"Synced {synced_count} orders from Salla.",
                'type': 'success',
                'sticky': False,
            }
        }

    def _import_salla_order(self, data):
        """
        Creates a sale.order from Salla data.
        """
        salla_id = str(data.get('id'))
        # Check existence
        order = self.search([('salla_order_id', '=', salla_id)], limit=1)
        if order:
            # Update status if changed? For now, skip to prevent overwriting edits
            return

        # 1. Partner
        customer_data = data.get('customer', {})
        partner = self._find_or_create_partner(customer_data)
        
        # 2. Lines
        order_lines = []
        items = data.get('items', [])
        for item in items:
            line_vals = self._prepare_order_line(item)
            if line_vals:
                order_lines.append((0, 0, line_vals))
                
        # 3. Create Order
        vals = {
            'partner_id': partner.id,
            'salla_order_id': salla_id,
            'salla_status': data.get('status', {}).get('name'),
            'salla_raw_data': str(data),
            'order_line': order_lines,
        }
        
        # Odoo requires picking type/warehouse if stock module installed?
        # Usually defaults work.
        
        self.create(vals)

    def _find_or_create_partner(self, data):
        Partner = self.env['res.partner']
        email = data.get('email')
        mobile = data.get('mobile')
        name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip() or "Salla Customer"

        # Odoo 19 merged res.partner 'mobile' into 'phone'
        phone_field = 'mobile' if 'mobile' in Partner._fields else 'phone'

        domain = []
        if mobile:
             domain = [(phone_field, '=', mobile)]
        elif email:
             domain = [('email', '=', email)]

        if domain:
            partner = Partner.search(domain, limit=1)
            if partner:
                return partner

        # Create
        return Partner.create({
            'name': name,
            'email': email,
            phone_field: mobile,
            'customer_rank': 1,
        })

    def _prepare_order_line(self, item):
        Product = self.env['product.product']
        
        salla_product_id = str(item.get('product', {}).get('id'))
        sku = item.get('sku')
        name = item.get('name', 'Salla Product')
        quantity = item.get('quantity', 1)
        price_unit = float(item.get('amounts', {}).get('price_without_tax', {}).get('amount', 0.0))
        
        # Find Product
        # 1. By Salla ID (stored in template)
        product_tmpl = self.env['product.template'].search([('salla_product_id', '=', salla_product_id)], limit=1)
        product = False
        if product_tmpl:
            product = Product.search([('product_tmpl_id', '=', product_tmpl.id)], limit=1)
            
        # 2. By SKU
        if not product and sku:
             product = Product.search([('default_code', '=', sku)], limit=1)
             
        product_id = product.id if product else False
        
        # Fallback if product not found? 
        # Ideally we should create it or use a default Service product.
        # For this version, let's create a line without product_id (Description only) or require product
        # Odoo Sale Order Line requires product_id in most standard flows.
        
        if not product_id:
             # Try to find a generic service/consumable or create on the fly?
             # Let's create a quick consumable product if missing to ensure order is created
             # OR log warning.
             # Better approach: Create product if missing
             product_vals = {
                 'name': name,
                 'default_code': sku,
                 'type': 'service', # Safer default if we don't know type
                 'list_price': price_unit,
                 'salla_product_id': salla_product_id
             }
             if salla_product_id: # Only if we have ID
                 product_tmpl = self.env['product.template'].create(product_vals)
                 product = Product.search([('product_tmpl_id', '=', product_tmpl.id)], limit=1)
                 product_id = product.id

        return {
            'product_id': product_id,
            'name': name, # Description
            'product_uom_qty': quantity,
            'price_unit': price_unit,
            # Taxes? Salla sends tax data, mapped similarly. Skipping for MVP.
        }
