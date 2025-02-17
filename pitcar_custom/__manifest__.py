{
    'name':'Pitcar\'s Customization',
    'author':'Pitcar',
    'website':'https://www.pitcar.co.id',
    'summary':'Pitcar\'s Customization for Odoo 2024',
    'maintainer': 'Ahmad Husein Hambali, Teddinata Kusuma',
    'icon': '/pitcar_custom/static/pitcar-modified.png',
    'sequence': 1,
    'depends': [
        'base',
        'mail',
        'sale',
        'stock',
        'sale_stock',
        'account',
        'crm',
        'sale_management',
        'purchase',
        'project',
        'product',
        'bus',
        'web',
        'hr',
        'hr_attendance',
    ],
    'assets': {
        'web.assets_qweb': [
            'pitcar_custom/static/src/xml/queue_dashboard.xml',
            'pitcar_custom/static/src/xml/map_widget.xml',
            'pitcar_custom/static/src/xml/lead_time_widget.xml',
        ],
        'web.assets_backend': [
            # CSS first
            'pitcar_custom/static/src/css/custom_button.css',
            'pitcar_custom/static/src/css/lead_time.css',
            'pitcar_custom/static/src/css/custom_dashboard.css',
            'pitcar_custom/static/src/css/map.css',
            'pitcar_custom/static/src/scss/dashboard.scss',
            'pitcar_custom/static/src/css/timeline.css',
            # External CSS
            ('include', 'https://unpkg.com/leaflet@1.7.1/dist/leaflet.css'),
            # JS files
            ('include', 'https://unpkg.com/leaflet@1.7.1/dist/leaflet.js'),
            'pitcar_custom/static/src/js/product_template_list.js',
            'pitcar_custom/static/src/js/product_template_kanban.js',
            'pitcar_custom/static/src/js/lead_time_widget.js',
            'pitcar_custom/static/src/js/queue_dashboard.js',
            'pitcar_custom/static/src/js/map_widget.js',
        ],
    },
    'data': [
        'data/res_partner_data.xml',
        'data/res_partner_car_data.xml',
        'data/lead_time_data.xml',
        'data/pitcar_position_data.xml',
        'data/sequence.xml',

        'report/ir_actions_report_templates.xml',
        'report/ir_actions_report.xml',
        'report/report_invoice.xml',
        'report/booking_quotation_template.xml',  # Tambahkan ini

        'security/mechanic_security.xml',
        'security/lead_time_security.xml',
        'security/ir.model.access.csv',

        'wizard/mechanic_credential_views.xml',
        'wizard/attendance_export_wizard_view.xml',
        'wizard/booking_link_sale_order_views.xml',
        'wizard/part_response_wizard_views.xml',
        
        'views/account_move.xml',
        'views/pitcar_mechanic_views.xml',
        'views/pitcar_service_advisor_views.xml',
        'views/res_partner_car_brand.xml',
        'views/res_partner_car_type.xml',
        'views/res_partner_category.xml',
        'views/res_partner_car.xml',
        'views/res_partner.xml',
        'views/sale_order.xml',
        'views/sale_order_template.xml',
        'views/service_booking_views.xml',
        'views/stock_picking.xml',
        'views/product_views.xml',
        'views/product_tag_views.xml',
        'views/crm_tag_views.xml',
        'views/project_task_views.xml',
        'views/product_template_views.xml',
        'views/user_views.xml',
        'views/queue_actions.xml',
        'views/queue_dashboard_views.xml',
        'views/queue_metric_views.xml',
        'views/kpi_service_advisor_overview.xml',
        'views/kpi_views.xml',
        'views/mechanic_kpi.xml',
        'views/kpi_mechanic_overview.xml',
        'views/hr_employee_views.xml',
        'views/work_location_views.xml',
        'views/hr_attendance_views.xml',
        'views/utm_menu.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'default_timezone': 'Asia/Jakarta',
    'license': 'LGPL-3',
    'version':'16.0.91'
}