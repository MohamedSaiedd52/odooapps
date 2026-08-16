import io
import json
import base64
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BomConsumptionWizard(models.TransientModel):
    _name = 'bom.consumption.wizard'
    _description = 'BOM vs Actual Consumption Report Wizard'

    date_from = fields.Date(
        string='From Date', required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(
        string='To Date', required=True,
        default=fields.Date.context_today)
    production_ids = fields.Many2many(
        'mrp.production', string='Manufacturing Orders',
        domain=[('state', 'in', ['draft', 'confirmed', 'progress', 'to_close', 'done'])])
    product_ids = fields.Many2many('product.product', string='Finished Products')
    state_filter = fields.Selection([
        ('all',       'All States'),
        ('draft',     'Draft'),
        ('confirmed', 'Confirmed'),
        ('progress',  'In Progress'),
        ('to_close',  'To Close'),
        ('done',      'Done'),
    ], string='MO Status', default='all')
    show_only_diff = fields.Boolean(string='Show Differences Only', default=False)

    # ─────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────

    def _get_productions(self):
        domain = []
        if self.state_filter == 'all':
            # all states including draft/confirmed
            domain.append(('state', 'in',
                            ['draft', 'confirmed', 'progress', 'to_close', 'done']))
        else:
            domain.append(('state', '=', self.state_filter))

        if self.production_ids:
            domain.append(('id', 'in', self.production_ids.ids))
        if self.product_ids:
            domain.append(('product_id', 'in', self.product_ids.ids))

        # date_start is the correct field in both Odoo 18 and 19 Enterprise
        # If your instance uses 'scheduled_date' change it here
        if self.date_from:
            domain.append(('date_start', '>=',
                            fields.Datetime.to_datetime(self.date_from)))
        if self.date_to:
            domain.append(('date_start', '<=',
                            fields.Datetime.to_datetime(self.date_to)
                            .replace(hour=23, minute=59, second=59)))

        return self.env['mrp.production'].search(domain, order='name asc')

    def _get_actual_qty(self, move):
        """
        Return total qty actually pulled from stock for one raw-material move,
        regardless of the number of steps (1 / 2 / 3) or warehouses.

        Strategy: collect ALL stock.move.line records that are:
          • state = 'done'
          • linked to this move OR any move in its origin chain
          • NOT an mrp_operation picking (those are internal WIP moves,
            not real stock withdrawals)

        We use a recursive walk through move_orig_ids so multi-step and
        multi-warehouse routes are handled automatically.
        """
        def _walk(mv, visited):
            if mv.id in visited:
                return 0.0
            visited.add(mv.id)

            picking_code = (mv.picking_type_id.code
                            if mv.picking_type_id else 'mrp_operation')

            if mv.move_orig_ids:
                # This move has origins → go deeper first
                total = 0.0
                for orig in mv.move_orig_ids:
                    total += _walk(orig, visited)
                # If nothing came back from origins (e.g. all cancelled),
                # fall back to this move's own done lines
                if total == 0.0 and picking_code != 'mrp_operation':
                    total = sum(
                        ml.quantity for ml in mv.move_line_ids
                        if ml.state == 'done'
                    )
                return total
            else:
                # Leaf move – on a done line `quantity` is the done qty
                # (stock.move.line has no qty_done field in 17/18/19)
                return sum(
                    ml.quantity for ml in mv.move_line_ids
                    if ml.state == 'done'
                )

        return _walk(move, set())

    def _build_report_lines(self, productions):
        lines = []
        for mo in productions:
            for move in mo.move_raw_ids:
                planned_qty = move.product_uom_qty
                actual_qty  = self._get_actual_qty(move)
                diff_qty    = actual_qty - planned_qty
                unit_cost   = move.product_id.standard_price
                uom_name    = move.product_uom.name if move.product_uom else ''

                if self.show_only_diff and abs(diff_qty) < 0.001:
                    continue

                if diff_qty > 0.001:
                    status = 'over'
                elif diff_qty < -0.001:
                    status = 'under'
                else:
                    status = 'exact'

                pct = (actual_qty / planned_qty * 100) if planned_qty else 0.0

                lines.append({
                    'mo_name':          mo.name,
                    'mo_id':            mo.id,
                    'finished_product': mo.product_id.display_name,
                    'component_name':   move.product_id.display_name,
                    'component_ref':    move.product_id.default_code or '',
                    'uom':              uom_name,
                    'planned_qty':      planned_qty,
                    'actual_qty':       actual_qty,
                    'diff_qty':         diff_qty,
                    'unit_cost':        unit_cost,
                    'diff_value':       diff_qty * unit_cost,
                    'pct':              pct,
                    'status':           status,
                })
        return lines

    # ─────────────────────────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────────────────────────

    def action_print_pdf(self):
        productions = self._get_productions()
        if not productions:
            raise UserError(
                _('No manufacturing orders found for the selected filters.'))
        lines = self._build_report_lines(productions)
        if not lines:
            raise UserError(_('No component lines found to print.'))

        # Store report data on the wizard record so the QWeb template
        # can read it via o.report_* fields (avoids the docs[0] IndexError)
        self.write({
            'report_date_from':  str(self.date_from),
            'report_date_to':    str(self.date_to),
            'report_company':    self.env.company.name,
            'report_printed_at': fields.Datetime.context_timestamp(
                self, fields.Datetime.now()).strftime('%Y-%m-%d %H:%M'),
            'report_lines_json': self._lines_to_json(lines),
        })

        return self.env.ref(
            'ms_mfg_bom_consumption_report.action_bom_consumption_pdf'
        ).report_action(self)          # pass self (wizard) as the record

    def _lines_to_json(self, lines):
        return json.dumps(lines)

    def get_report_lines(self):
        """Called from the QWeb template (`json` is not available there)."""
        self.ensure_one()
        return json.loads(self.report_lines_json or '[]')

    def action_export_excel(self):
        productions = self._get_productions()
        if not productions:
            raise UserError(
                _('No manufacturing orders found for the selected filters.'))
        lines = self._build_report_lines(productions)
        if not lines:
            raise UserError(_('No component lines found to export.'))

        xlsx_data = self._generate_xlsx(lines)
        attachment = self.env['ir.attachment'].create({
            'name': 'BOM_Consumption_Report.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(xlsx_data),
            'mimetype': (
                'application/vnd.openxmlformats-officedocument'
                '.spreadsheetml.sheet'),
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%d?download=true' % attachment.id,
            'target': 'self',
        }

    # ─────────────────────────────────────────────────────────────────
    # Stored fields used by QWeb (avoids docs[0] issue)
    # ─────────────────────────────────────────────────────────────────

    report_date_from  = fields.Char()
    report_date_to    = fields.Char()
    report_company    = fields.Char()
    report_printed_at = fields.Char()
    report_lines_json = fields.Text()

    # ─────────────────────────────────────────────────────────────────
    # Excel generation
    # ─────────────────────────────────────────────────────────────────

    def _generate_xlsx(self, lines):
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter
        except ImportError:
            raise UserError(
                _('openpyxl is required. Run: pip install openpyxl'))

        wb  = openpyxl.Workbook()
        ws  = wb.active
        ws.title = 'BOM vs Actual'

        C_H_BG  = 'FF1F3A5F'; C_H_FG  = 'FFFFFFFF'
        C_S_BG  = 'FFD6E4F0'; C_S_FG  = 'FF1F3A5F'
        C_OV_B  = 'FFFCE8E8'; C_OV_F  = 'FFA32D2D'
        C_UN_B  = 'FFEAF3DE'; C_UN_F  = 'FF3B6D11'
        C_EX_B  = 'FFF1EFE8'; C_EX_F  = 'FF5F5E5A'
        C_ALT   = 'FFF8F8F8'; C_WHT   = 'FFFFFFFF'
        C_SUM   = 'FFFFFDE7'

        thin   = Side(style='thin', color='FFD0D0D0')
        brd    = Border(left=thin, right=thin, top=thin, bottom=thin)
        ctr    = Alignment(horizontal='center', vertical='center', wrap_text=True)
        rgt    = Alignment(horizontal='right',  vertical='center')

        def fill(c):  return PatternFill('solid', fgColor=c)
        def font(bold=False, color=C_H_FG, size=11):
            return Font(name='Arial', bold=bold, color=color, size=size)

        # Title
        ws.merge_cells('A1:K1')
        ws['A1'].value     = 'BOM vs Actual Consumption Report'
        ws['A1'].font      = Font(name='Arial', bold=True, size=16, color=C_H_BG[2:])
        ws['A1'].alignment = ctr
        ws.row_dimensions[1].height = 32

        ws.merge_cells('A2:K2')
        ws['A2'].value = (
            f"Period: {self.date_from}  →  {self.date_to}"
            f"    |    Company: {self.env.company.name}")
        ws['A2'].font      = Font(name='Arial', size=10, color='FF666666')
        ws['A2'].alignment = ctr
        ws.row_dimensions[2].height = 18

        # Column headers
        cols = [
            ('Manufacturing Order', 20), ('Finished Product', 22),
            ('Component', 30), ('Ref', 14), ('UoM', 8),
            ('Planned Qty', 13), ('Actual Qty', 13), ('Diff Qty', 12),
            ('Unit Cost (EGP)', 15), ('Diff Value (EGP)', 16), ('% Consumed', 13),
        ]
        for ci, (lbl, w) in enumerate(cols, 1):
            c = ws.cell(row=4, column=ci, value=lbl)
            c.font = font(bold=True); c.fill = fill(C_H_BG)
            c.alignment = ctr; c.border = brd
            ws.column_dimensions[get_column_letter(ci)].width = w
        ws.row_dimensions[4].height = 22
        ws.freeze_panes = 'A5'

        row = 5; cur_mo = None
        q_fmt = '#,##0.000'; p_fmt = '#,##0.00 "EGP"'; pct_fmt = '0.0"%"'

        for i, ln in enumerate(lines):
            if ln['mo_name'] != cur_mo:
                cur_mo = ln['mo_name']
                ws.merge_cells(start_row=row, start_column=1,
                               end_row=row, end_column=11)
                c = ws.cell(row=row, column=1,
                            value=f"  ▶  {ln['mo_name']}  |  {ln['finished_product']}")
                c.font = Font(name='Arial', bold=True, size=10, color=C_S_FG[2:])
                c.fill = fill(C_S_BG)
                c.alignment = Alignment(vertical='center')
                ws.row_dimensions[row].height = 18
                row += 1

            rb, df = ((C_OV_B, C_OV_F) if ln['status'] == 'over'
                      else (C_UN_B, C_UN_F) if ln['status'] == 'under'
                      else (C_EX_B, C_EX_F))
            ab = C_ALT if i % 2 == 0 else C_WHT

            vals = [ln['mo_name'], ln['finished_product'], ln['component_name'],
                    ln['component_ref'], ln['uom'],
                    ln['planned_qty'], ln['actual_qty'], ln['diff_qty'],
                    ln['unit_cost'], ln['diff_value'], ln['pct']]
            fmts = [None]*5 + [q_fmt, q_fmt, q_fmt, p_fmt, p_fmt, pct_fmt]

            for ci, (v, fm) in enumerate(zip(vals, fmts), 1):
                c = ws.cell(row=row, column=ci, value=v)
                c.font = Font(name='Arial', size=10,
                              color=df[2:] if ci in (8, 10) else 'FF1F1F1F')
                c.fill      = fill(rb if ci in (8, 10) else ab)
                c.border    = brd
                c.alignment = rgt if ci >= 6 else Alignment(
                    vertical='center', wrap_text=True)
                if fm:
                    c.number_format = fm
            ws.row_dimensions[row].height = 16
            row += 1

        # Summary
        row += 1
        ov  = [l for l in lines if l['status'] == 'over']
        un  = [l for l in lines if l['status'] == 'under']
        ex  = [l for l in lines if l['status'] == 'exact']
        tot = sum(l['diff_value'] for l in lines)

        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=11)
        c = ws.cell(row=row, column=1, value='SUMMARY')
        c.font = font(bold=True, size=12); c.fill = fill(C_H_BG); c.alignment = ctr
        ws.row_dimensions[row].height = 20; row += 1

        for lbl, val, fm in [
            ('Total Components',          len(lines), None),
            ('Over Consumed (lines)',      len(ov),    None),
            ('Under Consumed (lines)',     len(un),    None),
            ('Exact Match (lines)',        len(ex),    None),
            ('Total Diff Value (EGP)',     tot,        p_fmt),
            ('Over-consumed Value (EGP)',  sum(l['diff_value'] for l in ov),  p_fmt),
            ('Under-consumed Value (EGP)', sum(l['diff_value'] for l in un),  p_fmt),
        ]:
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=8)
            lc = ws.cell(row=row, column=1, value=lbl)
            lc.font = Font(name='Arial', bold=True, size=10, color='FF333333')
            lc.fill = fill(C_SUM); lc.border = brd
            ws.merge_cells(start_row=row, start_column=9, end_row=row, end_column=11)
            vc = ws.cell(row=row, column=9, value=val)
            vc.font = Font(name='Arial', bold=True, size=11, color=C_H_BG[2:])
            vc.fill = fill(C_SUM); vc.border = brd; vc.alignment = rgt
            if fm:
                vc.number_format = fm
            ws.row_dimensions[row].height = 16; row += 1

        ws.auto_filter.ref = f'A4:K{row - 1}'
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
