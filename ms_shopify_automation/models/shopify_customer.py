# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
from odoo.exceptions import UserError
from odoo.tools.translate import _
from dateutil import parser as date_parser

_logger = logging.getLogger(__name__)


def parse_shopify_date(date_str):
    """Parse Shopify ISO date format to Odoo datetime"""
    if not date_str:
        return False
    try:
        dt = date_parser.parse(date_str)
        return dt.replace(tzinfo=None)
    except Exception:
        return False


class ShopifyCustomer(models.Model):
    _name = 'shopify.customer'
    _description = 'Shopify Customer Mapping'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Customer Name', compute='_compute_name', store=True)
    shopify_customer_id = fields.Char('Shopify Customer ID', required=True, tracking=True)
    odoo_partner_id = fields.Many2one('res.partner', string='Odoo Partner')
    instance_id = fields.Many2one('shopify.instance', string='Shopify Instance', required=True, ondelete='cascade')
    sync_status = fields.Selection([
        ('synced', 'Synced'),
        ('pending', 'Pending'),
        ('error', 'Error'),
    ], string='Sync Status', default='pending', tracking=True)
    last_sync = fields.Datetime('Last Sync')
    active = fields.Boolean('Active', default=True)

    # Shopify Customer Details
    email = fields.Char('Email')
    first_name = fields.Char('First Name')
    last_name = fields.Char('Last Name')
    phone = fields.Char('Phone')
    verified_email = fields.Boolean('Email Verified')
    accepts_marketing = fields.Boolean('Accepts Marketing')
    orders_count = fields.Integer('Orders Count')
    total_spent = fields.Float('Total Spent')
    currency = fields.Char('Currency')
    shopify_tags = fields.Char('Tags')
    shopify_state = fields.Selection([
        ('disabled', 'Disabled'),
        ('invited', 'Invited'),
        ('enabled', 'Enabled'),
        ('declined', 'Declined'),
    ], string='Account State')
    created_at = fields.Datetime('Created At')
    updated_at = fields.Datetime('Updated At')

    # Address fields
    default_address_line1 = fields.Char('Address Line 1')
    default_address_line2 = fields.Char('Address Line 2')
    default_city = fields.Char('City')
    default_province = fields.Char('Province/State')
    default_country = fields.Char('Country')
    default_zip = fields.Char('ZIP Code')

    note = fields.Text('Notes')

    if hasattr(models, 'Constraint'):  # Odoo 19+ ignores _sql_constraints
        _uniq_shopify_customer_instance = models.Constraint(
            'UNIQUE(shopify_customer_id, instance_id)',
            "This Shopify customer is already mapped for this instance!")
    else:
        _sql_constraints = [
            ('uniq_shopify_customer_instance', 'unique(shopify_customer_id, instance_id)',
             'This Shopify customer is already mapped for this instance!'),
        ]

    @api.depends('first_name', 'last_name', 'email')
    def _compute_name(self):
        for rec in self:
            name = f"{rec.first_name or ''} {rec.last_name or ''}".strip()
            rec.name = name or rec.email or 'Unknown Customer'

    def import_customers_from_shopify(self, instance, max_records=250):
        """Import customers from Shopify for the given instance using Access Token

        Args:
            instance: shopify.instance record
            max_records: Maximum number of customers to import (default 250)
        """
        if not instance:
            raise UserError(_('No Shopify instance provided.'))

        if instance.state != 'connected':
            raise UserError(_('Please test the connection first!'))

        # Create queue job
        job = self.env['shopify.queue.job'].create({
            'name': f'Import Customers ({instance.name})',
            'job_type': 'import_customer',
            'instance_id': instance.id,
            'status': 'in_progress',
        })

        try:
            # Use cursor-based pagination with batch processing for large datasets
            endpoint = 'customers.json'
            params = {'limit': 250}

            # INCREMENTAL SYNC: Only fetch customers updated after last sync
            is_incremental = False
            if instance.last_customer_sync:
                params['updated_at_min'] = instance.last_customer_sync.isoformat()
                is_incremental = True
                _logger.info("Incremental sync: fetching customers updated after %s", instance.last_customer_sync)
            else:
                _logger.info("Full sync: fetching all customers (first time)")

            page_count = 0
            max_pages = 2000  # Safety limit: 2000 pages * 250 = 500,000 customers max

            total_created = 0
            total_updated = 0
            total_errors = 0
            total_fetched = 0
            total_processed = 0
            batch_size = 100  # Process and commit every 100 customers

            # If max_records is set, adjust the limit parameter
            if max_records > 0 and max_records < 250:
                params['limit'] = max_records

            while page_count < max_pages:
                # Check if we've reached the max_records limit
                if max_records > 0 and total_processed >= max_records:
                    _logger.info("Reached max_records limit of %d", max_records)
                    break
                page_count += 1
                result, next_link = instance._shopify_request_with_link(endpoint, params=params)
                customers_batch = result.get('customers', [])
                batch_count = len(customers_batch)
                total_fetched += batch_count

                _logger.info("Customer import page %d: fetched %d customers (total fetched: %d)",
                            page_count, batch_count, total_fetched)

                # Process this batch immediately instead of storing all in memory
                for i, shopify_customer in enumerate(customers_batch):
                    try:
                        customer_id = str(shopify_customer.get('id'))

                        # Check if customer mapping already exists
                        existing_mapping = self.search([
                            ('shopify_customer_id', '=', customer_id),
                            ('instance_id', '=', instance.id)
                        ], limit=1)

                        # Get default address
                        default_address = shopify_customer.get('default_address', {}) or {}

                        customer_vals = {
                            'shopify_customer_id': customer_id,
                            'instance_id': instance.id,
                            'email': shopify_customer.get('email', ''),
                            'first_name': shopify_customer.get('first_name', ''),
                            'last_name': shopify_customer.get('last_name', ''),
                            'phone': shopify_customer.get('phone', ''),
                            'verified_email': shopify_customer.get('verified_email', False),
                            'accepts_marketing': shopify_customer.get('accepts_marketing', False),
                            'orders_count': shopify_customer.get('orders_count', 0),
                            'total_spent': float(shopify_customer.get('total_spent', 0)),
                            'currency': shopify_customer.get('currency', ''),
                            'shopify_tags': shopify_customer.get('tags', ''),
                            'shopify_state': shopify_customer.get('state', 'enabled'),
                            'created_at': parse_shopify_date(shopify_customer.get('created_at')),
                            'updated_at': parse_shopify_date(shopify_customer.get('updated_at')),
                            'default_address_line1': default_address.get('address1', ''),
                            'default_address_line2': default_address.get('address2', ''),
                            'default_city': default_address.get('city', ''),
                            'default_province': default_address.get('province', ''),
                            'default_country': default_address.get('country', ''),
                            'default_zip': default_address.get('zip', ''),
                            'sync_status': 'synced',
                            'last_sync': fields.Datetime.now(),
                        }

                        if existing_mapping:
                            existing_mapping.write(customer_vals)
                            total_updated += 1
                        else:
                            # Create Odoo partner
                            odoo_partner = self._create_odoo_partner(shopify_customer)
                            customer_vals['odoo_partner_id'] = odoo_partner.id if odoo_partner else False
                            self.create(customer_vals)
                            total_created += 1

                        total_processed += 1

                        # Check if we've reached max_records limit
                        if max_records > 0 and total_processed >= max_records:
                            _logger.info("Reached max_records limit of %d during processing", max_records)
                            break

                        # Commit every batch_size records to save progress
                        if (total_created + total_updated) % batch_size == 0:
                            self.env.cr.commit()
                            _logger.info("Progress: %d created, %d updated (committed)", total_created, total_updated)

                    except Exception as e:
                        total_errors += 1
                        _logger.error("Error importing customer %s: %s", shopify_customer.get('email', 'Unknown'), str(e))
                        if total_errors % 50 == 0:  # Log every 50 errors
                            self.env['shopify.log'].create({
                                'name': 'Customer Import Errors',
                                'log_type': 'error',
                                'job_id': job.id,
                                'message': f'Batch errors: {total_errors} errors so far',
                            })
                            self.env.cr.commit()

                # Commit after each page
                self.env.cr.commit()

                # Check if we've reached max_records limit
                if max_records > 0 and total_processed >= max_records:
                    break

                # Check if there's a next page
                if not next_link or batch_count < 250:
                    break

                # Use next page URL for cursor-based pagination
                endpoint = next_link
                params = {}

            # Update job status and last sync time
            job.write({'status': 'done'})
            instance.write({'last_customer_sync': fields.Datetime.now()})

            sync_type = "Incremental" if is_incremental else "Full"
            self.env['shopify.log'].create({
                'name': 'Customer Import Completed',
                'log_type': 'info',
                'job_id': job.id,
                'message': f'{sync_type} import completed: {total_created} created, {total_updated} updated, {total_errors} errors (total fetched: {total_fetched})',
            })
            self.env.cr.commit()

            _logger.info("%s customer import completed: %d created, %d updated, %d errors",
                        sync_type, total_created, total_updated, total_errors)

            return True

        except Exception as e:
            job.write({'status': 'failed', 'error_message': str(e)})
            self.env['shopify.log'].create({
                'name': 'Customer Import Failed',
                'log_type': 'error',
                'job_id': job.id,
                'message': f'Customer import failed: {str(e)}',
            })
            raise UserError(_('Failed to import customers: %s') % str(e))

    def _create_odoo_partner(self, shopify_customer):
        """Create Odoo partner from Shopify customer data"""
        try:
            customer_email = shopify_customer.get('email', '')
            customer_name = f"{shopify_customer.get('first_name', '')} {shopify_customer.get('last_name', '')}".strip()

            # Check if partner already exists by email
            if customer_email:
                existing_partner = self.env['res.partner'].search([('email', '=', customer_email)], limit=1)
                if existing_partner:
                    return existing_partner

            # Get default address
            default_address = shopify_customer.get('default_address', {}) or {}

            # Find country
            country = False
            country_code = default_address.get('country_code', '')
            if country_code:
                country = self.env['res.country'].search([('code', '=', country_code.upper())], limit=1)

            # Find state
            state = False
            province_code = default_address.get('province_code', '')
            if province_code and country:
                state = self.env['res.country.state'].search([
                    ('code', '=', province_code),
                    ('country_id', '=', country.id)
                ], limit=1)

            partner_vals = {
                'name': customer_name or customer_email or 'Shopify Customer',
                'email': customer_email,
                'phone': shopify_customer.get('phone', '') or default_address.get('phone', ''),
                'is_company': False,
                'customer_rank': 1,
                'street': default_address.get('address1', ''),
                'street2': default_address.get('address2', ''),
                'city': default_address.get('city', ''),
                'state_id': state.id if state else False,
                'country_id': country.id if country else False,
                'zip': default_address.get('zip', ''),
            }

            return self.env['res.partner'].create(partner_vals)

        except Exception as e:
            _logger.error("Error creating Odoo partner: %s", str(e))
            return False

    def export_customers_to_shopify(self, instance, customers):
        """Export customers to Shopify"""
        if not instance:
            raise UserError(_('No Shopify instance provided.'))

        job = self.env['shopify.queue.job'].create({
            'name': f'Export Customers ({instance.name})',
            'job_type': 'export_customer',
            'instance_id': instance.id,
            'status': 'in_progress',
        })

        exported_count = 0
        error_count = 0

        for customer_mapping in customers:
            try:
                odoo_partner = customer_mapping.odoo_partner_id
                if not odoo_partner:
                    continue

                customer_data = {
                    'customer': {
                        'first_name': odoo_partner.name.split()[0] if odoo_partner.name else '',
                        'last_name': ' '.join(odoo_partner.name.split()[1:]) if odoo_partner.name and len(odoo_partner.name.split()) > 1 else '',
                        'email': odoo_partner.email or '',
                        'phone': odoo_partner.phone or odoo_partner.mobile or '',
                        'verified_email': True,
                        'addresses': [{
                            'address1': odoo_partner.street or '',
                            'address2': odoo_partner.street2 or '',
                            'city': odoo_partner.city or '',
                            'province': odoo_partner.state_id.name if odoo_partner.state_id else '',
                            'country': odoo_partner.country_id.name if odoo_partner.country_id else '',
                            'zip': odoo_partner.zip or '',
                            'phone': odoo_partner.phone or '',
                        }] if odoo_partner.street else [],
                    }
                }

                if customer_mapping.shopify_customer_id:
                    # Update existing
                    result = instance._shopify_request(
                        f'customers/{customer_mapping.shopify_customer_id}.json',
                        method='PUT',
                        data=customer_data
                    )
                else:
                    # Create new
                    result = instance._shopify_request('customers.json', method='POST', data=customer_data)

                if result and 'customer' in result:
                    customer_mapping.write({
                        'shopify_customer_id': str(result['customer']['id']),
                        'sync_status': 'synced',
                        'last_sync': fields.Datetime.now(),
                    })
                    exported_count += 1

            except Exception as e:
                error_count += 1
                self.env['shopify.log'].create({
                    'name': 'Customer Export Error',
                    'log_type': 'error',
                    'job_id': job.id,
                    'message': f'Error exporting customer: {str(e)}',
                })

        job.write({'status': 'done'})
        self.env['shopify.log'].create({
            'name': 'Customer Export Completed',
            'log_type': 'info',
            'job_id': job.id,
            'message': f'Export completed: {exported_count} exported, {error_count} errors',
        })

        return True

    def action_sync_from_shopify(self):
        """Sync single customer from Shopify"""
        self.ensure_one()
        if not self.shopify_customer_id:
            raise UserError(_('No Shopify customer ID found!'))

        try:
            result = self.instance_id._shopify_request(f'customers/{self.shopify_customer_id}.json')
            if result and 'customer' in result:
                shopify_customer = result['customer']
                default_address = shopify_customer.get('default_address', {}) or {}

                self.write({
                    'email': shopify_customer.get('email', ''),
                    'first_name': shopify_customer.get('first_name', ''),
                    'last_name': shopify_customer.get('last_name', ''),
                    'phone': shopify_customer.get('phone', ''),
                    'verified_email': shopify_customer.get('verified_email', False),
                    'accepts_marketing': shopify_customer.get('accepts_marketing', False),
                    'orders_count': shopify_customer.get('orders_count', 0),
                    'total_spent': float(shopify_customer.get('total_spent', 0)),
                    'shopify_tags': shopify_customer.get('tags', ''),
                    'shopify_state': shopify_customer.get('state', 'enabled'),
                    'default_address_line1': default_address.get('address1', ''),
                    'default_address_line2': default_address.get('address2', ''),
                    'default_city': default_address.get('city', ''),
                    'default_province': default_address.get('province', ''),
                    'default_country': default_address.get('country', ''),
                    'default_zip': default_address.get('zip', ''),
                    'sync_status': 'synced',
                    'last_sync': fields.Datetime.now(),
                })

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Customer Synced'),
                        'message': _('Customer synced from Shopify successfully!'),
                        'type': 'success',
                        'sticky': False,
                    },
                }
        except Exception as e:
            raise UserError(_('Failed to sync customer from Shopify: %s') % str(e))

    @api.model
    def _run_customer_import_cron(self):
        """Cron job to import customers from all active instances"""
        instances = self.env['shopify.instance'].search([
            ('state', '=', 'connected'),
            ('active', '=', True),
            ('auto_sync_customers', '=', True)
        ])
        for instance in instances:
            try:
                self.import_customers_from_shopify(instance)
            except Exception as e:
                _logger.error("Cron customer import error for %s: %s", instance.name, str(e))