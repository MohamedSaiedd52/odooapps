import json
import logging

from odoo import http
from odoo.http import request

from ..models.salla_api import verify_webhook_signature

_logger = logging.getLogger(__name__)


class SallaAuth(http.Controller):

    @http.route('/salla_connector/auth_callback', type='http', auth='user')
    def salla_auth_callback(self, **kw):
        """
        Callback route for Salla OAuth2.
        Salla redirects here with ?code=...&state=...
        """
        code = kw.get('code')
        error = kw.get('error')

        if error:
            return f"Error from Salla: {error}"

        if not code:
            return "No code received from Salla."

        # Exchange code for token
        try:
            request.env['res.config.settings'].salla_exchange_code(code)
            return request.make_response(
                "<html><body style='font-family:Arial;text-align:center;"
                "padding-top:60px;'>"
                "<h2 style='color:#2e7d32;'>&#10004; Connected to Salla</h2>"
                "<p>Your store is now linked. You can close this tab and go "
                "back to <b>Settings &rarr; Salla Connector</b>.</p>"
                "</body></html>",
                headers=[('Content-Type', 'text/html')])
        except Exception as e:
            _logger.exception("Error during Salla Token Exchange")
            return f"Error during token exchange: {str(e)}"

    @http.route('/salla_connector/webhook', type='http', auth='public',
                methods=['POST'], csrf=False)
    def salla_webhook(self, **kw):
        """
        Endpoint for Salla Webhooks (secured with an HMAC signature when a
        webhook secret is configured in Settings).

        Declared as a plain http route on purpose: Salla posts raw JSON, not
        a JSON-RPC envelope, and this works identically on Odoo 17/18/19.
        """
        try:
            raw_body = request.httprequest.get_data()
            secret = request.env['ir.config_parameter'].sudo().get_param(
                'salla_connector.webhook_secret')
            signature = request.httprequest.headers.get('X-Salla-Signature')
            if not verify_webhook_signature(secret, raw_body, signature):
                _logger.warning("Salla webhook rejected: bad signature")
                return request.make_json_response(
                    {'status': 'error', 'message': 'invalid signature'},
                    status=403)
            if not secret:
                _logger.warning(
                    "Salla webhook accepted WITHOUT verification — set a "
                    "Webhook Secret in Settings > Salla Connector.")

            data = json.loads(raw_body or b'{}')

            event = data.get('event')
            payload = data.get('data')

            _logger.info("Salla Webhook Received: %s", event)

            if event == 'product.updated':
                request.env['product.template'].sudo()._import_salla_product(payload)

            elif event in ('order.created', 'order.updated'):
                request.env['sale.order'].sudo()._import_salla_order(payload)

            return request.make_json_response({'status': 'success'})

        except Exception as e:
            _logger.exception("Salla Webhook Error")
            return request.make_json_response(
                {'status': 'error', 'message': str(e)}, status=500)
