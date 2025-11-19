from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

MEASURE_KEYS = ('x_ancho_cm', 'x_alto_cm', 'x_grosor_cm')


class MarbleReceiveWizard(models.TransientModel):
    _name = 'sdv.marble.receive.wizard'
    _description = 'Recepción de Mármol por Piezas'

    picking_id = fields.Many2one('stock.picking', required=True)
    line_ids = fields.One2many('sdv.marble.receive.line', 'wizard_id', string='Piezas')

    last_x_ancho_cm = fields.Float(string='Últ. ancho (cm)', readonly=True)
    last_x_alto_cm = fields.Float(string='Últ. alto (cm)', readonly=True)
    last_x_grosor_cm = fields.Float(string='Últ. grosor (cm)', readonly=True)

    m2_total_calculated = fields.Float(string='m² totales (calculados)', compute='_compute_totals', store=False)
    moves_info = fields.Char(string='Resumen movimientos', compute='_compute_moves_info', store=False)

    # Línea concreta de la recepción sobre la que vamos a registrar las piezas
    move_id_custom = fields.Many2one(
        'stock.move.line',
        string="Línea de recepción",
        help="Elemento de la recepción sobre el que se registrarán las piezas.",
    )

    # ----------------- Computes -----------------
    @api.depends('line_ids.x_ancho_cm', 'line_ids.x_alto_cm')
    def _compute_totals(self):
        for wiz in self:
            wiz.m2_total_calculated = sum(l.m2 for l in wiz.line_ids)

    @api.depends('picking_id.move_ids_without_package.move_line_ids.qty_done')
    def _compute_moves_info(self):
        for wiz in self:
            txt = []
            for m in wiz.picking_id.move_ids_without_package:
                qty_done = sum(ml.qty_done for ml in m.move_line_ids) if m.move_line_ids else 0.0
                txt.append(
                    f"{m.product_id.display_name}: "
                    f"planificado {m.product_uom_qty} {m.product_uom.name} | "
                    f"hecho {qty_done} {m.product_uom.name}"
                )
            wiz.moves_info = " | ".join(txt)

    # ----------------- Helpers -----------------
    def _get_expected_product_name(self, base_name, ancho_cm, alto_cm, grosor_cm):
        def fmt(x):
            val = round(x, 2)
            if val == int(val):
                return str(int(val))
            else:
                return ('%g' % val).replace(',', '.')
        return f"{base_name} – {fmt(ancho_cm)}x{fmt(alto_cm)}x{fmt(grosor_cm)} cm"

    def _find_existing_child(self, base_product, ancho_cm, alto_cm, grosor_cm):
        Product = self.env['product.product']
        base_tmpl = base_product.product_tmpl_id

        ancho_cm = round(ancho_cm, 2)
        alto_cm = round(alto_cm, 2)
        grosor_cm = round(grosor_cm, 2)

        expected_name = self._get_expected_product_name(base_tmpl.name, ancho_cm, alto_cm, grosor_cm)

        products = Product.with_context(active_test=False).search([
            ('name', '=', expected_name),
            ('company_id', '=', base_tmpl.company_id.id),
        ])
        if not products:
            return False

        fields_pp = Product._fields
        has_measure_fields = {'x_ancho', 'x_alto', 'x_grosor'} <= set(fields_pp.keys())

        for product in products:
            if has_measure_fields:
                product_ancho = round(product.x_ancho or 0.0, 2)
                product_alto = round(product.x_alto or 0.0, 2)
                product_grosor = round(product.x_grosor or 0.0, 2)

                if (product_ancho == ancho_cm and
                        product_alto == alto_cm and
                        product_grosor == grosor_cm):
                    if not product.active:
                        product.active = True
                    return product
            else:
                if not product.active:
                    product.active = True
                return product

        return False

    def _ensure_component_with_measures(self, tmpl, ancho_cm, alto_cm, grosor_cm):
        vals = {}
        has_flag = 'x_b_es_componente' in tmpl._fields
        has_ancho = 'x_ancho' in tmpl._fields
        has_alto = 'x_alto' in tmpl._fields
        has_grosor = 'x_grosor' in tmpl._fields

        if has_ancho and (tmpl.x_ancho or 0.0) <= 0 and (ancho_cm or 0.0) > 0:
            vals['x_ancho'] = ancho_cm
        if has_alto and (tmpl.x_alto or 0.0) <= 0 and (alto_cm or 0.0) > 0:
            vals['x_alto'] = alto_cm
        if has_grosor and (tmpl.x_grosor or 0.0) <= 0:
            if (grosor_cm or 0.0) <= 0:
                raise ValidationError(_(
                    "Para marcar el producto '%s' como componente, debes indicar un Grosor (cm) > 0."
                ) % (tmpl.display_name,))
            vals['x_grosor'] = grosor_cm

        if vals:
            tmpl.with_context(skip_measure_validation=True).write(vals)

        if has_flag and not tmpl.x_b_es_componente:
            tmpl.with_context(skip_measure_validation=True).write({'x_b_es_componente': True})

    def _create_child_product(self, base_product, ancho_cm, alto_cm, grosor_cm):
        """
        Crea un nuevo product.template con el nombre maquetado con medidas.
        El producto será rastreable por bienes (type='consu', is_storable=True)
        y heredará precios de compra del producto base.
        """
        ProductT = self.env['product.template']
        base_tmpl = base_product.product_tmpl_id

        ancho_cm = round(ancho_cm, 2)
        alto_cm = round(alto_cm, 2)
        grosor_cm = round(grosor_cm, 2)

        # UoM = Unidad para contar piezas
        uom_unit = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
        if not uom_unit:
            uom_unit = self.env['uom.uom'].search([('uom_type', '=', 'reference')], limit=1)
        if not uom_unit:
            raise UserError(_("No se encontró una unidad de medida de tipo 'Unidad'."))

        # Maquetamos el nombre con las medidas
        product_name = self._get_expected_product_name(base_tmpl.name, ancho_cm, alto_cm, grosor_cm)

        vals_tmpl = {
            'name': product_name,  # "Tablero – 1x2x3 cm"
            'type': 'consu',
            'is_storable': True,
            'categ_id': base_tmpl.categ_id.id,
            'uom_id': uom_unit.id,
            'uom_po_id': uom_unit.id,
            'tracking': 'none',
            'company_id': base_tmpl.company_id.id,
            'purchase_ok': True,
            'sale_ok': base_tmpl.sale_ok,
        }

        # Medidas + flag de componente
        for f, v in (('x_ancho', ancho_cm), ('x_alto', alto_cm), ('x_grosor', grosor_cm)):
            if f in base_tmpl._fields:
                vals_tmpl[f] = v
        if 'x_b_es_componente' in base_tmpl._fields:
            vals_tmpl['x_b_es_componente'] = True

        # Crear template sin disparar el constraint de medidas
        child_tmpl = ProductT.with_context(skip_measure_validation=True).create(vals_tmpl)
        self._ensure_component_with_measures(child_tmpl, ancho_cm, alto_cm, grosor_cm)

        # ==== HEREDAR ATRIBUTOS DEL PRODUCTO PADRE ====
        ptavs = base_product.product_template_attribute_value_ids
        if ptavs:
            attr_cmds = [(5, 0, 0)]  # limpiar posibles líneas de atributo previas
            for ptav in ptavs:
                attr_cmds.append((
                    0, 0, {
                    'attribute_id': ptav.attribute_id.id,
                    'value_ids': [(6, 0, [ptav.product_attribute_value_id.id])],
                }
                ))
            child_tmpl.write({'attribute_line_ids': attr_cmds})
            # Garantizamos que solo haya la combinación correspondiente
            child_tmpl._create_variant_ids()

        # Variante única
        child = child_tmpl.product_variant_id

        # === HEREDAR PRECIOS DE COMPRA ===

        # 1) Coste estándar (standard_price y precio de ventas lst_price)
        if 'standard_price' in child._fields:
            child.standard_price = base_product.standard_price

        if 'lst_price' in child._fields:
            child.lst_price = base_product.lst_price





        # 2) Tarifas de proveedor (seller_ids)
        #    Clonamos las líneas de proveedor del template base apuntando al nuevo template
        for seller in base_tmpl.seller_ids:
            seller.copy({'product_tmpl_id': child_tmpl.id})

        # SKU opcional heredando el código base
        if 'default_code' in child._fields and base_product.default_code:
            child.default_code = base_product.default_code

        return child

    def action_generate_pieces(self):
        self.ensure_one()
        picking = self.picking_id

        if not self.line_ids:
            raise UserError(_("Debes añadir al menos una pieza."))

        if not self.move_id_custom:
            raise UserError(_("Debes seleccionar la línea de recepción sobre la que registrar las piezas."))

        # Trabajamos A PARTIR DE LA LÍNEA DE MOVIMIENTO SELECCIONADA
        base_move_line = self.move_id_custom          # stock.move.line
        base_move = base_move_line.move_id           # stock.move asociado

        if not base_move:
            raise UserError(_("La línea seleccionada no tiene un movimiento asociado."))

        StockMove = self.env['stock.move']
        StockMoveLine = self.env['stock.move.line']

        # Agrupar líneas del asistente por medidas
        lines_by_measures = {}
        for line in self.line_ids:
            ancho = round(line.x_ancho_cm or 0.0, 2)
            alto = round(line.x_alto_cm or 0.0, 2)
            grosor = round(line.x_grosor_cm or 0.0, 2)
            if ancho <= 0 or alto <= 0 or grosor <= 0:
                raise ValidationError(_("Todas las piezas deben tener Ancho, Alto y Grosor > 0."))
            key = (ancho, alto, grosor)
            lines_by_measures.setdefault(key, []).append(line)

        base_product = base_move_line.product_id
        base_tmpl = base_product.product_tmpl_id

        # UoM Unidad
        uom_unit = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
        if not uom_unit:
            uom_unit = self.env['uom.uom'].search([('uom_type', '=', 'reference')], limit=1)
        if not uom_unit:
            raise UserError(_("No se encontró una unidad de medida de tipo 'Unidad'."))

        for (ancho, alto, grosor), lines_group in lines_by_measures.items():
            # 1) Buscar / crear producto hijo
            child = self._find_existing_child(base_product, ancho, alto, grosor)
            if not child:
                child = self._create_child_product(base_product, ancho, alto, grosor)

            quantity = len(lines_group)

            # 2) Reutilizar move existente del mismo picking + producto hijo, o crear uno nuevo
            existing_move = StockMove.search([
                ('picking_id', '=', picking.id),
                ('product_id', '=', child.id),
                ('state', 'not in', ('cancel', 'done')),
            ], limit=1)

            if existing_move:
                child_move = existing_move
                child_move.product_uom_qty += quantity
                start_seq = len(child_move.move_line_ids)
            else:
                child_move = StockMove.create({
                    'name': child.display_name,
                    'product_id': child.id,
                    'product_uom_qty': quantity,
                    'product_uom': uom_unit.id,
                    'picking_id': picking.id,
                    'company_id': picking.company_id.id,
                    'location_id': base_move_line.location_id.id,
                    'location_dest_id': base_move_line.location_dest_id.id,
                    'state': 'draft',
                    'purchase_line_id': base_move.purchase_line_id.id
                        if 'purchase_line_id' in base_move._fields else False,
                    'origin': base_move.origin or picking.name,
                })
                child_move._action_confirm()
                start_seq = 0

            # 3) Crear las move lines (1 por pieza)
            for seq, line in enumerate(lines_group, start=start_seq + 1):
                StockMoveLine.create({
                    'move_id': child_move.id,              # <-- IMPORTANTE: campo correcto
                    'picking_id': picking.id,
                    'product_id': child.id,
                    'product_uom_id': uom_unit.id,
                    'location_id': child_move.location_id.id,
                    'location_dest_id': child_move.location_dest_id.id,
                    'qty_done': 1.0,
                })

            child_move._action_assign()

        # Cancelar el movimiento base original (sustituido por los hijos)
        if base_move.state not in ('cancel', 'done'):
            base_move._action_cancel()

        return {'type': 'ir.actions.act_window_close'}

    # ---------- Duplicado de última línea ----------
    def _get_last_complete_line_values(self):
        self.ensure_one()
        for line in reversed(self.line_ids):
            a, b, g = line.x_ancho_cm or 0.0, line.x_alto_cm or 0.0, line.x_grosor_cm or 0.0
            if a > 0 and b > 0 and g > 0:
                return a, b, g
        a, b, g = self.last_x_ancho_cm or 0.0, self.last_x_alto_cm or 0.0, self.last_x_grosor_cm or 0.0
        if a > 0 and b > 0 and g > 0:
            return a, b, g
        return None

    def action_duplicate_last_line(self):
        self.ensure_one()
        vals = self._get_last_complete_line_values()
        if not vals:
            raise UserError(_("Edita primero una línea (ancho/alto/grosor > 0) para poder duplicarla."))

        ancho, alto, grosor = vals
        self.write({
            'line_ids': [(0, 0, {
                'x_ancho_cm': ancho,
                'x_alto_cm': alto,
                'x_grosor_cm': grosor,
            })]
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sdv.marble.receive.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class MarbleReceiveLine(models.TransientModel):
    _name = 'sdv.marble.receive.line'
    _description = 'Línea de pieza recibida'

    wizard_id = fields.Many2one('sdv.marble.receive.wizard', required=True, ondelete='cascade')
    x_ancho_cm = fields.Float(string='Ancho (cm)', required=True, digits=(10, 2))
    x_alto_cm = fields.Float(string='Alto (cm)', required=True, digits=(10, 2))
    x_grosor_cm = fields.Float(string='Grosor (cm)', required=True, digits=(10, 2))
    m2 = fields.Float(string='m²', compute='_compute_m2', store=False, digits=(10, 4))

    @api.depends('x_ancho_cm', 'x_alto_cm')
    def _compute_m2(self):
        for rec in self:
            rec.m2 = (rec.x_ancho_cm or 0) * (rec.x_alto_cm or 0) / 10000.0

    @api.onchange('x_ancho_cm', 'x_alto_cm', 'x_grosor_cm')
    def _onchange_push_snapshot_to_wizard(self):
        for rec in self:
            if rec.wizard_id:
                rec.wizard_id.last_x_ancho_cm = rec.x_ancho_cm or 0.0
                rec.wizard_id.last_x_alto_cm = rec.x_alto_cm or 0.0
                rec.wizard_id.last_x_grosor_cm = rec.x_grosor_cm or 0.0
