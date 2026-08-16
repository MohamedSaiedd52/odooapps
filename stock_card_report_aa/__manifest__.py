{
    "name": "Stock Card Report",
    "summary": "Stock Card report (PDF, XLSX and HTML view) powered by openpyxl - fully standalone, no report_xlsx dependency.",
    "category": "Inventory/Warehouse",
    "author": 'Mohamed Saied',
    "license": "LGPL-3",
    "version": "19.0.1.0.0",
    "depends": ["base", "web", "stock"],
    "external_dependencies": {"python": ["openpyxl"]},
    "data": [
        "security/group.xml",
        "security/ir.model.access.csv",
        "data/paper_format.xml",
        "data/report_data.xml",
        "reports/stock_card_report_aa.xml",
        "wizard/stock_card_report_wizard_view.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "stock_card_report_aa/static/src/css/**/*",
            "stock_card_report_aa/static/src/js/**/*",
        ]
    },
    "price": "25",
    "currency": "USD",
    'images': ['static/description/banner.gif'],
    "development_status": "Mature",
    "installable": True,
    "application": True,
}
