# -*- coding: utf-8 -*-
{
    'name': 'ZKTeco Biometric Attendance Sync | ZK Fingerprint Attendance Machine | Biometric Device Integration',
    'version': '18.0.1.0.0',
    'summary': 'ZKTeco / ZK biometric fingerprint attendance machine integration: sync punches from the device to Odoo Attendance in real time.',
    'category': 'Human Resources/Attendances',
    'author': 'Mohamed Saied',
    'support': 'MohamedSaiedd53@gmail.com',
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
