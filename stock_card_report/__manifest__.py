{
    "name": "Stock Card Report 18",
    "summary": "Easily generate detailed stock card reports directly from Inventory Reporting.",
    "category": "Inventory/Warehouse",
    "author": "Mohamed SAied",
    "license": "LGPL-3",
    "depends": ["base", "web", "stock", "report_xlsx"],
    "data": [
        "security/ir.model.access.csv",
        "data/paper_format.xml",
        "data/report_data.xml",
        "reports/stock_card_report.xml",
        "wizard/stock_card_report_wizard_view.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "stock_card_report/static/src/css/**/*",
            "stock_card_report/static/src/js/**/*",
        ]
    },
    'price': "15",
    'currency': 'USD',
    "images": ["static/description/thumbnail.png"],
    "development_status": "Mature",
    "installable": True,
}
