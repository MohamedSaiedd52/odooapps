# -*- coding: utf-8 -*-
import socket

import requests
from requests.models import Response
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

def get_server_ip(domain):
    """
    Get Ip address from domain name
    :param domain: biotime server name
    :return: ip
    """
    ip = socket.gethostbyname(domain)
    return ip


def get_general_api_token_auth(url, username, password):
    """
    Get General API Token for authentication
    :param url: url for server and port
    :param username: biotime server username
    :param password: biotime server password
    :return: response
    """
    url = url + "/api-token-auth/"

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "username": username,
        "password": password
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
    except:
        res = Response()
        _logger.info(
            '****************************************************\n RES  %s **************************************************************\n',
            res)
        res.code = "connectionError"
        res.error_type = "connectionError"
        res.status_code = 400
        res._content = b'Connection Error: Check server ip or port'
        return res
    return response


def get_transactions(url, token, last_transaction, device_sn=None):
    device_sn = "&terminal_sn=" + str(device_sn) if device_sn else ""
    url = url + "/iclock/api/transactions/?page_size=1000&start_time=" + \
        str(last_transaction) + device_sn
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Token " + str(token)
    }
    try:
        response = requests.get(url, headers=headers)
    except:
        res = Response()
        res.code = "connectionError"
        res.error_type = "connectionError"
        res.status_code = 400
        res._content = b'Connection Error: Check server ip or port'
        return res
    return response


def get_devices(url, token):
    url = url + "/iclock/api/terminals/?page_size=100"

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Token " + str(token)
    }
    try:
        response = requests.get(url, headers=headers)
    except:
        res = Response()
        res.code = "connectionError"
        res.error_type = "connectionError"
        res.status_code = 400
        res._content = b'Connection Error: Check server ip or port'
        return res
    return response


def get_next_page(url, token):
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Token " + str(token)
    }

    try:
        response = requests.get(url, headers=headers)
    except:
        res = Response()
        res.code = "connectionError"
        res.error_type = "connectionError"
        res.status_code = 400
        res._content = b'Connection Error: Check server ip or port'
        return res
    return response


def check_server_connection(url):
    try:
        requests.head(url, timeout=10)
    except Exception as e:
        print(e)
        return False
    return True


def seconds_to_minutes(seconds):
    return abs(seconds) / 60

def seconds_to_hours(seconds):
    return abs(seconds) / 3600


def check_duplicated_punches(punch1, punch2):
    """
    Check if the two punches are too close to each other (less than 30 minutes)
    """
    time_diff = abs((punch1 - punch2).total_seconds())
    return time_diff <= 30 * 60  # 30 minutes


def check_over_check_out(punch1, punch2):
    """
    Check if time between punches is too long (over 10 hours)
    """
    time_diff = abs((punch1 - punch2).total_seconds())
    return time_diff > 10 * 3600  # 10 hours


def check_is_invalid_check_out(punch1, punch2):
    """
    Combines duplicate punch and long gap to mark invalid checkout
    """
    return check_duplicated_punches(punch1, punch2) and check_over_check_out(punch1, punch2)


def is_valid_check_out(punch, check_in):
    """
    Consider a checkout valid if it's within 9 hours of check-in
    """
    if not punch or not check_in:
        return False
    time_diff = (punch - check_in).total_seconds()
    return 0 < time_diff <= 9 * 3600


def is_same_day(punch, check):
    """
    Checks if two datetimes are on the same calendar day
    """
    if not punch or not check:
        return False
    return punch.date() == check.date()


def is_valid_overtime(punch, check_out):
    time_diff = punch - check_out
    return seconds_to_hours(time_diff.seconds) <= 2


def is_old_transaction(punch, last_attendance):
    """
    Check if the punch is before the last recorded attendance day
    """
    return punch.date() < last_attendance.date()

def max_time(punch):
    return datetime.combine(punch.date(), datetime.max.time())


def min_time(punch):
    return datetime.combine(punch.date(), datetime.min.time())
