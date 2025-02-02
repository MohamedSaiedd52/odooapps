
{
    'name': 'Module Path Display',
    'version': '1.0',
    'category': 'Tools',
    'summary': 'Display module path in the ir.module.module form',
    'author': 'Mohamed Saied',
    'depends': ['base', 'web'],
    'data': [
        'views/ir_module_module_views.xml',
    ],
    'images': ['static/description/banner.jpg'],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
