# MTO: Manufacture Order stays Draft

**Author:** Mohamed Saied  
**Version:** 19
**License:** LGPL-3

## What it does
For *Make To Order (MTO)* flows, Odoo normally creates a Manufacturing Order (MO) and **confirms** it immediately.
This addon overrides the manufacturing rule so that the MO is **created and kept in Draft**. This is useful when
your team wants to review/adjust components, dates, or responsible users before confirming.

## Key points
- Only affects MTO procurements that trigger manufacturing.
- Uses the standard `_prepare_mo_vals` so the created MO matches Odoo defaults.
- **Does not** call `action_confirm()`, so the MO stays in `draft`.

## Compatibility
- Tested with Odoo 19.  
- Depends on: `mrp`, `stock`.

## Usage
- Install the module.
- Create a Sales Order with MTO/Manufacture route. When procurement runs, the MO will be created in *Draft*.
- Manually open the MO and click *Confirm* when you're ready.

## Credits
- Developed by **Mohamed Saied**.
