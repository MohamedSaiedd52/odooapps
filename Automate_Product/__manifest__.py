{
    'name': 'Auto-Set PO Line Products',
    'version': '17.0',
    'category': 'Purchases',
    'summary': 'Custom Module to Manage Vendor Products in Purchase Orders',
    'depends': ['purchase', 'product'],
    'data': [
        'views/purchase_order_view.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
    'author': 'Mohamed Saied',
    'icon': 'automate.svg', 
}
