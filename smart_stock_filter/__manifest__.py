{
    "name": "Smart Stock Filter",
    "category": "Inventory",
    "summary": "Smart product filtering in stock picking based on location availability",
    "description": """
Adds intelligent product filtering to stock pickings based on the availability of products in the selected source location.

Features:
- Dynamically computes available locations per product.
- Filters selectable products in pickings to only those available at source.
- Enhances accuracy and prevents stock errors.
    """,
    "author": "Mohamed Saied",
    "website": "mailto:mohamedsaiedd53@gmail.com",
    "license": "LGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "stock",
    ],
    "data": [
        "views/stock_picking_view.xml",
    ],
    "images": [
"static/description/banner.gif",
"static/description/icon.png",

],
}
