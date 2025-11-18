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
    def validate_booking_dates(self):
        """Ensure end_datetime is after start_datetime"""
        for record in self:
            if record.start_datetime and record.end_datetime:
                if record.end_datetime <= record.start_datetime:
                    raise ValidationError(_(
                        'Invalid booking dates: End date and time must be after start date and time.\n'
                        'Start: %s\n'
                        'End: %s'
                    ) % (record.start_datetime, record.end_datetime))

    @api.constrains('start_datetime', 'end_datetime', 'facility_id', 'status')
    def check_facility_availability(self):
        """Prevent double booking by checking overlapping bookings for same facility"""
        for record in self:
            if record.facility_id and record.start_datetime and record.end_datetime:
                # Only check for active bookings (not cancelled)
                overlapping = self.search([
                    ('id', '!=', record.id),
                    ('facility_id', '=', record.facility_id.id),
                    ('status', 'in', ['draft', 'confirmed']),
                    ('start_datetime', '<', record.end_datetime),
                    ('end_datetime', '>', record.start_datetime),
                ])
                if overlapping:
                    overlapping_booking = overlapping[0]
                    raise ValidationError(_(
                        'Facility "%s" is not available for the selected time period.\n\n'
                        'Conflicting booking: %s\n'
                        'Time: %s to %s\n\n'
                        'Please choose a different time slot or facility.'
                    ) % (
                        record.facility_id.name,
                        overlapping_booking.booking_reference,
                        overlapping_booking.start_datetime,
                        overlapping_booking.end_datetime
                    ))

    @api.constrains('start_datetime', 'end_datetime', 'facility_id')
    def validate_operating_hours(self):
        """Ensure booking times are within facility operating hours"""
        for record in self:
            if record.facility_id and record.start_datetime and record.end_datetime:
                # Extract time from datetime
                start_time = record.start_datetime.hour + record.start_datetime.minute / 60.0
                end_time = record.end_datetime.hour + record.end_datetime.minute / 60.0
                
                operating_start = record.facility_id.operating_hours_start
                operating_end = record.facility_id.operating_hours_end
                
                # Check if booking is on the same day
                if record.start_datetime.date() == record.end_datetime.date():
                    # Single day booking
                    if start_time < operating_start:
                        raise ValidationError(_(
                            'Booking start time (%02d:%02d) is before facility operating hours.\n'
                            'Facility "%s" opens at %02d:%02d.'
                        ) % (
                            record.start_datetime.hour,
                            record.start_datetime.minute,
                            record.facility_id.name,
                            int(operating_start),
                            int((operating_start % 1) * 60)
                        ))
                    
                    if end_time > operating_end:
                        raise ValidationError(_(
                            'Booking end time (%02d:%02d) is after facility operating hours.\n'
                            'Facility "%s" closes at %02d:%02d.'
                        ) % (
                            record.end_datetime.hour,
                            record.end_datetime.minute,
                            record.facility_id.name,
                            int(operating_end),
                            int((operating_end % 1) * 60)
                        ))
                else:
                    # Multi-day booking - check first and last day
                    if start_time < operating_start:
                        raise ValidationError(_(
                            'Booking start time (%02d:%02d) is before facility operating hours.\n'
                            'Facility "%s" opens at %02d:%02d.'
                        ) % (
                            record.start_datetime.hour,
                            record.start_datetime.minute,
                            record.facility_id.name,
                            int(operating_start),
                            int((operating_start % 1) * 60)
                        ))
                    
                    if end_time > operating_end:
                        raise ValidationError(_(
                            'Booking end time (%02d:%02d) is after facility operating hours.\n'
                            'Facility "%s" closes at %02d:%02d.'
                        ) % (
                            record.end_datetime.hour,
                            record.end_datetime.minute,
                            record.facility_id.name,
                            int(operating_end),
                            int((operating_end % 1) * 60)
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
