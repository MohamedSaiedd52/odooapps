from odoo import models, fields, api
import requests
import logging
from datetime import timedelta
from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

# Shopify API Version - 2024-01 is stable
API_VERSION = '2024-01'

class ShopifyInstance(models.Model):
    _name = 'shopify.instance'
    _description = 'Shopify Store Instance'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Instance Name', required=True, tracking=True)
    shop_url = fields.Char('Shopify Shop URL', required=True, help='e.g. https://yourstore.myshopify.com', tracking=True)
    api_key = fields.Char('API Key', help='API Key from Shopify App')
    password = fields.Char('API Password', help='API Secret Key from Shopify App')
    shared_secret = fields.Char('Shared Secret', help='Shared Secret for webhook verification')
    access_token = fields.Char('Access Token', required=True, help='Admin API Access Token (starts with shpat_)')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    active = fields.Boolean('Active', default=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('connected', 'Connected'),
        ('error', 'Error'),
    ], string='Status', default='draft', tracking=True)
    last_sync = fields.Datetime('Last Sync')
    last_product_sync = fields.Datetime('Last Product Sync')
    last_order_sync = fields.Datetime('Last Order Sync')
    last_customer_sync = fields.Datetime('Last Customer Sync')
    last_inventory_sync = fields.Datetime('Last Inventory Sync')
    note = fields.Text('Notes')

    # Sync Settings
    auto_sync_products = fields.Boolean('Auto Sync Products', default=True)
    auto_sync_orders = fields.Boolean('Auto Sync Orders', default=True)
    auto_sync_customers = fields.Boolean('Auto Sync Customers', default=True)
    auto_sync_inventory = fields.Boolean('Auto Sync Inventory', default=True)
    sync_from_date = fields.Date('Sync From Date', help='Only sync orders/customers created after this date')

    # ============ PRODUCTION INTEGRATION SETTINGS ============
    # Product Settings
    sync_products_from_shopify = fields.Boolean(
        'Sync Products from Shopify',
        default=False,
        help='If disabled, products will only be looked up by SKU/Barcode, never created from Shopify'
    )
    product_lookup_field = fields.Selection([
        ('sku', 'SKU (default_code)'),
        ('barcode', 'Barcode'),
    ], default='sku', string='Product Lookup Field',
        help='Field to use when looking up existing Odoo products')
    skip_orders_missing_products = fields.Boolean(
        'Skip Lines with Missing Products',
        default=False,
        help='If enabled, order lines with products not found in Odoo will be skipped instead of creating placeholder'
    )

    # Customer Settings
    use_fixed_customer = fields.Boolean(
        'Use Fixed Customer for All Orders',
        default=False,
        help='If enabled, all Shopify orders will be assigned to a single fixed customer'
    )
    fixed_customer_id = fields.Many2one(
        'res.partner',
        string='Fixed Shopify Customer',
        help='All Shopify orders will be assigned to this customer when "Use Fixed Customer" is enabled'
    )
    store_customer_name_in_order = fields.Boolean(
        'Store Customer Name in Order',
        default=True,
        help='Store the actual customer name from Shopify in the customer_name field on Sale Order'
    )

    # Discount Settings
    map_discount_codes = fields.Boolean(
        'Map Discount Codes to Schemes',
        default=False,
        help='Map Shopify discount codes to Odoo discount.scheme records (requires sale_discount_total module)'
    )
    default_discount_scheme_name = fields.Char(
        'Default Discount Scheme Name',
        help='Name of the default discount scheme to use when Shopify discount code is not found (must match exactly)'
    )

    @property
    def default_discount_scheme_id(self):
        """Get the default discount scheme record by name (dynamic lookup)"""
        if not self.default_discount_scheme_name:
            return False
        if 'discount.scheme' not in self.env:
            return False
        return self.env['discount.scheme'].search([
            ('name', '=', self.default_discount_scheme_name)
        ], limit=1)

    # Dashboard KPIs
    total_sales = fields.Monetary(string='Total Sales', currency_field='currency_id', compute='_compute_dashboard_kpis')
    product_count = fields.Integer(string='Shopify Products', compute='_compute_dashboard_kpis')
    odoo_product_count = fields.Integer(string='Odoo Products', compute='_compute_dashboard_kpis')
    order_count = fields.Integer(string='Orders', compute='_compute_dashboard_kpis')
    customer_count = fields.Integer(string='Customers', compute='_compute_dashboard_kpis')
    queue_job_count = fields.Integer(string='Queue Jobs', compute='_compute_dashboard_kpis')
    error_count = fields.Integer(string='Errors', compute='_compute_dashboard_kpis')
    sales_chart_data = fields.Json(string='Sales Chart Data', compute='_compute_dashboard_kpis')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    # Dummy field for charts widget
    dashboard_charts = fields.Char(string='Dashboard Charts', compute='_compute_dashboard_charts')

    if hasattr(models, 'Constraint'):  # Odoo 19+ ignores _sql_constraints
        _shop_url_uniq = models.Constraint(
            'UNIQUE(shop_url, company_id)',
            "A Shopify instance with this URL already exists for this company!")
    else:
        _sql_constraints = [
            ('shop_url_uniq', 'unique(shop_url, company_id)', 'A Shopify instance with this URL already exists for this company!'),
        ]

    def _get_shopify_headers(self):
        """Get headers for Shopify API requests using Access Token"""
        self.ensure_one()
        return {
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json',
        }

    def _get_shopify_api_url(self, endpoint):
        """Build Shopify API URL"""
        self.ensure_one()
        shop_url = self.shop_url.rstrip('/')
        return f"{shop_url}/admin/api/{API_VERSION}/{endpoint}"

    def _shopify_request(self, endpoint, method='GET', data=None, params=None):
        """Make a request to Shopify API"""
        self.ensure_one()
        url = self._get_shopify_api_url(endpoint)
        headers = self._get_shopify_headers()

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, headers=headers, json=data, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                raise UserError(_("Unsupported HTTP method: %s") % method)

            # Log the request
            _logger.info("Shopify API %s %s - Status: %s", method, endpoint, response.status_code)

            if response.status_code in [200, 201]:
                return response.json()
            elif response.status_code == 204:
                return {}
            elif response.status_code == 429:
                # Rate limited - Shopify returns retry-after header
                retry_after = response.headers.get('Retry-After', 2)
                raise UserError(_("Rate limited by Shopify. Please wait %s seconds and try again.") % retry_after)
            else:
                error_msg = response.text
                try:
                    error_data = response.json()
                    if 'errors' in error_data:
                        error_msg = str(error_data['errors'])
                except:
                    pass
                raise UserError(_("Shopify API Error [%s]: %s") % (response.status_code, error_msg))

        except requests.exceptions.Timeout:
            raise UserError(_("Connection to Shopify timed out. Please try again."))
        except requests.exceptions.ConnectionError:
            raise UserError(_("Could not connect to Shopify. Please check your internet connection."))

    def _shopify_request_with_link(self, endpoint, method='GET', data=None, params=None):
        """Make a request to Shopify API and return response with Link header for pagination"""
        self.ensure_one()

        # Check if endpoint is a full URL (for pagination)
        if endpoint.startswith('http'):
            url = endpoint
        else:
            url = self._get_shopify_api_url(endpoint)

        headers = self._get_shopify_headers()

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=60)
            else:
                response = requests.get(url, headers=headers, params=params, timeout=60)

            _logger.info("Shopify API %s %s - Status: %s", method, endpoint[:50], response.status_code)

            if response.status_code in [200, 201]:
                # Parse Link header for pagination
                next_link = None
                link_header = response.headers.get('Link', '')
                if link_header:
                    # Parse Link header: <url>; rel="next", <url>; rel="previous"
                    links = link_header.split(',')
                    for link in links:
                        parts = link.strip().split(';')
                        if len(parts) == 2:
                            link_url = parts[0].strip().strip('<>')
                            link_rel = parts[1].strip()
                            if 'rel="next"' in link_rel:
                                next_link = link_url
                                break

                return response.json(), next_link
            elif response.status_code == 429:
                import time
                retry_after = int(response.headers.get('Retry-After', 2))
                _logger.warning("Rate limited, sleeping for %d seconds", retry_after)
                time.sleep(retry_after)
                return self._shopify_request_with_link(endpoint, method, data, params)
            else:
                error_msg = response.text
                try:
                    error_data = response.json()
                    if 'errors' in error_data:
                        error_msg = str(error_data['errors'])
                except:
                    pass
                raise UserError(_("Shopify API Error [%s]: %s") % (response.status_code, error_msg))

        except requests.exceptions.Timeout:
            raise UserError(_("Connection to Shopify timed out. Please try again."))
        except requests.exceptions.ConnectionError:
            raise UserError(_("Could not connect to Shopify. Please check your internet connection."))

    def action_test_connection(self):
        """Test connection to Shopify using Access Token"""
        self.ensure_one()
        try:
            result = self._shopify_request('shop.json')
            if result and 'shop' in result:
                shop_info = result['shop']
                self.state = 'connected'
                self.last_sync = fields.Datetime.now()
                message = _('Connection successful! Connected to: %s (%s)') % (
                    shop_info.get('name', ''),
                    shop_info.get('myshopify_domain', '')
                )
                self.message_post(body=message)
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Shopify Connection'),
                        'message': message,
                        'type': 'success',
                        'sticky': False,
                    },
                }
            else:
                self.state = 'error'
                raise UserError(_("Invalid response from Shopify"))
        except UserError:
            self.state = 'error'
            raise
        except Exception as e:
            self.state = 'error'
            _logger.exception("Shopify connection error")
            raise UserError(_("Connection error: %s") % str(e))

    def _compute_dashboard_charts(self):
        """Dummy compute for charts widget"""
        for rec in self:
            rec.dashboard_charts = 'charts'

    def _compute_dashboard_kpis(self):
        for rec in self:
            rec.product_count = self.env['shopify.product'].search_count([('instance_id', '=', rec.id), ('active', '=', True)])
            # Count Odoo products (saleable and active) - for Production Mode
            rec.odoo_product_count = self.env['product.product'].search_count([('sale_ok', '=', True), ('active', '=', True)])
            rec.order_count = self.env['shopify.order'].search_count([('instance_id', '=', rec.id), ('active', '=', True)])
            rec.customer_count = self.env['shopify.customer'].search_count([('instance_id', '=', rec.id), ('active', '=', True)])
            rec.queue_job_count = self.env['shopify.queue.job'].search_count([('instance_id', '=', rec.id)])
            rec.error_count = self.env['shopify.log'].search_count([('job_id.instance_id', '=', rec.id), ('log_type', '=', 'error')])

            # Calculate total sales directly from Shopify orders (total_price field)
            orders = self.env['shopify.order'].search([
                ('instance_id', '=', rec.id),
                ('active', '=', True),
            ])
            rec.total_sales = sum(orders.mapped('total_price') or [0.0])

            # Sales chart: sales per month for last 12 months using order_date from shopify.order
            sales_by_month = {}
            for order in orders:
                if order.order_date:
                    month = order.order_date.strftime('%Y-%m')
                    sales_by_month.setdefault(month, 0)
                    sales_by_month[month] += order.total_price or 0.0
            # Sort and keep last 12 months
            sorted_months = sorted(sales_by_month.keys())[-12:]
            rec.sales_chart_data = {
                'labels': sorted_months,
                'values': [round(sales_by_month[m], 2) for m in sorted_months]
            }

    # ==================== UPDATE EXISTING ORDERS ====================

    def action_update_existing_orders(self):
        """Re-sync existing orders to apply new changes:
        1. Remove discount lines (SHOPIFY-DISCOUNT product)
        2. Remove discount from shipping lines (SHOPIFY-SHIPPING product)
        3. Apply tax_included to product lines (VAT 15% Included)
        """
        self.ensure_one()
        if self.state != 'connected':
            raise UserError(_('Please test the connection first!'))

        # Find all shopify.order records for this instance that have odoo_order_id
        shopify_orders = self.env['shopify.order'].search([
            ('instance_id', '=', self.id),
            ('odoo_order_id', '!=', False),
        ])

        updated_count = 0
        error_count = 0

        for shop_order in shopify_orders:
            try:
                odoo_order = shop_order.odoo_order_id
                if not odoo_order:
                    continue

                order_updated = False

                # 1. Delete discount lines (product with SHOPIFY-DISCOUNT code)
                discount_lines = odoo_order.order_line.filtered(
                    lambda l: l.product_id and l.product_id.default_code == 'SHOPIFY-DISCOUNT'
                )
                if discount_lines:
                    discount_lines.unlink()
                    _logger.info("Removed discount line from order %s", odoo_order.name)
                    order_updated = True

                # 2. Remove discount from shipping lines (SHOPIFY-SHIPPING product)
                shipping_lines = odoo_order.order_line.filtered(
                    lambda l: l.product_id and l.product_id.default_code == 'SHOPIFY-SHIPPING' and l.discount > 0
                )
                if shipping_lines:
                    shipping_lines.write({'discount': 0})
                    _logger.info("Removed discount from shipping line in order %s", odoo_order.name)
                    order_updated = True

                # 3. Apply tax to product lines (not shipping)
                # Get tax rate from shopify.order tax_lines_json
                tax_rate = 0
                tax_record = False
                if shop_order.tax_lines_json:
                    try:
                        import json
                        tax_lines = json.loads(shop_order.tax_lines_json)
                        if tax_lines:
                            tax_rate = float(tax_lines[0].get('rate', 0)) * 100
                            t_title = tax_lines[0].get('title', 'VAT')
                            if tax_rate > 0:
                                tax_record = self._get_or_create_tax_for_shopify(tax_rate, t_title, self.company_id)
                    except Exception as e:
                        _logger.warning("Could not parse tax_lines_json for order %s: %s", shop_order.name, str(e))

                # Apply tax and convert prices for product lines (exclude shipping)
                if tax_record and tax_rate > 0:
                    product_lines = odoo_order.order_line.filtered(
                        lambda l: l.product_id and l.product_id.default_code != 'SHOPIFY-SHIPPING'
                    )
                    for line in product_lines:
                        # Convert tax-inclusive price to untaxed price
                        current_price = line.price_unit
                        untaxed_price = current_price / (1 + tax_rate / 100)

                        # Update line with untaxed price and tax
                        line.write({
                            'price_unit': untaxed_price,
                            'tax_id': [(6, 0, [tax_record.id])]
                        })
                        order_updated = True

                    if order_updated:
                        _logger.info("Applied tax to order %s", odoo_order.name)

                if order_updated:
                    updated_count += 1

            except Exception as e:
                error_count += 1
                _logger.error("Error updating order %s: %s", shop_order.shopify_order_number, str(e))

        # Commit changes
        self.env.cr.commit()

        # Show result message
        message = f"Updated {updated_count} orders, {error_count} errors"
        _logger.info(message)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Update Complete',
                'message': message,
                'type': 'success' if error_count == 0 else 'warning',
                'sticky': False,
            }
        }

    def _get_or_create_tax_for_shopify(self, tax_rate, tax_name, company):
        """Find or create a regular tax (NOT price_include)"""
        tax = self.env['account.tax'].search([
            ('amount', '=', tax_rate),
            ('type_tax_use', '=', 'sale'),
            ('price_include', '=', False),
            ('company_id', '=', company.id),
        ], limit=1)

        if tax:
            return tax

        try:
            tax = self.env['account.tax'].create({
                'name': f"{tax_name} {tax_rate}%",
                'amount': tax_rate,
                'type_tax_use': 'sale',
                'price_include': False,
                'company_id': company.id,
            })
            _logger.info("Created tax: %s", tax.name)
            return tax
        except Exception as e:
            _logger.error("Error creating tax: %s", str(e))
            return False

    # ==================== CRON METHODS ====================

    @api.model
    def _cron_sync_products(self):
        """Cron job to sync products from all active Shopify instances"""
        instances = self.search([('state', '=', 'connected'), ('active', '=', True), ('auto_sync_products', '=', True)])
        for instance in instances:
            try:
                _logger.info("Starting product sync for instance: %s", instance.name)
                self.env['shopify.product'].import_products_from_shopify(instance)
                instance.last_product_sync = fields.Datetime.now()
                self.env.cr.commit()
            except Exception as e:
                _logger.error("Error syncing products for instance %s: %s", instance.name, str(e))
                self.env['shopify.log'].sudo().create({
                    'name': 'Product Sync Error',
                    'log_type': 'error',
                    'message': f"Error syncing products for {instance.name}: {str(e)}",
                })
                self.env.cr.commit()

    @api.model
    def _cron_sync_orders(self):
        """Cron job to sync orders from all active Shopify instances"""
        instances = self.search([('state', '=', 'connected'), ('active', '=', True), ('auto_sync_orders', '=', True)])
        for instance in instances:
            try:
                _logger.info("Starting order sync for instance: %s", instance.name)
                self.env['shopify.order'].import_orders_from_shopify(instance)
                instance.last_order_sync = fields.Datetime.now()
                self.env.cr.commit()
            except Exception as e:
                _logger.error("Error syncing orders for instance %s: %s", instance.name, str(e))
                self.env['shopify.log'].sudo().create({
                    'name': 'Order Sync Error',
                    'log_type': 'error',
                    'message': f"Error syncing orders for {instance.name}: {str(e)}",
                })
                self.env.cr.commit()

    @api.model
    def _cron_sync_customers(self):
        """Cron job to sync customers from all active Shopify instances"""
        instances = self.search([('state', '=', 'connected'), ('active', '=', True), ('auto_sync_customers', '=', True)])
        for instance in instances:
            try:
                _logger.info("Starting customer sync for instance: %s", instance.name)
                self.env['shopify.customer'].import_customers_from_shopify(instance)
                instance.last_customer_sync = fields.Datetime.now()
                self.env.cr.commit()
            except Exception as e:
                _logger.error("Error syncing customers for instance %s: %s", instance.name, str(e))
                self.env['shopify.log'].sudo().create({
                    'name': 'Customer Sync Error',
                    'log_type': 'error',
                    'message': f"Error syncing customers for {instance.name}: {str(e)}",
                })
                self.env.cr.commit()

    @api.model
    def _cron_sync_inventory(self):
        """Cron job to sync inventory from all active Shopify instances"""
        instances = self.search([('state', '=', 'connected'), ('active', '=', True), ('auto_sync_inventory', '=', True)])
        for instance in instances:
            try:
                _logger.info("Starting inventory sync for instance: %s", instance.name)
                self.env['shopify.product'].sync_inventory_from_shopify(instance)
                instance.last_inventory_sync = fields.Datetime.now()
                self.env.cr.commit()
            except Exception as e:
                _logger.error("Error syncing inventory for instance %s: %s", instance.name, str(e))
                self.env['shopify.log'].sudo().create({
                    'name': 'Inventory Sync Error',
                    'log_type': 'error',
                    'message': f"Error syncing inventory for {instance.name}: {str(e)}",
                })
                self.env.cr.commit()

    # ==================== MANUAL SYNC ACTIONS ====================

    def action_sync_products(self):
        """Manual action to sync products"""
        self.ensure_one()
        if self.state != 'connected':
            raise UserError(_("Please test the connection first!"))
        self.env['shopify.product'].import_products_from_shopify(self)
        self.last_product_sync = fields.Datetime.now()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Shopify Sync'),
                'message': _('Products synced successfully!'),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_sync_orders(self):
        """Manual action to sync orders"""
        self.ensure_one()
        if self.state != 'connected':
            raise UserError(_("Please test the connection first!"))
        self.env['shopify.order'].import_orders_from_shopify(self)
        self.last_order_sync = fields.Datetime.now()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Shopify Sync'),
                'message': _('Orders synced successfully!'),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_force_resync_orders(self):
        """Force re-sync all orders - deletes existing Sale Orders and recreates them"""
        self.ensure_one()
        if self.state != 'connected':
            raise UserError(_("Please test the connection first!"))

        # Delete all Sale Orders linked to Shopify orders for this instance
        shopify_orders = self.env['shopify.order'].search([('instance_id', '=', self.id)])
        deleted_count = 0
        for order in shopify_orders:
            if order.odoo_order_id:
                try:
                    # Only delete if in draft or cancel state
                    if order.odoo_order_id.state in ['draft', 'sent', 'cancel']:
                        order.odoo_order_id.unlink()
                    else:
                        # Cancel first then delete
                        order.odoo_order_id.action_cancel()
                        order.odoo_order_id.unlink()
                    deleted_count += 1
                except Exception as e:
                    _logger.warning("Could not delete Sale Order %s: %s", order.odoo_order_id.name, str(e))
            order.odoo_order_id = False

        # Reset last sync date to force full re-sync
        self.last_order_sync = False

        # Run sync again
        self.env['shopify.order'].import_orders_from_shopify(self)
        self.last_order_sync = fields.Datetime.now()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Force Re-sync Complete'),
                'message': _('Deleted %d old Sale Orders and re-synced from Shopify!') % deleted_count,
                'type': 'success',
                'sticky': False,
            },
        }

    def action_refresh_existing_orders(self):
        """Refresh existing orders from Shopify - recalculates discounts without deleting

        This method re-fetches each order from Shopify and updates the sale.order
        with correct discount calculations.
        """
        self.ensure_one()
        if self.state != 'connected':
            raise UserError(_("Please test the connection first!"))

        shopify_orders = self.env['shopify.order'].search([
            ('instance_id', '=', self.id),
            ('odoo_order_id', '!=', False),
        ])

        if not shopify_orders:
            raise UserError(_("No orders found to refresh!"))

        updated_count = 0
        error_count = 0
        ShopifyOrder = self.env['shopify.order']

        for order in shopify_orders:
            try:
                # Fetch fresh order data from Shopify
                result = self._shopify_request(
                    f'orders/{order.shopify_order_id}.json'
                )

                if not result or 'order' not in result:
                    _logger.warning("Could not fetch order %s from Shopify", order.name)
                    error_count += 1
                    continue

                shopify_order_data = result['order']

                # Update the shopify.order line items
                order._sync_order_line_items(shopify_order_data)

                # Update the sale.order with new discount logic
                if order.odoo_order_id:
                    ShopifyOrder._update_odoo_sale_order(order.odoo_order_id, self, shopify_order_data)

                order.write({
                    'last_sync': fields.Datetime.now(),
                    'sync_status': 'synced',
                })

                updated_count += 1
                _logger.info("Refreshed order %s", order.name)

                # Commit every 10 orders
                if updated_count % 10 == 0:
                    self.env.cr.commit()

            except Exception as e:
                _logger.error("Error refreshing order %s: %s", order.name, str(e))
                error_count += 1

        self.env.cr.commit()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Orders Refreshed'),
                'message': _('Updated %d orders, %d errors') % (updated_count, error_count),
                'type': 'success' if error_count == 0 else 'warning',
                'sticky': False,
            },
        }

    def action_sync_customers(self):
        """Manual action to sync customers"""
        self.ensure_one()
        if self.state != 'connected':
            raise UserError(_("Please test the connection first!"))
        self.env['shopify.customer'].import_customers_from_shopify(self)
        self.last_customer_sync = fields.Datetime.now()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Shopify Sync'),
                'message': _('Customers synced successfully!'),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_sync_all(self):
        """Manual action to sync everything"""
        self.ensure_one()
        if self.state != 'connected':
            raise UserError(_("Please test the connection first!"))
        self.action_sync_products()
        self.action_sync_customers()
        self.action_sync_orders()
        self.last_sync = fields.Datetime.now()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Shopify Sync'),
                'message': _('All data synced successfully!'),
                'type': 'success',
                'sticky': False,
            },
        }

    @api.model
    def action_open_dashboard(self):
        """Open the automation dashboard for the first connected instance"""
        instance = self.search([('state', '=', 'connected'), ('active', '=', True)], limit=1)
        if not instance:
            raise UserError(_("No connected Shopify instance found! Please connect an instance first."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Automation Dashboard'),
            'res_model': 'shopify.instance',
            'view_mode': 'form',
            'res_id': instance.id,
            'view_id': self.env.ref('ms_shopify_automation.view_shopify_modern_dashboard').id,
            'target': 'current',
            'context': {'form_view_initial_mode': 'readonly'},
        }

    @api.model
    def get_dashboard_data(self):
        """Get dashboard data for JS charts - called by dashboard.js"""
        instance = self.search([('state', '=', 'connected'), ('active', '=', True)], limit=1)
        if not instance:
            return {}

        # Get orders for charts
        orders = self.env['shopify.order'].search([
            ('instance_id', '=', instance.id),
            ('active', '=', True),
        ])

        # Sales chart data - sales per month
        sales_by_month = {}
        for order in orders:
            if order.order_date:
                month = order.order_date.strftime('%Y-%m')
                sales_by_month.setdefault(month, 0)
                sales_by_month[month] += order.total_price or 0.0
        sorted_months = sorted(sales_by_month.keys())[-12:]

        # Customer growth - customers per month
        customers = self.env['shopify.customer'].search([
            ('instance_id', '=', instance.id),
            ('active', '=', True),
        ])
        customers_by_month = {}
        for customer in customers:
            if customer.create_date:
                month = customer.create_date.strftime('%Y-%m')
                customers_by_month.setdefault(month, 0)
                customers_by_month[month] += 1
        sorted_customer_months = sorted(customers_by_month.keys())[-6:]

        # Inventory status
        products = self.env['shopify.product'].search([
            ('instance_id', '=', instance.id),
            ('active', '=', True),
        ])
        in_stock = 0
        low_stock = 0
        out_of_stock = 0
        for product in products:
            if product.odoo_product_id:
                qty = product.odoo_product_id.qty_available
                if qty <= 0:
                    out_of_stock += 1
                elif qty <= 10:
                    low_stock += 1
                else:
                    in_stock += 1
            else:
                in_stock += 1  # Default to in stock if no Odoo product linked

        # Revenue distribution (placeholder - could be enhanced)
        total_sales = sum(orders.mapped('total_price') or [0.0])

        # Queue job counts - all jobs for this instance
        queue_jobs = self.env['shopify.queue.job'].search([
            ('instance_id', '=', instance.id),
        ])

        # Error counts from logs (all errors in last 7 days)
        error_logs = self.env['shopify.log'].search([
            ('log_type', '=', 'error'),
            ('create_date', '>=', fields.Datetime.now() - timedelta(days=7)),
        ])

        return {
            'order_count': len(orders),
            'customer_count': len(customers),
            'product_count': len(products),
            'total_sales': total_sales,
            'queue_job_count': len(queue_jobs),
            'error_count': len(error_logs),
            'sales_chart_data': {
                'labels': sorted_months,
                'values': [round(sales_by_month.get(m, 0), 2) for m in sorted_months]
            },
            'customer_growth': [customers_by_month.get(m, 0) for m in sorted_customer_months],
            'customer_growth_labels': sorted_customer_months,
            'inventory_status': [in_stock, low_stock, out_of_stock],
            'revenue_distribution': [total_sales * 0.7, total_sales * 0.2, total_sales * 0.1],  # Placeholder
            'date_from': fields.Date.today().replace(day=1).isoformat() if fields.Date.today() else '',
            'date_to': fields.Date.today().isoformat() if fields.Date.today() else '',
        }