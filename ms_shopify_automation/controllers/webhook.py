from odoo import http
from odoo.http import request, route
import logging

from odoo.addons.ms_shopify_automation.models.compat import JSON_ROUTE_TYPE

_logger = logging.getLogger(__name__)


class ShopifyWebhookController(http.Controller):

    def _resolve_instance(self):
        """Find the shopify.instance a webhook belongs to.

        Shopify sends the shop domain in the X-Shopify-Shop-Domain header
        (e.g. mystore.myshopify.com); fall back to the first active instance.
        """
        Instance = request.env['shopify.instance'].sudo()
        shop_domain = request.httprequest.headers.get('X-Shopify-Shop-Domain')
        if shop_domain:
            instance = Instance.search([('shop_url', 'ilike', shop_domain)], limit=1)
            if instance:
                return instance
        return Instance.search([], limit=1)

    def _enqueue_webhook(self, kind, payload):
        """Create a queue job + log entry for an incoming webhook."""
        instance = self._resolve_instance()
        if not instance:
            _logger.warning('Shopify %s webhook received but no instance configured', kind)
            request.env['shopify.log'].sudo().create({
                'name': f'{kind.capitalize()} Webhook (no instance)',
                'log_type': 'warning',
                'message': str(payload),
            })
            return {'status': 'error', 'message': 'No Shopify instance configured'}
        job = request.env['shopify.queue.job'].sudo().create({
            'name': f'Webhook {kind.capitalize()} Import',
            'job_type': f'import_{kind}',
            'instance_id': instance.id,
            'status': 'pending',
        })
        request.env['shopify.log'].sudo().create({
            'name': f'{kind.capitalize()} Webhook',
            'log_type': 'info',
            'job_id': job.id,
            'message': str(payload),
        })
        return {'status': 'ok', 'job_id': job.id}

    @route(['/shopify/webhook/product'], type=JSON_ROUTE_TYPE, auth='public', csrf=False, methods=['POST'])
    def shopify_webhook_product(self, **post):
        _logger.info('Received Shopify Product Webhook: %s', post)
        return self._enqueue_webhook('product', post)

    @route(['/shopify/webhook/order'], type=JSON_ROUTE_TYPE, auth='public', csrf=False, methods=['POST'])
    def shopify_webhook_order(self, **post):
        _logger.info('Received Shopify Order Webhook: %s', post)
        return self._enqueue_webhook('order', post)

    @route(['/shopify/webhook/customer'], type=JSON_ROUTE_TYPE, auth='public', csrf=False, methods=['POST'])
    def shopify_webhook_customer(self, **post):
        _logger.info('Received Shopify Customer Webhook: %s', post)
        return self._enqueue_webhook('customer', post)
