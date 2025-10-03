# -*- coding: utf-8 -*-
{
    'name': "MS Biotime Integration",
    'category': 'Hr',
    'author':'MOHAMED SAIED',
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
}
