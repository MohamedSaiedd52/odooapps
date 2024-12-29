
{
   'name': 'My Auto Backup Database',
    'version': '1.0',
    'category': 'Tools',
    'summary': 'Manage and schedule database backups for Odoo instances',
    'description': """
    This module helps you to configure, schedule, and manage database backups for Odoo. 
    It includes features for backup generation, retention management, and report generation. 
    The module supports local storage and can be extended to cloud storage. 
    Features include:
    - Configure backups for databases.
    - Automate backups with a scheduler.
    - Retain backups based on a defined retention policy.
    - Generate detailed reports about backup status.
    - Track backup progress in real-time.
    """,
    'depends':['base'],
    'author': 'Mohamed Saied',
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/db_backup.xml',
    ],
    'images': ['static/description/banner.jpg'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True,
}
