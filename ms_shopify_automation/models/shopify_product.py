# -*- coding: utf-8 -*-
from odoo import models, fields, api

from .compat import STORABLE_TYPE, default_product_category
import logging
from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class ShopifyProduct(models.Model):
    _name = 'shopify.product'
    _description = 'Shopify Product Mapping'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Shopify Product Name', tracking=True)
    shopify_product_id = fields.Char('Shopify Product ID', required=True, tracking=True)
    shopify_variant_id = fields.Char('Shopify Variant ID')
    odoo_product_id = fields.Many2one('product.product', string='Odoo Product')
    instance_id = fields.Many2one('shopify.instance', string='Shopify Instance', required=True, ondelete='cascade')
    sync_status = fields.Selection([
        ('synced', 'Synced'),
        ('pending', 'Pending'),
        ('error', 'Error'),
    ], string='Sync Status', default='pending', tracking=True)
    last_sync = fields.Datetime('Last Sync')
    active = fields.Boolean('Active', default=True)

    # Additional Shopify fields
    shopify_handle = fields.Char('Handle')
    shopify_product_type = fields.Char('Product Type')
    shopify_vendor = fields.Char('Vendor')
    shopify_tags = fields.Char('Tags')
    shopify_status = fields.Selection([
        ('active', 'Active'),
        ('archived', 'Archived'),
        ('draft', 'Draft'),
    ], string='Shopify Status', default='active')
    body_html = fields.Html('Description')
    shopify_price = fields.Float('Shopify Price')
    shopify_sku = fields.Char('SKU')
    shopify_inventory_quantity = fields.Integer('Inventory Quantity')
    shopify_image_url = fields.Char('Image URL')

    note = fields.Text('Notes')

    if hasattr(models, 'Constraint'):  # Odoo 19+ ignores _sql_constraints
        _uniq_shopify_product_instance = models.Constraint(
            'UNIQUE(shopify_product_id, shopify_variant_id, instance_id)',
            "This Shopify product/variant is already mapped for this instance!")
    else:
        _sql_constraints = [
            ('uniq_shopify_product_instance', 'unique(shopify_product_id, shopify_variant_id, instance_id)',
             'This Shopify product/variant is already mapped for this instance!'),
        ]

    def import_products_from_shopify(self, instance):
        """Import products from Shopify for the given instance using Access Token"""
        if not instance:
            raise UserError(_('No Shopify instance provided.'))

        if instance.state != 'connected':
            raise UserError(_('Please test the connection first!'))

        # Create queue job
        job = self.env['shopify.queue.job'].create({
            'name': f'Import Products ({instance.name})',
            'job_type': 'import_product',
            'instance_id': instance.id,
            'status': 'in_progress',
        })

        try:
            # Use cursor-based pagination to get ALL products from Shopify
            all_products = []
            endpoint = 'products.json'
            params = {'limit': 250}
            page_count = 0
            max_pages = 200  # Safety limit: 200 pages * 250 = 50,000 products max

            while page_count < max_pages:
                page_count += 1
                result, next_link = instance._shopify_request_with_link(endpoint, params=params)
                products = result.get('products', [])
                all_products.extend(products)

                _logger.info("Product import page %d: fetched %d products (total: %d)",
                            page_count, len(products), len(all_products))

                # Check if there's a next page
                if not next_link:
                    break

                # Use next page URL for cursor-based pagination
                endpoint = next_link
                params = {}

            products = all_products
            _logger.info("Total products fetched from Shopify: %d", len(products))

            self.env['shopify.log'].create({
                'name': 'Product Import Started',
                'log_type': 'info',
                'job_id': job.id,
                'message': f'Starting import of {len(products)} products from Shopify instance {instance.name}',
            })

            created_count = 0
            updated_count = 0
            error_count = 0

            for shopify_product in products:
                try:
                    product_id = str(shopify_product.get('id'))

                    # Check if product mapping already exists
                    existing_mapping = self.search([
                        ('shopify_product_id', '=', product_id),
                        ('shopify_variant_id', '=', False),
                        ('instance_id', '=', instance.id)
                    ], limit=1)

                    # Get first variant for price/sku
                    variants = shopify_product.get('variants', [])
                    first_variant = variants[0] if variants else {}

                    # Get first image
                    images = shopify_product.get('images', [])
                    first_image = images[0].get('src') if images else ''

                    product_vals = {
                        'name': shopify_product.get('title', 'Unknown Product'),
                        'shopify_product_id': product_id,
                        'instance_id': instance.id,
                        'shopify_handle': shopify_product.get('handle', ''),
                        'shopify_product_type': shopify_product.get('product_type', ''),
                        'shopify_vendor': shopify_product.get('vendor', ''),
                        'shopify_tags': shopify_product.get('tags', ''),
                        'shopify_status': shopify_product.get('status', 'active'),
                        'body_html': shopify_product.get('body_html', ''),
                        'shopify_price': float(first_variant.get('price', 0)),
                        'shopify_sku': first_variant.get('sku', ''),
                        'shopify_inventory_quantity': first_variant.get('inventory_quantity', 0),
                        'shopify_image_url': first_image,
                        'sync_status': 'synced',
                        'last_sync': fields.Datetime.now(),
                    }

                    if existing_mapping:
                        existing_mapping.write(product_vals)
                        updated_count += 1
                    else:
                        # Create Odoo product
                        # Odoo 18 uses 'consu' for storable products instead of 'product'
                        odoo_product = self.env['product.product'].create({
                            'name': shopify_product.get('title', 'Unknown Product'),
                            'default_code': first_variant.get('sku', ''),
                            'list_price': float(first_variant.get('price', 0)),
                            'type': STORABLE_TYPE,  # 17 = 'product', 18/19 = 'consu' (compat.py)
                            'categ_id': default_product_category(self.env),
                        })
                        product_vals['odoo_product_id'] = odoo_product.id
                        self.create(product_vals)
                        created_count += 1

                    # Handle variants
                    for variant in variants:
                        variant_id = str(variant.get('id'))
                        existing_variant = self.search([
                            ('shopify_product_id', '=', product_id),
                            ('shopify_variant_id', '=', variant_id),
                            ('instance_id', '=', instance.id)
                        ], limit=1)

                        if not existing_variant and variant.get('title') != 'Default Title':
                            variant_vals = {
                                'name': f"{shopify_product.get('title', '')} - {variant.get('title', '')}",
                                'shopify_product_id': product_id,
                                'shopify_variant_id': variant_id,
                                'instance_id': instance.id,
                                'shopify_price': float(variant.get('price', 0)),
                                'shopify_sku': variant.get('sku', ''),
                                'shopify_inventory_quantity': variant.get('inventory_quantity', 0),
                                'sync_status': 'synced',
                                'last_sync': fields.Datetime.now(),
                            }
                            self.create(variant_vals)

                except Exception as e:
                    error_count += 1
                    _logger.error("Error importing product %s: %s", shopify_product.get('title', 'Unknown'), str(e))
                    self.env['shopify.log'].create({
                        'name': 'Product Import Error',
                        'log_type': 'error',
                        'job_id': job.id,
                        'message': f'Error importing product {shopify_product.get("title", "Unknown")}: {str(e)}',
                    })

            # Update job status
            job.write({'status': 'done'})
            self.env['shopify.log'].create({
                'name': 'Product Import Completed',
                'log_type': 'info',
                'job_id': job.id,
                'message': f'Import completed: {created_count} created, {updated_count} updated, {error_count} errors',
            })

            return products

        except Exception as e:
            job.write({'status': 'failed', 'error_message': str(e)})
            self.env['shopify.log'].create({
                'name': 'Product Import Failed',
                'log_type': 'error',
                'job_id': job.id,
                'message': f'Product import failed: {str(e)}',
            })
            raise UserError(_('Failed to import products: %s') % str(e))

    def export_products_to_shopify(self, instance, products):
        """Export products to Shopify"""
        if not instance:
            raise UserError(_('No Shopify instance provided.'))

        job = self.env['shopify.queue.job'].create({
            'name': f'Export Products ({instance.name})',
            'job_type': 'export_product',
            'instance_id': instance.id,
            'status': 'in_progress',
        })

        exported_count = 0
        error_count = 0

        for product_mapping in products:
            try:
                odoo_product = product_mapping.odoo_product_id
                if not odoo_product:
                    continue

                product_data = {
                    'product': {
                        'title': odoo_product.name,
                        'body_html': odoo_product.description_sale or '',
                        'vendor': 'Odoo',
                        'product_type': odoo_product.categ_id.name if odoo_product.categ_id else '',
                        'variants': [{
                            'price': str(odoo_product.list_price),
                            'sku': odoo_product.default_code or '',
                            'inventory_management': 'shopify',
                        }]
                    }
                }

                if product_mapping.shopify_product_id:
                    # Update existing
                    result = instance._shopify_request(
                        f'products/{product_mapping.shopify_product_id}.json',
                        method='PUT',
                        data=product_data
                    )
                else:
                    # Create new
                    result = instance._shopify_request('products.json', method='POST', data=product_data)

                if result and 'product' in result:
                    product_mapping.write({
                        'shopify_product_id': str(result['product']['id']),
                        'sync_status': 'synced',
                        'last_sync': fields.Datetime.now(),
                    })
                    exported_count += 1

            except Exception as e:
                error_count += 1
                self.env['shopify.log'].create({
                    'name': 'Product Export Error',
                    'log_type': 'error',
                    'job_id': job.id,
                    'message': f'Error exporting product: {str(e)}',
                })

        job.write({'status': 'done'})
        self.env['shopify.log'].create({
            'name': 'Product Export Completed',
            'log_type': 'info',
            'job_id': job.id,
            'message': f'Export completed: {exported_count} exported, {error_count} errors',
        })

        return True

    def sync_inventory_from_shopify(self, instance):
        """Sync inventory levels from Shopify"""
        if not instance:
            raise UserError(_('No Shopify instance provided.'))

        products = self.search([('instance_id', '=', instance.id), ('active', '=', True)])

        for product in products:
            try:
                if product.shopify_variant_id:
                    # Get inventory for variant
                    result = instance._shopify_request(f'variants/{product.shopify_variant_id}.json')
                    if result and 'variant' in result:
                        product.shopify_inventory_quantity = result['variant'].get('inventory_quantity', 0)
                        product.last_sync = fields.Datetime.now()
            except Exception as e:
                _logger.error("Error syncing inventory for product %s: %s", product.name, str(e))

        return True

    @api.model
    def _run_product_import_cron(self):
        """Cron job to import products from all active instances"""
        instances = self.env['shopify.instance'].search([
            ('state', '=', 'connected'),
            ('active', '=', True),
            ('auto_sync_products', '=', True)
        ])
        for instance in instances:
            try:
                self.import_products_from_shopify(instance)
            except Exception as e:
                _logger.error("Cron product import error for %s: %s", instance.name, str(e))