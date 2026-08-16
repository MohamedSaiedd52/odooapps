# -*- coding: utf-8 -*-
{
    'name': 'Biometric Device Attendance Sync',
    'version': '19.0.1.0.0',
    'summary': 'Sync employee attendance from fingerprint & biometric machines (ZKTeco) straight to Odoo Attendance in real time.',
    'category': 'Human Resources/Attendances',
    'author': 'Mohamed Saied',
    'depends': ['base', 'hr', 'hr_attendance'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_employee_view.xml',
        'views/biometric_log_view.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'price': 70.0,
    'currency': 'USD',
    'images': ['static/description/banner.gif'],
}
