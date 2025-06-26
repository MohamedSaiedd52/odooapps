{
    "name": "Import Internal Transfer of Materials from Excel",
    "summary": "Import internal stock transfers from Excel (.xlsx) files easily into Odoo.",
    "description": """
Import Internal Transfers from Excel
====================================

This module allows users to **import internal stock transfers** (picking type = internal) from Excel `.xlsx` files directly into Odoo.

✔ Supports Excel upload via wizard  
✔ Uses `openpyxl` to parse data  
✔ Prevents duplication and validates records  
✔ Works with multiple locations and products

Ideal for inventory managers and warehouse users who want to save time during stock operations.

""",
    "category": "Extra Tools",
    "version": "1.0",
    "author": "Mohamed Saied",
    "maintainer": "Mohamed Saied <mohamedsaiedd53@gmail.com>",
    "license": "LGPL-3",
    "price": 5.0,
    "currency": "USD",
    "depends": ["stock"],
    "external_dependencies": {
        "python": ["openpyxl"]
    },
    "data": [
        "security/import_internal_transfer_security.xml",
        "security/ir.model.access.csv",
        "wizard/import_internal_transfer_wizard.xml",
        "wizard/message_wizard.xml",
        "views/stock.xml"
    ],
    "images": ["static/description/bannar.png"],
    "installable": True,
    "application": True,
    "auto_install": False
}
