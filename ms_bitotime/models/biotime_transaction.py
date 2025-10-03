# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from datetime import datetime
import requests
import pytz
import json
import logging

_logger = logging.getLogger(__name__)


class BiotimeTransaction(models.Model):
    _name = "biotime.transaction"
    _description = "Biotime Transaction"
    _order = "punch_time desc"

    transaction_id = fields.Integer("Transaction ID", required=True, index=True)
    employee_id = fields.Many2one("hr.employee", string="Employee")
    department = fields.Char("Department")
    punch_time = fields.Datetime("Punch Time", required=True)
    punch_state = fields.Char("Punch State")
    punch_state_display = fields.Char("Punch State Display")
    device_id = fields.Many2one("biotime.terminal", string="Device")
    server_id = fields.Many2one("biotime.config", string="Server", required=True)
    is_transferred = fields.Boolean("Is Transferred", default=False)


class BioTimeTransactionLog(models.Model):
    _name = 'biotime.transaction.log'
    _description = 'Unmatched BioTime Transactions'

    transaction_id = fields.Char("Transaction ID")
    emp_code = fields.Char("Employee Code")
    emp_name = fields.Char("Employee Name")
    department = fields.Char("Department")
    punch_time = fields.Datetime("Punch Time")
    punch_state = fields.Char("Punch State")
    punch_state_display = fields.Char("Punch State Display")
    device_id = fields.Many2one('biotime.terminal', "Device")
    server_id = fields.Many2one('biotime.config', "Server")
    note = fields.Text("Note")