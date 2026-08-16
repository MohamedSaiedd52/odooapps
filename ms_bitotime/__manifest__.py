{
    'name': 'ZKTeco BioTime Attendance Sync | ZK BioTime | Biometric Attendance Machine Integration',
    'version': '18.0.3.0.0',
    'category': 'Human Resources/Attendances',
    'author': 'Mohamed Saied',
    'depends': ['base', 'hr', 'hr_attendance', 'mail', 'base_sparse_field'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/groups.xml',
        'security/queue_job_security.xml',
        'security/ir.model.access.csv',
        'views/queue_job_views.xml',
        'views/queue_job_channel_views.xml',
        'views/queue_job_function_views.xml',
        'views/biotime.xml',
        'views/queue_job_menus.xml',
        'views/biotime_wizards.xml',
        'data/queue_data.xml',
        'data/queue_job_data.xml',
        'data/cron.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'post_load': 'post_load',
    'images': ['static/description/banner.gif'],
    'license': 'LGPL-3',
    'summary': 'ZK BioTime / ZKTeco BioTime attendance integration: sync fingerprint, face recognition & RFID devices with Odoo HR Attendance.',
    'description': """
         Odoo ZKTeco Biotime Integration
         ===================================
         - Full integration with ZKTeco Biotime & ZK devices
         - Supports fingerprint, RFID, face recognition
         - Automatic attendance & payroll sync
     """,
    'installable': True,
    'application': True,
    'price': 80,
    'currency': 'USD',
}
