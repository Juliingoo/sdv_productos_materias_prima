from odoo import models, api

class StockMoveInherit(models.Model):
    _inherit = 'stock.move'

    def name_get(self):
        result = []
        for move in self:
            if move.product_id:
                # Formato: [Producto] Nombre del movimiento
                name = f"[{move.product_id}] {move.origin}"
            else:
                name = move.name
                print("No tiene producto")
            result.append((move.id, name))
        return result

