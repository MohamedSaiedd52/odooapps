# -*- coding: utf-8 -*-

##############################################################################
#
#    Merged from fs_planning: create planning slots for a whole
#    department or for employee tags at once.
#
##############################################################################

from odoo import models, fields, api


class PlanningSlot(models.Model):
    _inherit = "planning.slot"

    department = fields.Many2one("hr.department", string="Department")
    category_ids = fields.Many2many("hr.employee.category", string="Tags")

    def _create_slots(self, employees, vals):
        """Create one slot per employee resource from ``vals``."""
        Resource = self.env["resource.resource"]
        if not employees:
            return self.browse()
        resources = Resource.search(
            [("employee_id", "in", employees.ids)])
        created = self.browse()
        for res in resources:
            new_vals = dict(vals)
            new_vals["resource_id"] = res.id
            new_vals["department"] = False
            new_vals["category_ids"] = False
            if not new_vals.get("company_id"):
                new_vals["company_id"] = res.company_id.id
            if res.resource_type == "material":
                new_vals["state"] = "published"
            created |= super(PlanningSlot, self).create(new_vals)
        return created[-1] if created else created

    @api.onchange("resource_id")
    def _onchange_resource_id(self):
        self.department = False
        self.category_ids = False

    @api.onchange("department")
    def _onchange_department_id(self):
        if self.resource_id:
            self.resource_id = False
        self.category_ids = False

    @api.onchange("category_ids")
    def _onchange_category_ids(self):
        if self.resource_id:
            self.resource_id = False
        self.department = False

    @api.model_create_multi
    def create(self, vals_list):
        Resource = self.env["resource.resource"]

        for vals in vals_list:
            category_ids = (
                vals.get("category_ids")[0][2]
                if vals.get("category_ids") else False
            )
            # the field is named 'department' on planning.slot
            department_id = vals.get("department") or vals.get("department_id")

            if department_id:
                employees = self.env["hr.employee"].search(
                    [("department_id", "=", department_id)]
                )
                return self._create_slots(employees, vals)

            elif category_ids:
                employees = self.env["hr.employee"].search(
                    [("category_ids", "in", category_ids)]
                )
                return self._create_slots(employees, vals)

            elif vals.get("resource_id"):
                resource = Resource.browse(vals.get("resource_id"))
                if not vals.get("company_id"):
                    vals["company_id"] = resource.company_id.id
                if resource.resource_type == "material":
                    vals["state"] = "published"

            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id

        return super(PlanningSlot, self).create(vals_list)
