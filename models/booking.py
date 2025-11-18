# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta
from odoo.tools import float_round
import pytz
import logging

_logger = logging.getLogger(__name__)


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
        """
        Calculate hours between start_datetime and end_datetime.
        Handles timezone conversions properly to ensure accurate duration calculation.
        The field is stored in the database for performance optimization.
        """
        for record in self:
            if record.start_datetime and record.end_datetime:
                # Get user timezone or default to UTC
                tz_name = self.env.user.tz or 'UTC'
                user_tz = pytz.timezone(tz_name)
                
                # Convert datetime to user timezone for accurate calculation
                # Odoo stores datetime in UTC, so we need to localize properly
                start_utc = pytz.UTC.localize(record.start_datetime.replace(tzinfo=None))
                end_utc = pytz.UTC.localize(record.end_datetime.replace(tzinfo=None))
                
                # Convert to user timezone
                start_local = start_utc.astimezone(user_tz)
                end_local = end_utc.astimezone(user_tz)
                
                # Calculate duration in seconds and convert to hours
                delta = end_local - start_local
                duration_hours = delta.total_seconds() / 3600.0
                
                # Round to 2 decimal places for precision
                record.duration = float_round(duration_hours, precision_digits=2)
            else:
                record.duration = 0.0

    @api.depends('duration', 'facility_id', 'facility_id.hourly_rate', 
                 'equipment_ids', 'equipment_ids.rental_rate',
                 'customer_id', 'start_datetime')
    def _compute_total_cost(self):
        """
        Calculate total booking cost including:
        1) Facility hourly rate * duration
        2) Sum of all equipment rental rates * duration
        3) Apply membership discount if customer has active membership
        
        The field is stored in database and handles all edge cases.
        """
        for record in self:
            total = 0.0
            
            # 1) Calculate facility cost (duration * hourly_rate)
            if record.facility_id and record.duration:
                facility_rate = record.facility_id.hourly_rate or 0.0
                total += facility_rate * record.duration
            
            # 2) Add equipment rental costs (sum of rental_rates * duration)
            if record.equipment_ids and record.duration:
                for equipment in record.equipment_ids:
                    equipment_rate = equipment.rental_rate or 0.0
                    total += equipment_rate * record.duration
            
            # 3) Apply membership discount if customer has active membership
            discount_percentage = 0.0
            if record.customer_id and record.start_datetime:
                # Find active membership for the customer at booking start date
                active_membership = self.env['sports.membership'].search([
                    ('member_id', '=', record.customer_id.id),
                    ('status', '=', 'active'),
                    ('start_date', '<=', record.start_datetime.date()),
                    ('end_date', '>=', record.start_datetime.date()),
                    ('payment_status', '=', 'paid'),
                ], limit=1)
                
                if active_membership:
                    discount_percentage = active_membership.discount_percentage or 0.0
            
            # Apply discount to total cost
            if discount_percentage > 0 and total > 0:
                discount_amount = (total * discount_percentage) / 100.0
                total = total - discount_amount
            
            # Ensure total is never negative and round to 2 decimal places
            record.total_cost = float_round(max(0.0, total), precision_digits=2)

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
        """
        Confirm the booking:
        - Validate availability
        - Set status to 'confirmed'
        - Decrease equipment quantity_available for each equipment
        - Send confirmation email using mail template
        """
        for record in self:
            # Validate current status
            if record.status != 'draft':
                raise ValidationError(_('Only draft bookings can be confirmed.'))
            
            # Validate facility availability (double-check)
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
                        'Facility is no longer available for this time slot. '
                        'Please refresh and select a different time.'
                    ))
            
            # Checkout equipment - decrease available quantity
            equipment_checkout_errors = []
            for equipment in record.equipment_ids:
                try:
                    equipment.checkout_equipment(quantity=1)
                except Exception as e:
                    equipment_checkout_errors.append(str(e))
            
            if equipment_checkout_errors:
                raise ValidationError(_(
                    'Equipment checkout failed:\n%s'
                ) % '\n'.join(equipment_checkout_errors))
            
            # Update booking status
            record.write({'status': 'confirmed'})
            
            # Send confirmation email
            try:
                template = self.env.ref('sport_facility_booking_system.email_template_booking_confirmation', 
                                       raise_if_not_found=False)
                if template:
                    template.send_mail(record.id, force_send=True)
            except Exception as e:
                # Log error but don't fail the confirmation
                _logger.warning(
                    'Failed to send booking confirmation email for booking %s: %s',
                    record.booking_reference, str(e)
                )
        
        return True

    def action_complete(self):
        """
        Mark the booking as completed:
        - Set status to 'completed'
        - Restore equipment quantities
        """
        for record in self:
            # Validate current status
            if record.status != 'confirmed':
                raise ValidationError(_('Only confirmed bookings can be completed.'))
            
            # Return equipment - restore available quantity
            equipment_return_errors = []
            for equipment in record.equipment_ids:
                try:
                    equipment.return_equipment(quantity=1)
                except Exception as e:
                    equipment_return_errors.append(str(e))
            
            if equipment_return_errors:
                raise ValidationError(_(
                    'Equipment return failed:\n%s'
                ) % '\n'.join(equipment_return_errors))
            
            # Update booking status
            record.write({'status': 'completed'})
        
        return True

    def action_cancel(self):
        """
        Cancel the booking:
        - Set status to 'cancelled'
        - Restore equipment quantities
        - Handle refund logic
        """
        for record in self:
            # Validate current status
            if record.status == 'completed':
                raise ValidationError(_('Completed bookings cannot be cancelled.'))
            
            # Store original status for refund calculation
            original_status = record.status
            
            # Return equipment if booking was confirmed
            if original_status == 'confirmed':
                equipment_return_errors = []
                for equipment in record.equipment_ids:
                    try:
                        equipment.return_equipment(quantity=1)
                    except Exception as e:
                        equipment_return_errors.append(str(e))
                
                if equipment_return_errors:
                    raise ValidationError(_(
                        'Equipment return failed:\n%s'
                    ) % '\n'.join(equipment_return_errors))
            
            # Calculate refund amount based on cancellation policy
            refund_amount = 0.0
            refund_percentage = 0.0
            
            if original_status == 'confirmed' and record.total_cost > 0:
                # Calculate hours until booking starts
                from datetime import datetime
                now = fields.Datetime.now()
                
                if record.start_datetime > now:
                    hours_until_booking = (record.start_datetime - now).total_seconds() / 3600.0
                    
                    # Refund policy based on cancellation time
                    if hours_until_booking >= 48:
                        refund_percentage = 100.0  # Full refund if cancelled 48+ hours before
                    elif hours_until_booking >= 24:
                        refund_percentage = 50.0   # 50% refund if cancelled 24-48 hours before
                    elif hours_until_booking >= 12:
                        refund_percentage = 25.0   # 25% refund if cancelled 12-24 hours before
                    else:
                        refund_percentage = 0.0    # No refund if cancelled less than 12 hours before
                    
                    refund_amount = (record.total_cost * refund_percentage) / 100.0
            
            # Update booking status and add cancellation note
            cancellation_note = _(
                'Booking cancelled. Refund: %.2f%% (Amount: %.2f %s)'
            ) % (refund_percentage, refund_amount, record.currency_id.name or '')
            
            existing_notes = record.notes or ''
            updated_notes = f"{existing_notes}\n\n{cancellation_note}" if existing_notes else cancellation_note
            
            record.write({
                'status': 'cancelled',
                'notes': updated_notes,
            })
            
            # Send cancellation email
            try:
                template = self.env.ref('sport_facility_booking_system.email_template_booking_cancellation',
                                       raise_if_not_found=False)
                if template:
                    template.send_mail(record.id, force_send=True)
            except Exception as e:
                # Log error but don't fail the cancellation
                _logger.warning(
                    'Failed to send booking cancellation email for booking %s: %s',
                    record.booking_reference, str(e)
                )
        
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
