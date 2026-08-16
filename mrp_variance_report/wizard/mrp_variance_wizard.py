import xlsxwriter
import base64

from odoo import fields, models, api
from io import BytesIO


class MrpVarianceWizard(models.TransientModel):
    _name = 'mrp.variance.wizard'
    _description = 'Manufacturing Variance Report'

    date_from = fields.Date('Date From', required=True)
    date_to = fields.Date('Date To', required=True)
    product_ids = fields.Many2many(
        'product.product', 'mrp_variance_product_rel',
        'wizard_id', 'product_id', string='Finished Products',
    )
    production_ids = fields.Many2many(
        'mrp.production', 'mrp_variance_production_rel',
        'wizard_id', 'production_id', string='Manufacturing Orders',
    )
    datas = fields.Binary('File', readonly=True)
    datas_fname = fields.Char('Filename', readonly=True)

    def print_excel_report(self):
        domain = [('state', '=', 'done')]
        if self.date_from:
            domain.append(('date_start', '>=', self.date_from))
        if self.date_to:
            domain.append(('date_start', '<=', self.date_to))
        if self.product_ids:
            domain.append(('product_id', 'in', self.product_ids.ids))
        if self.production_ids:
            domain.append(('id', 'in', self.production_ids.ids))

        productions = self.env['mrp.production'].search(domain, order='name')

        fp = BytesIO()
        workbook = xlsxwriter.Workbook(fp)
        wbf = self._add_workbook_formats(workbook)

        self._write_material_sheet(workbook, wbf, productions)
        self._write_operation_sheet(workbook, wbf, productions)

        workbook.close()
        out = base64.encodebytes(fp.getvalue())
        fp.close()

        date_str = fields.Date.today().isoformat()
        filename = 'Manufacturing Variance Report %s' % date_str
        self.write({'datas': out, 'datas_fname': filename})

        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': (
                '/web/content/?model=%s&id=%s'
                '&field=datas&download=true&filename=%s%%2Exlsx'
            ) % (self._name, self.id, filename.replace(' ', '%20')),
        }

    # ──────────────────────────────────────────────
    #  Sheet 1: Material Variance
    # ──────────────────────────────────────────────
    def _write_material_sheet(self, workbook, wbf, productions):
        ws = workbook.add_worksheet('Material Variance')
        ws.set_landscape()
        ws.set_paper(9)  # A4

        # Column widths
        col_widths = [5, 30, 10, 14, 14, 14, 14, 16, 16, 16, 12]
        for i, w in enumerate(col_widths):
            ws.set_column(i, i, w)

        # Title
        ws.merge_range('A1:K2', 'Manufacturing Variance Report - Materials', wbf['title'])
        ws.merge_range(
            'A3:K3',
            'From: %s  To: %s' % (
                self.date_from.strftime('%d/%m/%Y'),
                self.date_to.strftime('%d/%m/%Y'),
            ),
            wbf['subtitle'],
        )

        row = 4  # 0-indexed
        grand_std_cost = 0.0
        grand_act_cost = 0.0

        headers = [
            '#', 'Component', 'UoM', 'Std Qty', 'Actual Qty',
            'Qty Variance', 'Unit Cost', 'Std Cost', 'Actual Cost',
            'Cost Variance', 'Variance %',
        ]

        for mo in productions:
            # MO Header
            mo_label = '%s | %s | Qty: %s %s' % (
                mo.name,
                mo.product_id.display_name,
                self._fmt_qty(mo.qty_produced),
                mo.product_uom_id.name,
            )
            ws.merge_range(row, 0, row, 10, mo_label, wbf['mo_header'])
            row += 1

            # Column headers
            for col, h in enumerate(headers):
                ws.write(row, col, h, wbf['header'])
            row += 1

            mo_std_cost = 0.0
            mo_act_cost = 0.0
            seq = 0

            # `scrapped` was removed in Odoo 19 (replaced by scrap_id)
            moves = mo.move_raw_ids.filtered(
                lambda m: m.state == 'done' and not (
                    m.scrapped if 'scrapped' in m._fields else m.scrap_id
                )
            )
            for move in moves:
                seq += 1
                std_qty = move.product_uom_qty
                act_qty = move.quantity
                unit_cost = move.product_id.standard_price
                std_cost = std_qty * unit_cost
                act_cost = act_qty * unit_cost
                qty_var = act_qty - std_qty
                cost_var = act_cost - std_cost
                var_pct = (cost_var / std_cost * 100) if std_cost else 0.0

                mo_std_cost += std_cost
                mo_act_cost += act_cost

                var_fmt = self._get_variance_format(wbf, cost_var)
                var_pct_fmt = self._get_variance_pct_format(wbf, cost_var)

                ws.write(row, 0, seq, wbf['content_center'])
                ws.write(row, 1, move.product_id.display_name, wbf['content'])
                ws.write(row, 2, move.product_uom.name, wbf['content_center'])
                ws.write(row, 3, std_qty, wbf['content_float'])
                ws.write(row, 4, act_qty, wbf['content_float'])
                ws.write(row, 5, qty_var, var_fmt)
                ws.write(row, 6, unit_cost, wbf['content_float'])
                ws.write(row, 7, std_cost, wbf['content_float'])
                ws.write(row, 8, act_cost, wbf['content_float'])
                ws.write(row, 9, cost_var, var_fmt)
                ws.write(row, 10, var_pct / 100, var_pct_fmt)
                row += 1

            # MO Summary row
            mo_var = mo_act_cost - mo_std_cost
            mo_var_pct = (mo_var / mo_std_cost * 100) if mo_std_cost else 0.0
            mo_var_f = self._get_variance_total_format(wbf, mo_var)
            mo_var_pct_f = self._get_variance_total_pct_format(wbf, mo_var)

            ws.merge_range(row, 0, row, 6, 'MO Total', wbf['total'])
            ws.write(row, 7, mo_std_cost, wbf['total_float'])
            ws.write(row, 8, mo_act_cost, wbf['total_float'])
            ws.write(row, 9, mo_var, mo_var_f)
            ws.write(row, 10, mo_var_pct / 100, mo_var_pct_f)
            row += 2  # blank row between MOs

            grand_std_cost += mo_std_cost
            grand_act_cost += mo_act_cost

        # Grand Total
        if productions:
            grand_var = grand_act_cost - grand_std_cost
            grand_pct = (grand_var / grand_std_cost * 100) if grand_std_cost else 0.0
            g_var_f = self._get_variance_total_format(wbf, grand_var)
            g_var_pct_f = self._get_variance_total_pct_format(wbf, grand_var)

            ws.merge_range(row, 0, row, 6, 'Grand Total - Materials', wbf['grand_total'])
            ws.write(row, 7, grand_std_cost, wbf['grand_total_float'])
            ws.write(row, 8, grand_act_cost, wbf['grand_total_float'])
            ws.write(row, 9, grand_var, g_var_f)
            ws.write(row, 10, grand_pct / 100, g_var_pct_f)

    # ──────────────────────────────────────────────
    #  Sheet 2: Operation Variance
    # ──────────────────────────────────────────────
    def _write_operation_sheet(self, workbook, wbf, productions):
        ws = workbook.add_worksheet('Operation Variance')
        ws.set_landscape()
        ws.set_paper(9)

        col_widths = [5, 25, 20, 16, 18, 16, 14, 16, 16, 16, 12]
        for i, w in enumerate(col_widths):
            ws.set_column(i, i, w)

        ws.merge_range('A1:K2', 'Manufacturing Variance Report - Operations', wbf['title'])
        ws.merge_range(
            'A3:K3',
            'From: %s  To: %s' % (
                self.date_from.strftime('%d/%m/%Y'),
                self.date_to.strftime('%d/%m/%Y'),
            ),
            wbf['subtitle'],
        )

        row = 4
        grand_std_cost = 0.0
        grand_act_cost = 0.0

        headers = [
            '#', 'Operation', 'Workcenter', 'Std Duration (min)',
            'Actual Duration (min)', 'Duration Variance', 'Cost/Hour',
            'Std Cost', 'Actual Cost', 'Cost Variance', 'Variance %',
        ]

        for mo in productions:
            mo_label = '%s | %s | Qty: %s %s' % (
                mo.name,
                mo.product_id.display_name,
                self._fmt_qty(mo.qty_produced),
                mo.product_uom_id.name,
            )
            ws.merge_range(row, 0, row, 10, mo_label, wbf['mo_header'])
            row += 1

            for col, h in enumerate(headers):
                ws.write(row, col, h, wbf['header'])
            row += 1

            mo_std_cost = 0.0
            mo_act_cost = 0.0
            seq = 0

            workorders = mo.workorder_ids.filtered(lambda wo: wo.state == 'done')
            for wo in workorders:
                seq += 1
                rate = wo.costs_hour or wo.workcenter_id.costs_hour
                std_dur = wo.duration_expected
                act_dur = wo.duration
                std_cost = (std_dur / 60.0) * rate
                act_cost = (act_dur / 60.0) * rate
                dur_var = act_dur - std_dur
                cost_var = act_cost - std_cost
                var_pct = (cost_var / std_cost * 100) if std_cost else 0.0

                mo_std_cost += std_cost
                mo_act_cost += act_cost

                var_fmt = self._get_variance_format(wbf, cost_var)
                var_pct_fmt = self._get_variance_pct_format(wbf, cost_var)

                ws.write(row, 0, seq, wbf['content_center'])
                ws.write(row, 1, wo.name or wo.operation_id.name or '', wbf['content'])
                ws.write(row, 2, wo.workcenter_id.name, wbf['content'])
                ws.write(row, 3, std_dur, wbf['content_float'])
                ws.write(row, 4, act_dur, wbf['content_float'])
                ws.write(row, 5, dur_var, var_fmt)
                ws.write(row, 6, rate, wbf['content_float'])
                ws.write(row, 7, std_cost, wbf['content_float'])
                ws.write(row, 8, act_cost, wbf['content_float'])
                ws.write(row, 9, cost_var, var_fmt)
                ws.write(row, 10, var_pct / 100, var_pct_fmt)
                row += 1

            # MO Summary
            mo_var = mo_act_cost - mo_std_cost
            mo_var_pct = (mo_var / mo_std_cost * 100) if mo_std_cost else 0.0
            mo_var_f = self._get_variance_total_format(wbf, mo_var)
            mo_var_pct_f = self._get_variance_total_pct_format(wbf, mo_var)

            ws.merge_range(row, 0, row, 6, 'MO Total', wbf['total'])
            ws.write(row, 7, mo_std_cost, wbf['total_float'])
            ws.write(row, 8, mo_act_cost, wbf['total_float'])
            ws.write(row, 9, mo_var, mo_var_f)
            ws.write(row, 10, mo_var_pct / 100, mo_var_pct_f)
            row += 2

            grand_std_cost += mo_std_cost
            grand_act_cost += mo_act_cost

        # Grand Total
        if productions:
            grand_var = grand_act_cost - grand_std_cost
            grand_pct = (grand_var / grand_std_cost * 100) if grand_std_cost else 0.0
            g_var_f = self._get_variance_total_format(wbf, grand_var)
            g_var_pct_f = self._get_variance_total_pct_format(wbf, grand_var)

            ws.merge_range(row, 0, row, 6, 'Grand Total - Operations', wbf['grand_total'])
            ws.write(row, 7, grand_std_cost, wbf['grand_total_float'])
            ws.write(row, 8, grand_act_cost, wbf['grand_total_float'])
            ws.write(row, 9, grand_var, g_var_f)
            ws.write(row, 10, grand_pct / 100, g_var_pct_f)

    # ──────────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────────
    @staticmethod
    def _fmt_qty(val):
        if val == int(val):
            return str(int(val))
        return '%.2f' % val

    def _get_variance_format(self, wbf, value):
        if value > 0:
            return wbf['content_float_red']
        elif value < 0:
            return wbf['content_float_green']
        return wbf['content_float']

    def _get_variance_pct_format(self, wbf, value):
        if value > 0:
            return wbf['content_pct_red']
        elif value < 0:
            return wbf['content_pct_green']
        return wbf['content_pct']

    def _get_variance_total_format(self, wbf, value):
        if value > 0:
            return wbf['total_float_red']
        elif value < 0:
            return wbf['total_float_green']
        return wbf['total_float']

    def _get_variance_total_pct_format(self, wbf, value):
        if value > 0:
            return wbf['total_pct_red']
        elif value < 0:
            return wbf['total_pct_green']
        return wbf['total_pct']

    # ──────────────────────────────────────────────
    #  Workbook Formats
    # ──────────────────────────────────────────────
    def _add_workbook_formats(self, workbook):
        colors = {
            'green': '#C6EFCE',
            'green_font': '#006100',
            'red': '#FFC7CE',
            'red_font': '#9C0006',
            'orange': '#FFC300',
            'light_orange': '#FFFFDB',
            'blue': '#4472C4',
            'light_blue': '#D6E4F0',
            'dark_blue': '#1F3864',
        }

        wbf = {}

        # Title
        wbf['title'] = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'font_size': 16, 'font_name': 'Calibri',
            'bg_color': colors['dark_blue'], 'font_color': '#FFFFFF',
        })

        # Subtitle (date range)
        wbf['subtitle'] = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'font_size': 11, 'font_name': 'Calibri',
            'bg_color': colors['light_blue'], 'font_color': '#000000',
        })

        # MO Header row
        wbf['mo_header'] = workbook.add_format({
            'bold': True, 'align': 'left', 'valign': 'vcenter',
            'font_size': 11, 'font_name': 'Calibri',
            'bg_color': colors['blue'], 'font_color': '#FFFFFF',
        })
        wbf['mo_header'].set_border()

        # Column header
        wbf['header'] = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'font_size': 10, 'font_name': 'Calibri',
            'bg_color': colors['orange'], 'font_color': '#000000',
        })
        wbf['header'].set_border()

        # Content - text
        wbf['content'] = workbook.add_format({
            'font_name': 'Calibri', 'font_size': 10,
        })
        wbf['content'].set_border()

        # Content - center
        wbf['content_center'] = workbook.add_format({
            'align': 'center', 'font_name': 'Calibri', 'font_size': 10,
        })
        wbf['content_center'].set_border()

        # Content - float
        wbf['content_float'] = workbook.add_format({
            'align': 'right', 'num_format': '#,##0.00',
            'font_name': 'Calibri', 'font_size': 10,
        })
        wbf['content_float'].set_border()

        # Content float - RED (unfavorable variance)
        wbf['content_float_red'] = workbook.add_format({
            'align': 'right', 'num_format': '#,##0.00',
            'font_name': 'Calibri', 'font_size': 10,
            'bg_color': colors['red'], 'font_color': colors['red_font'],
        })
        wbf['content_float_red'].set_border()

        # Content float - GREEN (favorable variance)
        wbf['content_float_green'] = workbook.add_format({
            'align': 'right', 'num_format': '#,##0.00',
            'font_name': 'Calibri', 'font_size': 10,
            'bg_color': colors['green'], 'font_color': colors['green_font'],
        })
        wbf['content_float_green'].set_border()

        # Content percent
        wbf['content_pct'] = workbook.add_format({
            'align': 'right', 'num_format': '0.0%',
            'font_name': 'Calibri', 'font_size': 10,
        })
        wbf['content_pct'].set_border()

        wbf['content_pct_red'] = workbook.add_format({
            'align': 'right', 'num_format': '0.0%',
            'font_name': 'Calibri', 'font_size': 10,
            'bg_color': colors['red'], 'font_color': colors['red_font'],
        })
        wbf['content_pct_red'].set_border()

        wbf['content_pct_green'] = workbook.add_format({
            'align': 'right', 'num_format': '0.0%',
            'font_name': 'Calibri', 'font_size': 10,
            'bg_color': colors['green'], 'font_color': colors['green_font'],
        })
        wbf['content_pct_green'].set_border()

        # MO Total row
        wbf['total'] = workbook.add_format({
            'bold': True, 'align': 'center', 'font_name': 'Calibri',
            'font_size': 10, 'bg_color': colors['light_orange'],
        })
        wbf['total'].set_border()

        wbf['total_float'] = workbook.add_format({
            'bold': True, 'align': 'right', 'num_format': '#,##0.00',
            'font_name': 'Calibri', 'font_size': 10,
            'bg_color': colors['light_orange'],
        })
        wbf['total_float'].set_border()

        wbf['total_float_red'] = workbook.add_format({
            'bold': True, 'align': 'right', 'num_format': '#,##0.00',
            'font_name': 'Calibri', 'font_size': 10,
            'bg_color': colors['red'], 'font_color': colors['red_font'],
        })
        wbf['total_float_red'].set_border()

        wbf['total_float_green'] = workbook.add_format({
            'bold': True, 'align': 'right', 'num_format': '#,##0.00',
            'font_name': 'Calibri', 'font_size': 10,
            'bg_color': colors['green'], 'font_color': colors['green_font'],
        })
        wbf['total_float_green'].set_border()

        wbf['total_pct'] = workbook.add_format({
            'bold': True, 'align': 'right', 'num_format': '0.0%',
            'font_name': 'Calibri', 'font_size': 10,
            'bg_color': colors['light_orange'],
        })
        wbf['total_pct'].set_border()

        wbf['total_pct_red'] = workbook.add_format({
            'bold': True, 'align': 'right', 'num_format': '0.0%',
            'font_name': 'Calibri', 'font_size': 10,
            'bg_color': colors['red'], 'font_color': colors['red_font'],
        })
        wbf['total_pct_red'].set_border()

        wbf['total_pct_green'] = workbook.add_format({
            'bold': True, 'align': 'right', 'num_format': '0.0%',
            'font_name': 'Calibri', 'font_size': 10,
            'bg_color': colors['green'], 'font_color': colors['green_font'],
        })
        wbf['total_pct_green'].set_border()

        # Grand Total
        wbf['grand_total'] = workbook.add_format({
            'bold': True, 'align': 'center', 'font_name': 'Calibri',
            'font_size': 11, 'bg_color': colors['orange'],
        })
        wbf['grand_total'].set_border()

        wbf['grand_total_float'] = workbook.add_format({
            'bold': True, 'align': 'right', 'num_format': '#,##0.00',
            'font_name': 'Calibri', 'font_size': 11,
            'bg_color': colors['orange'],
        })
        wbf['grand_total_float'].set_border()

        return wbf
