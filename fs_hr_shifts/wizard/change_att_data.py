# -*- coding: utf-8 -*-

##############################################################################
#
#    Merged from rm_hr_attendance_sheet (Eng.Ramadan Khalil).
#
##############################################################################

from odoo import models, fields, api


class AttendanceSheetLineChange(models.TransientModel):
    _name = "attendance.sheet.line.change"
    _description = "Change Attendance Sheet Line Data"

    overtime = fields.Float("Overtime")
    late_in = fields.Float("Late In")
    diff_time = fields.Float("Diff Time")
    note = fields.Text("Note", required=True)
    att_line_id = fields.Many2one(comodel_name="attendance.sheet.line")

    @api.model
    def default_get(self, fields):
        res = super(AttendanceSheetLineChange, self).default_get(fields)
        atts_line_id = self.env[self._context['active_model']].browse(
            self._context['active_id'])
        if 'overtime' in fields and 'overtime' not in res:
            res['overtime'] = atts_line_id.overtime
            res['late_in'] = atts_line_id.late_in
            res['diff_time'] = atts_line_id.diff_time
            res['att_line_id'] = atts_line_id.id
        return res

    def change_att_data(self):
        [data] = self.read()
        self.ensure_one()
        atts_line_id = self.env['attendance.sheet.line'].browse(
            self._context['active_id'])
        res = {
            'overtime': data['overtime'],
            'late_in': data['late_in'],
            'diff_time': data['diff_time'],
            'note': data['note'],
        }
        atts_line_id.write(res)
        return {'type': 'ir.actions.act_window_close'}
