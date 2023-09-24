{
    'name':'Pitcar\'s Customization',
    'author':'Pitcar',
    'website':'https://www.pitcar.co.id',
    'summary':'Pitcar\'s Customization for Odoo',
    'maintainer': 'Odoo Mates',
    'depends': [
        'base',
        'sale',
        'stock',
    ],
    'data': [
        'data/res_partner_data.xml',
        'data/res_partner_car_data.xml',

        'security/ir.model.access.csv',

        'views/res_partner_car.xml',
        'views/res_partner.xml',
        'views/sale_order.xml',
        'views/stock_picking.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}