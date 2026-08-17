{
    'name': 'Manufacturing Variance Report',
    'version': '19.0.1.0.0',
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
    'support': 'MohamedSaiedd53@gmail.com',
    'images': ['static/description/banner.gif'],
}
