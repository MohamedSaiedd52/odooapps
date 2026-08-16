{
    'name': 'Manufacturing Variance Report',
    'version': '18.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Standard vs actual cost & material variance analysis per Manufacturing Order - production cost control report.',
    'depends': ['mrp'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/mrp_variance_wizard.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
    'price': 40.0,
    'currency': 'USD',
    'author': 'Mohamed Saied',
    'images': ['static/description/banner.gif'],
}
