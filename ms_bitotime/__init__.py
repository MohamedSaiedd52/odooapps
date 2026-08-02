# -*- coding: utf-8 -*-

# Embedded job queue (merged from OCA queue_job — only the runtime core).
# Must be imported first: it registers the queue.* models, the /queue_job
# controllers and monkey-patches the Odoo server to start the jobrunner.
from . import queue

from . import models
from . import wizard
from . import controllers

from .queue.post_init_hook import post_init_hook
from .queue.post_load import post_load
