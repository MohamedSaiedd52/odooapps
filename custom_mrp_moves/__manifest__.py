# -*- coding: utf-8 -*-
{
    'name': 'BOM Component Source Location',

    'summary': 'Consume manufacturing components from a specific stock location per BOM line - control raw material sourcing in MRP.',

    'description': """
Adds a Source Location on BOM lines and Manufacturing Order components.
When a Manufacturing Order is created or its BOM is changed, each raw material
move takes its source location from the matching BOM line instead of the
default picking type location.
    """,

    'author': 'Mohamed Saied',
    'website': "https://www.yourcompany.com",

    'category': 'Manufacturing',
    'version': '17.0.1.0.0',
    'license': 'LGPL-3',

    # any module necessary for this one to work correctly
    'depends': ['mrp', 'stock'],

    # always loaded
    'data': [
        'views/mrp_production.xml',
        'views/mrp_bom_line.xml',
    ],
    'installable': True,
    'application': False,
    'price': 40.0,
    'currency': 'USD',
    'images': ['static/description/banner.gif'],
}
