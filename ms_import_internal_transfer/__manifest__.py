{
    "name": "Import Internal Transfer of Materials from Excel file MS",
    "category": "Inventory",
    "summary": "Import internal stock transfers from Excel files (.xlsx)",
    "author": "Mohamed Saied",
    "license": "LGPL-3",
    "price": 5.0,
    "currency": "USD",
    "depends": ["stock"],
    "data": [
        "security/import_internal_transfer_security.xml",
        "security/ir.model.access.csv",
        "wizard/import_internal_transfer_wizard.xml",
        "wizard/message_wizard.xml",
        "views/stock.xml"
    ],
    "external_dependencies": {
        "python": ["openpyxl"]
    },
    "installable": True,
    "application": True,
    "auto_install": False,
    "maintainer": "Mohamed Saied",
    "images": ["static/description/bannar.png"]

}
