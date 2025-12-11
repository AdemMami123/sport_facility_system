# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SportsFacility(models.Model):
    _name = 'sports.facility'
    _description = 'Sports Facility'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Facility Name',
        required=True,
        index=True,
        tracking=True,
        help='Name of the sports facility'
    )
    
    facility_type = fields.Selection([
        ('court', 'Court'),
        ('gym', 'Gym'),
        ('pool', 'Pool'),
        ('field', 'Field'),
    ], string='Facility Type', required=True, default='court',
       tracking=True,
       help='Type of sports facility')
    
    description = fields.Text(
        string='Description',
        help='Detailed description of the facility'
    )
    
    capacity = fields.Integer(
        string='Capacity',
        default=1,
        help='Maximum number of people allowed'
    )
    
    hourly_rate = fields.Float(
        string='Hourly Rate',
        digits='Product Price',
        tracking=True,
        help='Cost per hour for booking this facility'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        help='Currency for the hourly rate'
    )
    
    status = fields.Selection([
        ('available', 'Available'),
        ('maintenance', 'Under Maintenance'),
        ('booked', 'Booked'),
    ], string='Status', default='available', required=True,
       tracking=True,
       help='Current status of the facility')
    
    image = fields.Binary(
        string='Image',
        attachment=True,
        help='Image of the facility'
    )
    
    location = fields.Char(
        string='Location',
        help='Physical location of the facility'
    )
    
    operating_hours_start = fields.Float(
        string='Operating Hours Start',
        default=8.0,
        help='Start time of daily operations (24-hour format)'
    )
    
    operating_hours_end = fields.Float(
        string='Operating Hours End',
        default=22.0,
        help='End time of daily operations (24-hour format)'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to archive the facility'
    )
    
    booking_count = fields.Integer(
        string='Number of Bookings',
        compute='_compute_booking_count',
        help='Total number of bookings for this facility'
    )

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Facility name must be unique!'),
    ]

    @api.depends('name')
    def _compute_booking_count(self):
        """Count all bookings related to this facility"""
        for record in self:
            record.booking_count = self.env['sports.booking'].search_count([
                ('facility_id', '=', record.id)
            ])

    @api.constrains('capacity')
    def _check_capacity(self):
        for record in self:
            if record.capacity < 1:
                raise ValidationError(_('Capacity must be at least 1.'))

    @api.constrains('hourly_rate')
    def _check_hourly_rate(self):
        for record in self:
            if record.hourly_rate < 0:
                raise ValidationError(_('Hourly rate cannot be negative.'))

    @api.constrains('operating_hours_start', 'operating_hours_end')
    def _check_operating_hours(self):
        for record in self:
            if record.operating_hours_start < 0 or record.operating_hours_start >= 24:
                raise ValidationError(_('Operating hours start must be between 0 and 24.'))
            if record.operating_hours_end < 0 or record.operating_hours_end >= 24:
                raise ValidationError(_('Operating hours end must be between 0 and 24.'))
            if record.operating_hours_start >= record.operating_hours_end:
                raise ValidationError(_('Operating hours start must be before operating hours end.'))

    def action_view_bookings(self):
        """
        Open tree view of all bookings related to this facility
        
        :return: Action dictionary to display bookings
        """
        self.ensure_one()
        
        return {
            'name': _('Bookings for %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'sports.booking',
            'view_mode': 'tree,form,calendar',
            'domain': [('facility_id', '=', self.id)],
            'context': {
                'default_facility_id': self.id,
                'search_default_facility_id': self.id,
            },
            'target': 'current',
        }
