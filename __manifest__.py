# -*- coding: utf-8 -*-
{
    'name': 'SDV - Recepción por Piezas',
    'version': '1.0',
    'summary': 'Recepción de materias primas en m² creando piezas (lotes) con dimensiones',
    'author': 'SmallDev',
    'website': 'https://smalldev.es',
    'category': 'Inventory',
    'depends': [
        'stock',
        'purchase_stock',
        'sale_stock',
        'mrp',
        'sdv_cortes_especiales',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_picking_views.xml',
        'views/marble_receive_wizard_views.xml',
    ],
    'installable': True,
}
