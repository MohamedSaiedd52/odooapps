# -*- coding: utf-8 -*-
{
    'name': 'Website Cash on Delivery COD | eCommerce COD Payment | COD Fee & Zip Rules',
    'summary': 'Cash on Delivery (COD) payment option on the website shop: minimum order amount, COD fee (fixed + percent), zip code & country restrictions, COD order flag and collection sheet report.',
    'description': """
Website Cash on Delivery (COD)
==============================
- Adds a Cash on Delivery payment option to the eCommerce checkout.
- Minimum order amount rule (maximum amount uses the provider's native field).
- Optional COD fee: fixed amount and/or percentage, added to the order automatically.
- Restrict availability by shipping zip codes (comma separated list) and countries.
- Orders paid with COD are flagged and searchable.
- Print a COD Collection Sheet for the driver with amounts to collect.
""",
    'category': 'eCommerce',
    'version': '17.0.1.0.0',
    'author': 'Mohamed Saied',
    'support': 'MohamedSaiedd53@gmail.com',
    'license': 'OPL-1',
    'price': 35.0,
    'currency': 'USD',
    'depends': ['website_sale', 'payment_custom', 'delivery'],
    'data': [
        'data/payment_method_data.xml',
        'data/product_data.xml',
        'data/payment_provider_data.xml',
        'views/payment_provider_views.xml',
        'views/sale_order_views.xml',
        'report/cod_collection_report.xml',
    ],
    'images': ['static/description/banner.gif'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
