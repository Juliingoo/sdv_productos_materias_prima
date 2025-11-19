from odoo import models

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_open_marble_receive_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Registrar piezas (mármol)',
            'res_model': 'sdv.marble.receive.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_picking_id': self.id},
        }
