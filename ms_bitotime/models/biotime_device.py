# -*- coding: utf-8 -*-
import logging
import requests
from datetime import datetime, timedelta
from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class BioTimeTerminal(models.Model):
    _name = 'biotime.terminal'
    _description = "Biotime Terminal"

    name = fields.Char(string="Name")
    terminal_id = fields.Char(string="Terminal ID")
    terminal_sn = fields.Char(string="Terminal SN")
    ip_address = fields.Char(string="IP Address")
    alias = fields.Char(string="Alias")
    terminal_tz = fields.Char(string="Terminal TZ")
    biotime_id = fields.Many2one('biotime.config', string="Biotime")
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company.id)

    def action_get_transactions(self, page=1, from_date=None, to_date=None):
        """Fetch transactions from BioTime device"""
        for rec in self:
            # ضبط التواريخ الافتراضية
            if not from_date:
                from_date = datetime.now().replace(hour=0, minute=0, second=0)
            if not to_date:
                to_date = datetime.now().replace(hour=23, minute=59, second=59)

            # تحويل إلى الصيغة المطلوبة للـ URL
            start_time = from_date.strftime("%Y-%m-%d %H:%M:%S")
            end_time = to_date.strftime("%Y-%m-%d %H:%M:%S")

            url = (
                f"{rec.biotime_id.server_url}/iclock/api/transactions/"
                f"?page={page}&page_size=1000000&terminal_sn={rec.terminal_sn}"
                f"&start_time={start_time}&end_time={end_time}"
            )
            _logger.info("Fetching transactions from %s to %s for terminal %s", start_time, end_time, rec.terminal_sn)

            # توليد التوكن
            token = rec.biotime_id.generate_access_token()
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Token {token}'
            }

            # طلب البيانات
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                _logger.error("Failed to fetch transactions: %s", str(e))
                raise ValidationError(f"Failed to fetch transactions: {str(e)}")

            if "data" not in data:
                _logger.warning("No transaction data returned: %s", data)
                return {}

            return data
