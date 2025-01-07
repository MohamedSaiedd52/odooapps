{
    "name": "Stock Card Report 18",
    "summary": "Easily generate detailed stock card reports directly from Inventory Reporting.",
    "category": "Inventory/Warehouse",
    "author": "Mohamed Saied",
    "license": "LGPL-3",
    "depends": ["base", "web", "stock", "report_xlsx_aa"],
    "data": [
        "security/ir.model.access.csv",
        "data/paper_format.xml",
        "data/report_data.xml",
        "reports/stock_card_report_aa.xml",
        "wizard/stock_card_report_aa_wizard_view.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "stock_card_report_aa/static/src/css/**/*",
            "stock_card_report_aa/static/src/js/**/*",
        ]
    },
    'price': "15",
    'currency': 'USD',
    "images": ["static/description/thumbnail.png"],
    "development_status": "Mature",
    "installable": True,
}
