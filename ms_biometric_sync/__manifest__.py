# -*- coding: utf-8 -*-
{
    'name': 'MS Biometric Sync',
    'version': '19.0.1.0.0',
    'summary': 'Sync attendance from local biometric devices via API',
    'category': 'Human Resources/Attendance',
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
