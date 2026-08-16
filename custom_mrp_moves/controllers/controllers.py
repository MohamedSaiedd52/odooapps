# -*- coding: utf-8 -*-
# from odoo import http


# class CustomMrpMoves(http.Controller):
#     @http.route('/custom_mrp_moves/custom_mrp_moves', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/custom_mrp_moves/custom_mrp_moves/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('custom_mrp_moves.listing', {
#             'root': '/custom_mrp_moves/custom_mrp_moves',
#             'objects': http.request.env['custom_mrp_moves.custom_mrp_moves'].search([]),
#         })

#     @http.route('/custom_mrp_moves/custom_mrp_moves/objects/<model("custom_mrp_moves.custom_mrp_moves"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('custom_mrp_moves.object', {
#             'object': obj
#         })

