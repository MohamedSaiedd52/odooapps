{
    'name': 'Auto-Set PO Line Products',
     'version': '17.0.1.0.0',
    'category': 'Purchases',
  'summary': 'Automatically create purchase orders and fetch related products when selecting a vendor.',
    'description': """
    Auto Purchase Addon
    ===================
    This module automates the creation of purchase orders and fetches all related products when a vendor is selected.
    
    Features:
    - Automatically create purchase orders based on stock levels.
    - Fetch and add all related products to the purchase order when a vendor is selected.
    - Configurable stock thresholds.
    - Easy integration with existing purchase workflows.
    """,
    'depends': ['purchase', 'product'],
    'data': [
        'views/purchase_order_view.xml',
    ],

    'installable': True,
    'application': False,
    'license': 'LGPL-3',
    'author': 'Mohamed Saied',
    'images': ['static/description/icon.png']
}
