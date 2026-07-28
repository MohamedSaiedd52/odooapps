# -*- coding: utf-8 -*-
from . import models
from . import controllers
from . import wizard


def post_init_hook(env):
    """Flag abstract models so they can be excluded from rule configuration."""
    for model in env['ir.model'].search([]):
        if model.model in env.registry:
            model.abstract = env[model.model]._abstract
