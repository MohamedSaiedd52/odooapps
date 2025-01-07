{
    "name": " report aaa",
    
    "author": "Mohamed Saied",
    "category": "Reporting",
    "development_status": "Mature",
    "license": "LGPL-3",
    "external_dependencies": {"python": ["xlsxwriter", "xlrd"]},
    "depends": ["base", "web"],
    "demo": ["demo/report.xml"],
    "installable": True,
    "assets": {
        "web.assets_backend": [
            "report_xlsx_aa/static/src/js/report/action_manager_report.esm.js",
        ],
    },
    'application': False,  

}
