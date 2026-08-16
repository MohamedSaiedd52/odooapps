import hashlib
import hmac
import logging

import requests

_logger = logging.getLogger(__name__)


def verify_webhook_signature(secret, raw_body, signature):
    """Check a Salla webhook HMAC-SHA256 signature against the raw body."""
    if not secret:
        return True  # verification disabled
    if not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

class SallaAPI:
    """Helper class to interact with Salla API"""

    def __init__(self, env):
        self.env = env
        self.base_url = "https://api.salla.dev/admin/v2"
        self.token_url = "https://accounts.salla.sa/oauth2/token"
        
        self.access_token = self.env['ir.config_parameter'].sudo().get_param('ms_salla_connector.access_token')
        
    def _get_headers(self):
        # Check if we should refresh? (Simplified for now, assume access_token is valid or handle 401)
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
    def refresh_access_token(self):
        refresh_token = self.env['ir.config_parameter'].sudo().get_param('ms_salla_connector.refresh_token')
        client_id = self.env['ir.config_parameter'].sudo().get_param('ms_salla_connector.client_id')
        client_secret = self.env['ir.config_parameter'].sudo().get_param('ms_salla_connector.client_secret')
        
        if not refresh_token:
            raise Exception("No refresh token available.")
            
        payload = {
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
        }
        
        try:
            response = requests.post(self.token_url, data=payload)
            response.raise_for_status()
            data = response.json()
            
            new_access_token = data.get('access_token')
            new_refresh_token = data.get('refresh_token')
            
            if new_access_token:
                self.env['ir.config_parameter'].sudo().set_param('ms_salla_connector.access_token', new_access_token)
                self.access_token = new_access_token
            if new_refresh_token:
                self.env['ir.config_parameter'].sudo().set_param('ms_salla_connector.refresh_token', new_refresh_token)
                
            return True
        except Exception as e:
            _logger.error(f"Failed to refresh token: {e}")
            return False

    def _request(self, method, endpoint, **kwargs):
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        response = None

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30, **kwargs)
            elif method == 'POST':
                response = requests.post(url, headers=headers, timeout=30, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status_code == 401:
                # Token expired, try to refresh
                _logger.info("Salla Token Expired. Attempting refresh...")
                if self.refresh_access_token():
                    # Retry request with new token
                    headers = self._get_headers()
                    if method == 'GET':
                        response = requests.get(url, headers=headers, **kwargs)
                    elif method == 'POST':
                        response = requests.post(url, headers=headers, **kwargs)
                else:
                    return {'error': 'Token expired and refresh failed.'}

            response.raise_for_status()
            return response.json()
        except Exception as e:
            _logger.error(f"Salla API Error ({endpoint}): {e}")
            try:
                error_content = response.json() \
                    if response is not None and response.content else str(e)
            except Exception:
                error_content = str(e)
            return {'data': [], 'error': error_content}

    def get_products(self, page=1):
        return self._request('GET', f"/products?page={page}")

    def get_orders(self, page=1):
        return self._request('GET', f"/orders?page={page}")
