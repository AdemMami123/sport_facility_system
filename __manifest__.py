# -*- coding: utf-8 -*-
{
    'name': 'Sports Facility Booking System',
    'version': '17.0.1.0.0',
    'category': 'Services',
    'summary': 'Manage sports facility bookings and reservations',
    'description': """
        Sports Facility Booking System
        ===============================
        This module allows you to manage sports facility bookings and reservations.
        
        Features:
        ---------
        * Facility management
        * Booking and reservation system
        * Calendar integration
        * Customer management
        * Payment processing
    """,
    'author': 'Mohamed Landolsi, Adem Mami, Ahmed Yasser Zrelli',
    'website': 'https://github.com/AdemMami123/sport_facility_system',
    'depends': [
        'base',
        'web',
        'website',
        'calendar',
        'sale_management',
        'mail',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        
        # Views
        'views/facility_views.xml',
        'views/booking_views.xml',
        'views/equipment_views.xml',
        
        # Templates
        'views/templates/booking_templates.xml',
        'views/templates/assets.xml',
        
        # Menus
        'views/menu.xml',
    ],
    'demo': [
        # Demo Data
        'data/demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
