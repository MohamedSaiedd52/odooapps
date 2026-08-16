{
    'name': 'Manufacturing Variance Report',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Standard vs Actual variance analysis for Manufacturing Orders',
    'depends': ['mrp'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/mrp_variance_wizard.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
    'price': 40.0,
    'currency': 'USD',
}
