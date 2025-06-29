{
    "name": "Filter Products by Stock Location",
    "category": "Inventory",
    "summary": "Filter products in stock picking lines based on stock locations",
    "description": """
This module filters products in stock picking lines based on available stock locations.

Features:
- Computes `location_ids` for products where stock exists.
- Filters products in picking lines to match the source location.
- Prevents selection of unavailable products for the picking location.
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
    "images": ["static/description/thumbnail.png"],
}
