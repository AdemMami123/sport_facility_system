# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date


class SportsMembership(models.Model):
    _name = 'sports.membership'
    _description = 'Sports Membership'
    _order = 'start_date desc'
    _rec_name = 'member_id'

    member_id = fields.Many2one(
        'res.partner',
        string='Member',
        required=True,
        ondelete='restrict',
        help='Member associated with this membership'
    )
    
    membership_type = fields.Selection([
        ('basic', 'Basic'),
        ('premium', 'Premium'),
        ('vip', 'VIP'),
    ], string='Membership Type', required=True, default='basic',
       help='Type of membership plan')
    
    start_date = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.context_today,
        help='Membership start date'
    )
    
    end_date = fields.Date(
        string='End Date',
        required=True,
        help='Membership expiration date'
    )
    
    discount_percentage = fields.Float(
        string='Discount Percentage',
        digits=(5, 2),
        default=0.0,
        help='Discount percentage on bookings'
    )
    
    status = fields.Selection([
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='active', required=True, tracking=True,
       help='Current status of the membership')
    
    payment_status = fields.Selection([
        ('paid', 'Paid'),
        ('pending', 'Pending'),
    ], string='Payment Status', default='pending', required=True, tracking=True,
       help='Payment status of the membership')
    
    is_active = fields.Boolean(
        string='Is Active',
        compute='_compute_is_active',
        store=True,
        help='Whether the membership is currently active'
    )
    
    duration_days = fields.Integer(
        string='Duration (Days)',
        compute='_compute_duration',
        store=True,
        help='Total duration of the membership in days'
    )
    
    remaining_days = fields.Integer(
        string='Remaining Days',
        compute='_compute_remaining_days',
        help='Number of days remaining until expiration'
    )
    
    membership_fee = fields.Float(
        string='Membership Fee',
        digits='Product Price',
        help='Total membership fee amount'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to archive the membership'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        readonly=True
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes or comments'
    )

    _sql_constraints = [
        ('discount_valid', 'CHECK(discount_percentage >= 0 AND discount_percentage <= 100)', 
         'Discount percentage must be between 0 and 100!'),
    ]

    @api.depends('start_date', 'end_date', 'status')
    def _compute_is_active(self):
        """Check if membership is active based on current date and status"""
        today = fields.Date.context_today(self)
        for record in self:
            if record.status == 'active' and record.start_date and record.end_date:
                record.is_active = record.start_date <= today <= record.end_date
            else:
                record.is_active = False

    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        """Calculate total duration of membership in days"""
        for record in self:
            if record.start_date and record.end_date:
                delta = record.end_date - record.start_date
                record.duration_days = delta.days + 1
            else:
                record.duration_days = 0

    @api.depends('end_date')
    def _compute_remaining_days(self):
        """Calculate remaining days until expiration"""
        today = fields.Date.context_today(self)
        for record in self:
            if record.end_date:
                delta = record.end_date - today
                record.remaining_days = delta.days if delta.days > 0 else 0
            else:
                record.remaining_days = 0

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        """Ensure end date is after start date"""
        for record in self:
            if record.start_date and record.end_date:
                if record.end_date <= record.start_date:
                    raise ValidationError(_('End date must be after start date.'))

    @api.constrains('membership_fee')
    def _check_membership_fee(self):
        """Ensure membership fee is not negative"""
        for record in self:
            if record.membership_fee < 0:
                raise ValidationError(_('Membership fee cannot be negative.'))

    @api.model
    def create(self, vals):
        """Auto-set discount percentage based on membership type"""
        if vals.get('membership_type') and not vals.get('discount_percentage'):
            discount_map = {
                'basic': 5.0,
                'premium': 15.0,
                'vip': 25.0,
            }
            vals['discount_percentage'] = discount_map.get(vals['membership_type'], 0.0)
        return super(SportsMembership, self).create(vals)

    @api.onchange('membership_type')
    def _onchange_membership_type(self):
        """Update discount percentage when membership type changes"""
        if self.membership_type:
            discount_map = {
                'basic': 5.0,
                'premium': 15.0,
                'vip': 25.0,
            }
            self.discount_percentage = discount_map.get(self.membership_type, 0.0)

    def action_activate(self):
        """Activate the membership"""
        for record in self:
            if record.payment_status != 'paid':
                raise ValidationError(_('Cannot activate membership with pending payment.'))
            record.write({'status': 'active'})
        return True

    def action_cancel(self):
        """Cancel the membership"""
        for record in self:
            record.write({'status': 'cancelled'})
        return True

    def action_renew(self, duration_days=365):
        """
        Renew the membership by extending the end date
        
        :param duration_days: Number of days to extend (default 365)
        :return: True if successful
        """
        self.ensure_one()
        from datetime import timedelta
        
        if self.end_date:
            new_end_date = self.end_date + timedelta(days=duration_days)
        else:
            new_end_date = fields.Date.context_today(self) + timedelta(days=duration_days)
        
        self.write({
            'end_date': new_end_date,
            'status': 'active',
            'payment_status': 'pending',
        })
        return True

    @api.model
    def _cron_update_expired_memberships(self):
        """Scheduled action to update expired memberships"""
        today = fields.Date.context_today(self)
        expired_memberships = self.search([
            ('status', '=', 'active'),
            ('end_date', '<', today),
        ])
        expired_memberships.write({'status': 'expired'})
        return True

    def name_get(self):
        result = []
        for record in self:
            name = "{} - {} ({})".format(
                record.member_id.name if record.member_id else 'N/A',
                record.membership_type.capitalize() if record.membership_type else 'N/A',
                record.status.capitalize() if record.status else 'N/A'
            )
            result.append((record.id, name))
        return result
