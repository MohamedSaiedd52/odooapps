# -*- coding: utf-8 -*-
{
    'name': "ZK Biotime",
    'category': 'Hr',
    'author':'Mohamed Saied',
    'depends': ['base', 'hr', 'hr_attendance','mail'],
    'external_dependencies':
        {'python':
             [ 'pyzk','openpyxl']
         },
    'data': [
        'security/ir.model.access.csv',
        'views/biotime.xml',
        'data/cron.xml',
        'views/dashboard.xml',
    ],
    "images": [
        'static/description/banner.gif',
        'static/description/icon.png',
    ],
    'assets': {
        'web.assets_backend': [
            'ms_bitotime/static/src/js/biotime_dashboard.js',
            'ms_bitotime/static/src/xml/biotime_dashboard.xml',
            'https://cdn.jsdelivr.net/npm/chart.js',

        ],
    },
    'license': 'LGPL-3',
    'price': 100.0,
    'currency': 'USD',
    'summary': "Sync ZKTeco Biotime (ZK devices, fingerprint, face recognition, RFID) with Odoo Attendance & HR",
    'description': """
         Odoo ZKTeco Biotime Integration
         ===================================
         - Full integration with ZKTeco Biotime & ZK devices
         - Supports fingerprint, RFID, face recognition
         - Models supported: iClock, uFace, MB Series, K Series, UA Series, F Series, LX Series, SpeedFace, ProFace X, SilkBio, ZPad
         - Automatic attendance & payroll sync
     """,
}
