import re
from io import BytesIO

from odoo import models

from openpyxl import Workbook


class ReportXlsxAbstract(models.AbstractModel):
    """Base class for XLSX reports rendered with openpyxl.

    Concrete reports must implement generate_xlsx_report(workbook, data, objs)
    and add their own worksheets to the given openpyxl Workbook.
    """

    _name = "report.report_xlsx_aa_aa.abstract"
    _description = "Abstract XLSX Report (openpyxl)"

    def _get_objs_for_report(self, docids, data):
        """
        Returns objects for the xlsx report. From the WebUI these are
        either passed as docids (taken from context.active_ids) or, for
        wizards, inside data. Manual calls may rely on regular context,
        setting docids, or setting data.
        """
        if docids:
            ids = docids
        elif data and "context" in data:
            ids = data["context"].get("active_ids", [])
        else:
            ids = self.env.context.get("active_ids", [])
        return self.env[self.env.context.get("active_model")].browse(ids)

    def create_xlsx_report(self, docids, data):
        objs = self._get_objs_for_report(docids, data)
        workbook = Workbook()
        # Reports create their own sheets; drop the default one.
        workbook.remove(workbook.active)
        self.generate_xlsx_report(workbook, data, objs)
        if not workbook.worksheets:
            workbook.create_sheet("Report")
        buffer = BytesIO()
        workbook.save(buffer)
        buffer.seek(0)
        return buffer.read(), "xlsx"

    def generate_xlsx_report(self, workbook, data, objs):
        raise NotImplementedError()

    def _check_ws_name(self, name):
        """Sanitize a worksheet name: strip characters Excel forbids and
        enforce the 31 characters limit. openpyxl deduplicates identical
        titles by itself when the sheet is created."""
        name = re.sub(r"[/\\*\[\]:?]", "", name or "Report")
        return name[:31] or "Report"
