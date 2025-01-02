{
    'name': "POS Prevent Negative Stock",
    'summary': "Enhance your POS system by preventing sales of products with insufficient stock levels.",
    'description': """
        This module adds a restriction to the Point of Sale (POS) system in Odoo, ensuring that sales cannot proceed if the stock level for any product is below zero. 
        It enhances stock management accuracy and prevents errors due to negative stock quantities.
        
        Features:
        - Restrict sales for products with insufficient stock.
        - Ensure inventory accuracy and integrity.
        - Includes robust security rules to protect stock data.

        Ideal for businesses that require strict inventory controls and accurate sales data.
    """,
    'author': "Mohamed Saied",
    'category': 'Point of Sale',
    'version': '17.0.0.1.0',
    'depends': ['point_of_sale'],
    'price': 25.00,
    'currency': 'USD',
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
    ],
    'assets': {
        "point_of_sale._assets_pos": [
            "pos_prevent_negative_stock/static/src/js/models.js",
        ],
    },
    'license': 'LGPL-3',
    'application': True,
}
