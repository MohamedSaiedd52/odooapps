# MS Shopify Automation - Development Notes & Roadmap

> **Last Updated:** 2025-12-10
> **Module:** `ms_shopify_automation`
> **Odoo Version:** 18

---

## Table of Contents
1. [Overview](#overview)
2. [Completed Tasks](#completed-tasks)
3. [Current Issues & Limitations](#current-issues--limitations)
4. [Next Steps](#next-steps)
5. [Technical Reference](#technical-reference)
6. [File Structure](#file-structure)

---

## Overview

### Module Description
MS Shopify Automation (previously "Syncify") is an Odoo 18 module for Shopify store integration with:
- Product, Order, Customer sync
- Automation Dashboard
- Advanced Analytics Dashboard
- Queue Job Management
- Webhook Support

### Key Components
| Component | Description |
|-----------|-------------|
| `shopify.instance` | Shopify store connection settings |
| `shopify.order` | Synced orders from Shopify |
| `shopify.customer` | Synced customers from Shopify |
| `shopify.product` | Synced products from Shopify |
| `shopify.analytics` | Advanced analytics & reporting |
| `shopify.queue.job` | Background job queue |
| `shopify.log` | System logs |

---

## Completed Tasks

### 1. Dashboard Refresh Issue (Fixed)
**Problem:** Dashboard redirected to instance view on page refresh

**Solution:**
- Changed from `ir.actions.server` to `ir.actions.client`
- Added `path` attribute for stable URL (`/odoo/shopify-dashboard`)
- Created OWL component with proper state management

**Files Modified:**
- `views/dashboard_view.xml` - Client action with path
- `views/menu.xml` - Updated to use client action
- `static/src/js/dashboard.js` - New OWL component
- `static/src/xml/dashboard_template.xml` - Component template

### 2. Dashboard CSS/Styling (Fixed)
**Problems Fixed:**
- KPI section title color (white text invisible)
- Status bar colors (white on white)
- Content overflow cutting off sections
- Chart containers styling

**Files Modified:**
- `static/src/css/dashboard.css`

### 3. Queue Jobs & Error Counts (Fixed)
**Added to Dashboard:**
- `queue_job_count` - Total queue jobs for instance
- `error_count` - Error logs in last 7 days

**Files Modified:**
- `models/shopify_instance.py` - `get_dashboard_data()` method

### 4. Advanced Analytics Dashboard (Fixed)

#### 4.1 Date Field Labels
- Added "From Date" and "To Date" labels
- Fixed date input text color (was white on white)

#### 4.2 Charts Implementation
- Replaced placeholder divs with Canvas elements
- Created `analytics_dashboard.js` with Chart.js integration
- Charts: Sales Trend, Customer Growth, Top Products, Inventory Status

#### 4.3 Period Type Grouping (Fixed)
**Problem:** Daily/Weekly/Monthly/Quarterly/Yearly selection didn't affect charts

**Solution:**
- Added `_get_period_key()` method for date grouping
- Updated `_generate_sales_chart_data()` to use period_type
- Updated `_generate_customer_chart_data()` to use period_type
- Added `period_type` to `@api.depends` decorator

**Files Modified:**
- `models/shopify_analytics.py`
- `static/src/js/analytics_dashboard.js`

#### 4.4 Currency (SAR)
- Changed Sales chart label from "$" to "SAR"
- Updated Y-axis ticks to show SAR
- Updated tooltips to show SAR format

### 5. Branding Update
- Changed app name from "Syncify" to "MS Shopify Automation"
- Icon path: `static/description/icon.png` (needs new logo)

**Files Modified:**
- `views/menu.xml` - Menu name

---

## Current Issues & Limitations

### Issue 1: Top Products Chart - No Real Data
**Status:** NEEDS FIX

**Problem:**
The `shopify.order` model only stores `total_price`, NOT individual line items (products in each order). This means we can't accurately determine:
- Which products were sold
- Quantity per product
- Revenue per product

**Current Workaround (Not Ideal):**
```python
# If no linked Odoo orders, distribute revenue by price ratio
# THIS IS ESTIMATED DATA, NOT REAL!
```

**Impact:**
- Top Products pie chart shows estimated/fake distribution
- Not suitable for real business analytics

### Issue 2: Missing Order Line Items
**Status:** ROOT CAUSE

The Shopify API returns order line items, but they're not being synced to Odoo:
```json
{
  "order": {
    "id": 123,
    "line_items": [
      {
        "product_id": 456,
        "title": "Product Name",
        "quantity": 2,
        "price": "29.99"
      }
    ]
  }
}
```

Currently, only the order header is stored, not the line items.

---

## Next Steps

### Phase 1: Fix Top Products Chart (COMPLETED)
**Status:** DONE (2025-12-10)

**Completed:**
- [x] Updated JS to show "No product sales data" message when no data
- [x] Removed fake revenue distribution logic from analytics

### Phase 2: Sync Order Line Items from Shopify (COMPLETED)
**Status:** DONE (2025-12-10)

**Completed Tasks:**

#### 2.1 Created New Model: `shopify.order.line`
- [x] Created `models/shopify_order_line.py` with full Shopify line item fields
- [x] Fields: order_id, shopify_line_id, shopify_product_id, shopify_variant_id, title, variant_title, sku, vendor, quantity, price, total_price, total_discount, net_price, fulfillment_status, taxable, grams, requires_shipping, gift_card, shopify_product_mapping_id
- [x] Computed fields: name, total_price, net_price
- [x] SQL constraint for unique line per order

#### 2.2 Updated Order Sync
- [x] Added `line_ids` One2many field to `shopify.order`
- [x] Created `_sync_order_line_items()` method in shopify_order.py
- [x] Updated `import_orders_from_shopify()` to call line sync for both new and existing orders
- [x] Line items sync automatically links to shopify.product if exists

#### 2.3 Updated Analytics
- [x] Modified `_get_top_selling_products()` to query `shopify.order.line` first
- [x] Falls back to sale.order.order_line if no Shopify line data
- [x] Groups by product, sums quantities and revenue
- [x] Returns real sales data for Top Products chart

#### 2.4 Security & Views
- [x] Added access rights in `security/ir.model.access.csv`
- [x] Added "Order Lines" tab in shopify_order_view.xml form view
- [x] Updated `models/__init__.py` to import new model

**Files Created:**
- `models/shopify_order_line.py`

**Files Modified:**
- `models/__init__.py`
- `models/shopify_order.py`
- `models/shopify_analytics.py`
- `security/ir.model.access.csv`
- `views/shopify_order_view.xml`

### Phase 3: Enhanced Analytics (Future)
Once we have line item data:

1. **Top Products by Quantity** - Most sold products
2. **Top Products by Revenue** - Highest revenue products
3. **Product Trends** - Sales over time per product
4. **Category Analysis** - Sales by product category
5. **Variant Analysis** - Popular variants

---

## Technical Reference

### Key Files

| File | Purpose |
|------|---------|
| `models/shopify_analytics.py` | Analytics computations & chart data |
| `models/shopify_instance.py` | Dashboard data & Shopify connection |
| `models/shopify_order.py` | Order sync from Shopify |
| `static/src/js/analytics_dashboard.js` | Chart.js rendering for Analytics |
| `static/src/js/dashboard.js` | Main dashboard OWL component |
| `views/dashboard_view.xml` | Dashboard & Analytics views |

### Chart Data Structure
```python
# Sales/Customer Chart
{
    'labels': ['2025-01', '2025-02', ...],  # Period labels
    'values': [1000, 2000, ...],             # Values
    'type': 'line'                           # Chart type
}

# Product Chart
{
    'labels': ['Product A', 'Product B', ...],
    'values': [500, 300, ...],  # Revenue or quantity
    'type': 'pie'
}

# Inventory Chart
{
    'labels': ['In Stock', 'Low Stock', 'Out of Stock'],
    'values': [50, 10, 5],
    'type': 'doughnut'
}
```

### Period Type Grouping
```python
def _get_period_key(self, date_obj, period_type):
    if period_type == 'daily':
        return date_obj.strftime('%Y-%m-%d')
    elif period_type == 'weekly':
        week_start = date_obj - timedelta(days=date_obj.weekday())
        return f"Week {week_start.strftime('%Y-%m-%d')}"
    elif period_type == 'monthly':
        return date_obj.strftime('%Y-%m')
    elif period_type == 'quarterly':
        quarter = (date_obj.month - 1) // 3 + 1
        return f"{date_obj.year}-Q{quarter}"
    elif period_type == 'yearly':
        return str(date_obj.year)
```

---

## File Structure

```
ms_shopify_automation/
├── __init__.py
├── __manifest__.py
├── DEVELOPMENT_NOTES.md          # This file
├── models/
│   ├── __init__.py
│   ├── shopify_instance.py       # Instance & dashboard data
│   ├── shopify_order.py          # Order sync + line item sync
│   ├── shopify_order_line.py     # Order line items model (NEW)
│   ├── shopify_customer.py       # Customer sync
│   ├── shopify_product.py        # Product sync
│   ├── shopify_analytics.py      # Analytics computations
│   ├── shopify_queue_job.py      # Queue management
│   ├── shopify_log.py            # Logging
│   ├── shopify_cron.py           # Scheduled jobs
│   └── shopify_webhook.py        # Webhooks
├── views/
│   ├── dashboard_view.xml        # Dashboard & Analytics views
│   ├── menu.xml                  # App menu (Shopify Automation)
│   ├── shopify_instance_view.xml
│   ├── shopify_order_view.xml
│   ├── shopify_customer_view.xml
│   ├── shopify_product_view.xml
│   └── ...
├── static/
│   ├── description/
│   │   └── icon.png              # App icon (needs update)
│   └── src/
│       ├── css/
│       │   └── dashboard.css     # All dashboard styles
│       ├── js/
│       │   ├── dashboard.js      # Main dashboard OWL
│       │   ├── dashboard_charts.js
│       │   └── analytics_dashboard.js  # Analytics charts
│       └── xml/
│           └── dashboard_template.xml  # OWL templates
├── security/
│   ├── ir.model.access.csv
│   ├── security.xml
│   └── record_rules.xml
└── wizard/
    └── manual_sync_wizard_view.xml
```

---

## Commands Reference

### Upgrade Module
```bash
python server/odoo-bin -c server/odoo.conf -u ms_shopify_automation -d YOUR_DATABASE
```

### Start with Dev Mode
```bash
python server/odoo-bin -c server/odoo.conf --dev=all
```

### Clear Browser Cache
- Windows: `Ctrl + Shift + R`
- Mac: `Cmd + Shift + R`

---

## Notes

### Currency
- Currently hardcoded to SAR (Saudi Riyal)
- Future: Get from instance or company settings

### Icon
- Location: `static/description/icon.png`
- Recommended size: 128x128 or 256x256 pixels

---

**Document maintained by:** Development Team
**Next Session:** Test order line sync & analytics, then Phase 3 (Enhanced Analytics)
