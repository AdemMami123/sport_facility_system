# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class SportsTimeSlot(models.Model):
    _name = 'sports.timeslot'
    _description = 'Sports Facility Time Slot'
    _order = 'date desc, start_time'

    facility_id = fields.Many2one(
        'sports.facility',
        string='Facility',
        required=True,
        ondelete='cascade',
        help='The facility for this time slot'
    )
    
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
        help='Date of the time slot'
    )
    
    start_time = fields.Float(
        string='Start Time',
        required=True,
        help='Start time in 24-hour format (e.g., 14.5 for 2:30 PM)'
    )
    
    end_time = fields.Float(
        string='End Time',
        required=True,
        help='End time in 24-hour format (e.g., 16.0 for 4:00 PM)'
    )
    
    is_available = fields.Boolean(
        string='Available',
        compute='_compute_is_available',
        store=True,
        help='Whether this time slot is available for booking'
    )
    
    booking_id = fields.Many2one(
        'sports.booking',
        string='Booking',
        ondelete='set null',
        help='Associated booking if this slot is reserved'
    )
    
    duration = fields.Float(
        string='Duration (Hours)',
        compute='_compute_duration',
        store=True,
        help='Duration of the time slot in hours'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to archive the time slot'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    _sql_constraints = [
        ('check_time_range', 'CHECK(end_time > start_time)', 
         'End time must be after start time!'),
        ('check_start_time_valid', 'CHECK(start_time >= 0 AND start_time < 24)', 
         'Start time must be between 0 and 24!'),
        ('check_end_time_valid', 'CHECK(end_time > 0 AND end_time <= 24)', 
         'End time must be between 0 and 24!'),
    ]

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for record in self:
            if record.start_time and record.end_time:
                record.duration = record.end_time - record.start_time
            else:
                record.duration = 0.0

    @api.depends('booking_id', 'date', 'start_time', 'end_time', 'facility_id')
    def _compute_is_available(self):
        for record in self:
            # Not available if there's already a booking assigned
            if record.booking_id:
                record.is_available = False
                continue
            
            # Check if there are any confirmed bookings overlapping this time slot
            if record.facility_id and record.date and record.start_time and record.end_time:
                # Convert date and time to datetime for comparison
                start_datetime = self._convert_to_datetime(record.date, record.start_time)
                end_datetime = self._convert_to_datetime(record.date, record.end_time)
                
                # Search for overlapping bookings
                overlapping_bookings = self.env['sports.booking'].search([
                    ('facility_id', '=', record.facility_id.id),
                    ('status', 'in', ['draft', 'confirmed']),
                    ('start_datetime', '<', end_datetime),
                    ('end_datetime', '>', start_datetime),
                ])
                
                record.is_available = not bool(overlapping_bookings)
            else:
                record.is_available = True

    @api.constrains('facility_id', 'date', 'start_time', 'end_time')
    def _check_no_overlap(self):
        """Prevent overlapping time slots for the same facility on the same date"""
        for record in self:
            if record.facility_id and record.date and record.start_time and record.end_time:
                overlapping_slots = self.search([
                    ('id', '!=', record.id),
                    ('facility_id', '=', record.facility_id.id),
                    ('date', '=', record.date),
                    ('start_time', '<', record.end_time),
                    ('end_time', '>', record.start_time),
                ])
                
                if overlapping_slots:
                    raise ValidationError(_(
                        'This time slot overlaps with an existing slot for the same facility. '
                        'Please choose a different time range.'
                    ))

    @api.constrains('start_time', 'end_time', 'facility_id')
    def _check_within_operating_hours(self):
        """Ensure time slot is within facility operating hours"""
        for record in self:
            if record.facility_id:
                if record.start_time < record.facility_id.operating_hours_start:
                    raise ValidationError(_(
                        'Start time (%s) is before facility operating hours (%s).'
                    ) % (
                        self._float_to_time_string(record.start_time),
                        self._float_to_time_string(record.facility_id.operating_hours_start)
                    ))
                
                if record.end_time > record.facility_id.operating_hours_end:
                    raise ValidationError(_(
                        'End time (%s) is after facility operating hours (%s).'
                    ) % (
                        self._float_to_time_string(record.end_time),
                        self._float_to_time_string(record.facility_id.operating_hours_end)
                    ))

    def _convert_to_datetime(self, date, time_float):
        """Convert date and float time to datetime object"""
        hours = int(time_float)
        minutes = int((time_float - hours) * 60)
        return datetime.combine(date, datetime.min.time()) + timedelta(hours=hours, minutes=minutes)

    def _float_to_time_string(self, time_float):
        """Convert float time to string format (HH:MM)"""
        hours = int(time_float)
        minutes = int((time_float - hours) * 60)
        return f"{hours:02d}:{minutes:02d}"

    @api.model
    def get_available_slots(self, facility_id, date, duration=1.0):
        """
        Get all available time slots for a facility on a specific date
        
        :param facility_id: ID of the facility
        :param date: Date to check
        :param duration: Minimum duration required (in hours)
        :return: Recordset of available time slots
        """
        slots = self.search([
            ('facility_id', '=', facility_id),
            ('date', '=', date),
            ('is_available', '=', True),
            ('duration', '>=', duration),
        ])
        return slots

    def book_slot(self, booking_id):
        """
        Book this time slot by associating it with a booking
        
        :param booking_id: ID of the booking
        :return: True if successful
        """
        self.ensure_one()
        
        if not self.is_available:
            raise ValidationError(_('This time slot is not available for booking.'))
        
        self.booking_id = booking_id
        return True

    def release_slot(self):
        """Release this time slot by removing the booking association"""
        self.ensure_one()
        self.booking_id = False
        return True

    def name_get(self):
        result = []
        for record in self:
            name = "{} - {} ({} - {})".format(
                record.facility_id.name if record.facility_id else 'N/A',
                record.date.strftime('%Y-%m-%d') if record.date else 'N/A',
                record._float_to_time_string(record.start_time),
                record._float_to_time_string(record.end_time)
            )
            result.append((record.id, name))
        return result
