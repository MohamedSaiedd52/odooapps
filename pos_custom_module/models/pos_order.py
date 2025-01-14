from odoo import models, api, _
from odoo.exceptions import UserError

class PosOrder(models.Model):
    _inherit = 'pos.order'

    def action_paid_to_invoice(self):
        """
        Converts selected POS orders to invoices and posts them to accounting entries.
        """
        selected_orders = self.env['pos.order'].browse(self.env.context.get('active_ids', []))
        for order in selected_orders:
            try:
                if not order.partner_id:
                    raise UserError(_("Please assign a partner to the order before invoicing."))
                
                if order.state == 'paid':
                    # Convert the order to an invoice
                    result = order.action_pos_order_invoice()
                    
                    # Extract the invoice ID from the result and fetch the invoice record
                    invoice_id = result.get('res_id')
                    if invoice_id:
                        invoice = self.env['account.move'].browse(invoice_id)
                        
                        # Ensure the invoice is in draft state before posting
                        if invoice.state == 'draft':
                            invoice.post()
                            # Log a success message (requires `mail.thread` inheritance)
                            if hasattr(order, 'message_post'):
                                order.sudo().message_post(body=_("The order was successfully converted to an invoice and posted."))
            except UserError as e:
                raise e
            except Exception as e:
                # Log an error message if possible
                if hasattr(order, 'message_post'):
                    order.sudo().message_post(body=_("Failed to convert the order to an invoice: %s") % str(e))
                raise UserError(_("Failed to convert order %s to an invoice: %s") % (order.name, str(e)))
