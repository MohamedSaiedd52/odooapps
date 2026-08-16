# -*- coding: utf-8 -*-
{
    "name": 'Approval Matrix & Multi-Level Approval Workflow',
    "summary": 'Amount-based multi-level approval workflow for Sales Orders, Purchase Orders, Invoices, Payments & Stock Transfers.',
    "description": "Approval matrix with multi-level amount-based rules, escalation reminders, delegation (vacation mode) and a full audit trail. Blocks confirmation of Sales/Purchase Orders, posting of Invoices/Bills and validation of Stock Transfers until approved.",
    "version": "17.0.1.0.0",
    "category": 'Extra Tools',
    "author": 'Mohamed Saied',
    "license": "OPL-1",
    "price": 78.16,
    "currency": "USD",
    "depends": ["sale_management", "purchase", "stock", "account", "mail"],
    "data": [
        "security/approval_security.xml",
        "security/ir.model.access.csv",
        "data/approval_data.xml",
        "views/approval_views.xml",
        "views/document_views.xml",
    ],
    "demo": ["demo/approval_demo.xml"],
    'images': ['static/description/banner.gif'],
    "installable": True,
    "application": True,
}
