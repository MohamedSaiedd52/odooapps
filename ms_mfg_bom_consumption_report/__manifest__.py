{
    'name': 'BOM vs Actual Consumption Report',
    'version': '18.0.1.0.1',
    'category': 'Manufacturing',
    'summary': 'Compare planned BOM quantities with actual material consumption per Manufacturing Order - waste & overuse analysis.',
    'author': 'Mohamed Saied',

    'license': 'LGPL-3',
    'depends': ['mrp', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/bom_consumption_wizard_view.xml',
        'report/bom_consumption_report_template.xml',
        'report/bom_consumption_report_action.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'price': 35.0,
    'currency': 'USD',
    'images': ['static/description/banner.gif'],
}
