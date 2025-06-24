from odoo import models, fields, _
from odoo.exceptions import UserError
import base64
import openpyxl
from io import BytesIO
import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class ImportInternalTransferWizard(models.TransientModel):
    _name = "import.internal.transfer.wizard"
    _description = "Import Internal Transfer Wizard"

    file = fields.Binary(string="Excel File (.xlsx)", required=True)
    product_by = fields.Selection([
        ('default_code', 'Internal Reference'),
        ('name', 'Name'),
    ], string="Identify Product By", required=True, default='default_code')

    source_location_id = fields.Many2one(
        'stock.location', string="Source Location", required=True)
    destination_location_id = fields.Many2one(
        'stock.location', string="Destination Location", required=True)
    picking_type_id = fields.Many2one(
        'stock.picking.type',
        string="Operation Type",
        required=True,
        domain=[('code', '=', 'internal')]
    )

    def read_xls_book(self):
        try:
            in_memory_file = BytesIO(base64.b64decode(self.file))
            workbook = openpyxl.load_workbook(filename=in_memory_file, data_only=True)
            sheet = workbook.active

            values_sheet = []
            for row in sheet.iter_rows(values_only=True):
                values_sheet.append([
                    str(cell).strip() if cell is not None else ''
                    for cell in row
                ])
            return values_sheet
        except Exception as e:
            raise UserError(_("Invalid Excel file. Error: %s") % str(e))

    def show_success_msg(self, counter, skipped_line_no, extra_message=""):
        dic_msg = "%s lines imported successfully." % counter
        if extra_message:
            dic_msg = extra_message + dic_msg
        if skipped_line_no:
            dic_msg += "\nNote:"
        for k, v in skipped_line_no.items():
            dic_msg += "\nRow No %s %s" % (k, v)

        wizard = self.env['import.transfer.message.wizard'].create({'message': dic_msg})
        return {
            'name': _('Import Result'),
            'type': 'ir.actions.act_window',
            'res_model': 'import.transfer.message.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    def import_internal_transfer_apply(self):
        values = self.read_xls_book()
        if not values:
            raise UserError(_("The file is empty."))

        header = values[0]
        expected_header = ['Product', 'Quantity']
        if [h.strip().lower() for h in header] != [h.lower() for h in expected_header]:
            raise UserError(_("Invalid header. Expected: %s") % ", ".join(expected_header))

        picking_type = self.picking_type_id

        picking_vals = {
            'location_id': self.source_location_id.id,
            'location_dest_id': self.destination_location_id.id,
            'scheduled_date': datetime.datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            'picking_type_id': picking_type.id,
            'origin': 'Import Internal Transfer',
        }
        picking = self.env['stock.picking'].create(picking_vals)

        skipped_lines = {}
        success_count = 0
        for index, row in enumerate(values[1:], start=2):
            product_value = str(row[0]).strip().split('.')[0]
            try:
                qty = float(row[1]) if row[1] else 1.0
            except Exception:
                skipped_lines[str(index)] = " - Invalid quantity"
                continue

            product = self.env['product.product'].search([
                (self.product_by, '=', product_value)
            ], limit=1)

            if not product:
                skipped_lines[str(index)] = " - Product not found: %s" % product_value
                continue

            move_vals = {
                'product_id': product.id,
                'product_uom_qty': qty,
                'product_uom': product.uom_id.id,
                'picking_id': picking.id,
                'name': product.name,
                'location_id': self.source_location_id.id,
                'location_dest_id': self.destination_location_id.id,
            }
            self.env['stock.move'].create(move_vals)
            success_count += 1

        msg_info = "Reference: %s\n" % picking.name
        return self.show_success_msg(success_count, skipped_lines, extra_message=msg_info)

