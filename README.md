# SDV - Recepción por Piezas

## Descripción
Este módulo permite gestionar la **recepción de materias primas en m²** mediante la creación de **piezas (lotes)** con dimensiones específicas.  
Su objetivo es facilitar el control de materiales como planchas, mármoles, tableros u otros productos que se reciben en unidades físicas con medidas concretas.

El proceso añade un asistente para registrar las piezas provenientes de una recepción y vincularlas con los movimientos de stock correspondientes.

## Características principales
- Registro de piezas (lotes) con medidas físicas: largo, ancho, grosor, m², entre otros.
- Integración con los documentos de recepción de mercancía.
- Relación directa entre las piezas creadas y los movimientos de stock.
- Compatibilidad con operaciones de compra, venta y fabricación.
- Integración con el módulo **sdv_cortes_especiales** para gestionar formatos especiales y procesos derivados.

## Dependencias
Este módulo requiere los siguientes módulos de Odoo:
- `stock`
- `purchase_stock`
- `sale_stock`
- `mrp`
- `sdv_cortes_especiales`

## Instalación
1. Copiar el módulo a la carpeta de addons de Odoo.
2. Actualizar la lista de módulos.
3. Instalar **SDV - Recepción por Piezas** desde el menú de aplicaciones.

## Archivos incluidos
- **security/ir.model.access.csv** — Permisos de acceso.
- **views/stock_picking_views.xml** — Adaptaciones visuales en recepciones.
- **views/marble_receive_wizard_views.xml** — Vista del asistente de recepción por piezas.

## Licencia

