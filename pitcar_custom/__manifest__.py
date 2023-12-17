{
    'name':'Pitcar\'s Customization',
    'author':'Pitcar',
    'website':'https://www.pitcar.co.id',
    'summary':'Pitcar\'s Customization for Odoo',
    'maintainer': 'Ahmad Husein Hambali',
    'sequence': 1,
    'depends': [
        'base',
        'sale',
        'stock',
        'sale_stock',
        'account',
        'crm',
        'sale_management',
        'purchase'
    ],
    'data': [
        'data/res_partner_data.xml',
        'data/res_partner_car_data.xml',

        'report/ir_actions_report_templates.xml',
        'report/ir_actions_report.xml',
        'report/report_invoice.xml',

        'security/ir.model.access.csv',

        'views/account_move.xml',
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
    'version':'16.0.5'
}