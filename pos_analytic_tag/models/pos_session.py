
from odoo import fields, models


class PosSession(models.Model):
    """To add analytic tags in pos session"""
    _inherit = 'pos.session'

    pos_analytic_account_id = fields.Many2one('account.analytic.account',
                                              string='Pos Analytic Tag',
                                              help="Pos Analytic account in"
                                                   " pos session",
                                              readonly=True)

    def _create_account_move(self, balancing_account=False,
                             amount_to_balance=0,
                             bank_payment_method_diffs=None):
        """Call the parent class method using super() and creates
         analytic distribution model"""
        res = super()._create_account_move(balancing_account,
                                           amount_to_balance,
                                           bank_payment_method_diffs)
        self.pos_analytic_account_id = self.config_id.analytic_account_id
        if self.pos_analytic_account_id:
            for move in self._get_related_account_moves():
                for rec in move.line_ids:
                    rec.write({
                        'analytic_distribution': {
                            self.config_id.analytic_account_id.id: 100
                        }
                    })
        else:
            for move in self._get_related_account_moves():
                for rec in move.line_ids:
                    rec.write({
                        'analytic_distribution': {}
                    })
        return res