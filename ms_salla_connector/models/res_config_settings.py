from odoo import fields, models, api
from odoo.exceptions import UserError
import requests
import logging
import werkzeug.urls

_logger = logging.getLogger(__name__)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    salla_client_id = fields.Char(string='Client ID', config_parameter='ms_salla_connector.client_id')
    salla_client_secret = fields.Char(string='Client Secret', config_parameter='ms_salla_connector.client_secret')
    salla_access_token = fields.Char(string='Access Token', config_parameter='ms_salla_connector.access_token', readonly=True)
    salla_refresh_token = fields.Char(string='Refresh Token', config_parameter='ms_salla_connector.refresh_token', readonly=True)
    salla_webhook_secret = fields.Char(
        string='Webhook Secret',
        config_parameter='ms_salla_connector.webhook_secret',
        help="Secret used to verify the signature of incoming Salla "
             "webhooks. Leave empty to accept webhooks without verification "
             "(not recommended).")
    
    # Constants
    AUTH_URL = "https://accounts.salla.sa/oauth2/auth"
    TOKEN_URL = "https://accounts.salla.sa/oauth2/token"

    def action_salla_connect(self):
        self.ensure_one()
        client_id = self.env['ir.config_parameter'].sudo().get_param('ms_salla_connector.client_id')
        if not client_id:
            raise UserError("Please save the Client ID first.")
            
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        redirect_uri = werkzeug.urls.url_join(base_url, '/ms_salla_connector/auth_callback')
        
        params = {
            'client_id': client_id,
            'response_type': 'code',
            'redirect_uri': redirect_uri,
            'scope': 'offline_access', # Ensure we get a refresh token
            # 'state': 'random_string' # TODO: Implement state for security
        }
        
        auth_url = f"{self.AUTH_URL}?{werkzeug.urls.url_encode(params)}"
        
        return {
            'type': 'ir.actions.act_url',
            'url': auth_url,
            'target': 'self',
        }

    @api.model
    def salla_exchange_code(self, code):
        client_id = self.env['ir.config_parameter'].sudo().get_param('ms_salla_connector.client_id')
        client_secret = self.env['ir.config_parameter'].sudo().get_param('ms_salla_connector.client_secret')
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        redirect_uri = werkzeug.urls.url_join(base_url, '/ms_salla_connector/auth_callback')

        payload = {
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
            'scope': 'offline_access',
        }
        
        try:
            response = requests.post(self.TOKEN_URL, data=payload)
            response.raise_for_status()
            data = response.json()
            
            access_token = data.get('access_token')
            refresh_token = data.get('refresh_token')
            expires_in = data.get('expires_in')
            
            if access_token:
                self.env['ir.config_parameter'].sudo().set_param('ms_salla_connector.access_token', access_token)
            if refresh_token:
                self.env['ir.config_parameter'].sudo().set_param('ms_salla_connector.refresh_token', refresh_token)
                
            _logger.info("Salla Token Exchange Successful: %s", data)
            
        except Exception as e:
            _logger.error("Failed to exchange code for token: %s", str(e))
            if response and response.content:
                 _logger.error("Salla Response content: %s", response.content)
            raise UserError(f"Failed to connect to Salla: {str(e)}")

    def action_salla_test_connection(self):
        # We can implement a simple test here
        # For now, let's just use the SallaAPI helper
        try:
            from .salla_api import SallaAPI
            api = SallaAPI(self.env)
            # Fetch products (page 1) as a test
            result = api.get_products(page=1)
            
            if 'error' in result:
                 return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Connection Failed',
                        'message': f"Error: {result['error']}",
                        'type': 'danger',
                        'sticky': False,
                    }
                }
            else:
                 return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Connection Successful',
                        'message': f"Successfully fetched {len(result.get('data', []))} products.",
                        'type': 'success',
                        'sticky': False,
                    }
                }

        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Test Failed',
                    'message': str(e),
                    'type': 'danger',
                    'sticky': False,
                }
            }
