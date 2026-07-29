# -*- coding: utf-8 -*-
from odoo import api, fields, models


class IrModel(models.Model):
    _inherit = 'ir.model'

    abstract = fields.Boolean(readonly=True)

    @api.depends('name')
    @api.depends_context('arm_technical_names')
    def _compute_display_name(self):
        if not self.env.context.get('arm_technical_names'):
            return super()._compute_display_name()
        for model in self:
            model.display_name = "%s (%s)" % (model.name, model.model)


class IrModelFields(models.Model):
    _inherit = 'ir.model.fields'

    @api.depends('field_description', 'model')
    @api.depends_context('arm_technical_names')
    def _compute_display_name(self):
        if not self.env.context.get('arm_technical_names'):
            return super()._compute_display_name()
        for field in self:
            field.display_name = "%s (%s)" % (field.field_description, field.name)


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    def _button_immediate_function(self, function):
        res = super()._button_immediate_function(function)
        if function.__name__ in ('button_install', 'button_upgrade'):
            for model in self.env['ir.model'].search([]):
                if model.model in self.env.registry:
                    abstract = self.env[model.model]._abstract
                    if model.abstract != abstract:
                        model.abstract = abstract
        return res
