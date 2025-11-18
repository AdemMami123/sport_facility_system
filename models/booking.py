# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class SportsBooking(models.Model):
    _name = 'sports.booking'
    _description = 'Sports Facility Booking'
    _order = 'start_datetime desc'
    _rec_name = 'booking_reference'

    booking_reference = fields.Char(
        string='Booking Reference',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New'),
        help='Auto-generated booking reference number'
    )
    
    facility_id = fields.Many2one(
        'sports.facility',
        string='Facility',
        required=True,
        ondelete='restrict',
        help='The facility being booked'
    )
    
    customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        ondelete='restrict',
        help='Customer making the booking'
    )
    
    start_datetime = fields.Datetime(
        string='Start Date & Time',
        required=True,
        help='Booking start date and time'
    )
    
    end_datetime = fields.Datetime(
        string='End Date & Time',
        required=True,
        help='Booking end date and time'
    )
    
    duration = fields.Float(
        string='Duration (Hours)',
        compute='_compute_duration',
        store=True,
        help='Duration of the booking in hours'
    )
    
    total_cost = fields.Float(
        string='Total Cost',
        compute='_compute_total_cost',
        store=True,
        digits='Product Price',
        help='Total cost of the booking'
    )
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True,
       help='Current status of the booking')
    
    equipment_ids = fields.Many2many(
        'sports.equipment',
        'sports_booking_equipment_rel',
        'booking_id',
        'equipment_id',
        string='Equipment',
        help='Additional equipment requested for this booking'
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes or special requests'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to archive the booking'
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

    @api.model
    def create(self, vals):
        if vals.get('booking_reference', _('New')) == _('New'):
            vals['booking_reference'] = self.env['ir.sequence'].next_by_code('sports.booking') or _('New')
        return super(SportsBooking, self).create(vals)

    @api.depends('start_datetime', 'end_datetime')
    def _compute_duration(self):
        for record in self:
            if record.start_datetime and record.end_datetime:
                delta = record.end_datetime - record.start_datetime
                record.duration = delta.total_seconds() / 3600.0
            else:
                record.duration = 0.0

    @api.depends('duration', 'facility_id', 'facility_id.hourly_rate', 'equipment_ids', 'equipment_ids.rental_rate')
    def _compute_total_cost(self):
        for record in self:
            total = 0.0
            # Calculate facility cost
            if record.facility_id and record.duration:
                total += record.facility_id.hourly_rate * record.duration
            
            # Add equipment rental costs
            for equipment in record.equipment_ids:
                if equipment.rental_rate:
                    total += equipment.rental_rate * record.duration
            
            record.total_cost = total

    @api.constrains('start_datetime', 'end_datetime')
    def _check_dates(self):
        for record in self:
            if record.start_datetime and record.end_datetime:
                if record.end_datetime <= record.start_datetime:
                    raise ValidationError(_('End date must be after start date.'))

    @api.constrains('start_datetime', 'end_datetime', 'facility_id')
    def _check_booking_overlap(self):
        for record in self:
            if record.facility_id and record.start_datetime and record.end_datetime:
                overlapping = self.search([
                    ('id', '!=', record.id),
                    ('facility_id', '=', record.facility_id.id),
                    ('status', 'in', ['draft', 'confirmed']),
                    ('start_datetime', '<', record.end_datetime),
                    ('end_datetime', '>', record.start_datetime),
                ])
                if overlapping:
                    raise ValidationError(_(
                        'This facility is already booked for the selected time period. '
                        'Please choose a different time slot or facility.'
                    ))

    def action_confirm(self):
        """Confirm the booking"""
        for record in self:
            if record.status != 'draft':
                raise ValidationError(_('Only draft bookings can be confirmed.'))
            record.write({'status': 'confirmed'})
        return True

    def action_complete(self):
        """Mark the booking as completed"""
        for record in self:
            if record.status != 'confirmed':
                raise ValidationError(_('Only confirmed bookings can be completed.'))
            record.write({'status': 'completed'})
        return True

    def action_cancel(self):
        """Cancel the booking"""
        for record in self:
            if record.status == 'completed':
                raise ValidationError(_('Completed bookings cannot be cancelled.'))
            record.write({'status': 'cancelled'})
        return True

    def action_reset_to_draft(self):
        """Reset booking to draft status"""
        for record in self:
            if record.status == 'completed':
                raise ValidationError(_('Completed bookings cannot be reset to draft.'))
            record.write({'status': 'draft'})
        return True

    def name_get(self):
        result = []
        for record in self:
            name = f"{record.booking_reference} - {record.facility_id.name if record.facility_id else 'N/A'}"
            result.append((record.id, name))
        return result
