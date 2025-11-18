# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from odoo.tools import float_round
import pytz
import logging

_logger = logging.getLogger(__name__)


class SportsBooking(models.Model):
    _name = 'sports.booking'
    _description = 'Sports Facility Booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
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
        tracking=True,
        help='The facility being booked'
    )
    
    customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        ondelete='restrict',
        tracking=True,
        help='Customer making the booking'
    )
    
    start_datetime = fields.Datetime(
        string='Start Date & Time',
        required=True,
        tracking=True,
        help='Booking start date and time'
    )
    
    end_datetime = fields.Datetime(
        string='End Date & Time',
        required=True,
        tracking=True,
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
        groups='sport_facility_system.group_sports_manager',
        help='Total cost of the booking'
    )
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True,
       groups='sport_facility_system.group_sports_manager',
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
    
    # Recurrence fields
    is_recurring = fields.Boolean(
        string='Recurring Booking',
        default=False,
        help='Enable to create recurring bookings'
    )
    
    recurrence_type = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ], string='Recurrence Type',
       help='Frequency of recurring bookings')
    
    recurrence_count = fields.Integer(
        string='Number of Occurrences',
        default=1,
        help='How many times this booking should repeat'
    )
    
    recurrence_end_date = fields.Date(
        string='Recurrence End Date',
        help='Alternative to count - bookings will be created until this date'
    )
    
    parent_booking_id = fields.Many2one(
        'sports.booking',
        string='Parent Booking',
        ondelete='cascade',
        index=True,
        help='Original booking that generated this recurring booking'
    )
    
    child_booking_ids = fields.One2many(
        'sports.booking',
        'parent_booking_id',
        string='Child Bookings',
        help='Bookings created from this recurring booking'
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
            
            # Send confirmation email after status change
            try:
                template = self.env.ref('sport_facility_system.email_template_booking_confirmation', 
                                       raise_if_not_found=False)
                if template:
                    template.send_mail(record.id, force_send=True)
                    _logger.info(
                        'Booking confirmation email sent successfully for booking %s',
                        record.booking_reference
                    )
            except Exception as e:
                # Log error but don't fail the confirmation
                _logger.error(
                    'Failed to send booking confirmation email for booking %s: %s',
                    record.booking_reference, str(e)
                )
            
            # Generate recurring bookings if enabled
            if record.is_recurring:
                try:
                    record.generate_recurring_bookings()
                    _logger.info(
                        'Recurring bookings generated successfully for booking %s',
                        record.booking_reference
                    )
                except Exception as e:
                    _logger.error(
                        'Failed to generate recurring bookings for booking %s: %s',
                        record.booking_reference, str(e)
                    )
                    # Don't fail the confirmation, but inform the user
                    raise UserError(_(
                        'Booking confirmed successfully, but recurring bookings could not be created: %s'
                    ) % str(e))
        
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
                template = self.env.ref('sport_facility_system.email_template_booking_cancellation', 
                                       raise_if_not_found=False)
                if template:
                    template.send_mail(record.id, force_send=True)
                    _logger.info(
                        'Booking cancellation email sent successfully for booking %s',
                        record.booking_reference
                    )
            except Exception as e:
                # Log error but don't fail the cancellation
                _logger.error(
                    'Failed to send booking cancellation email for booking %s: %s',
                    record.booking_reference, str(e)
                )
            
            # Auto-assign from waitlist if facility slot becomes available
            try:
                record.auto_assign_from_waitlist()
            except Exception as e:
                # Log error but don't fail the cancellation
                _logger.error(
                    'Failed to auto-assign from waitlist for booking %s: %s',
                    record.booking_reference, str(e)
                )
        
        return True
    
    def auto_assign_from_waitlist(self):
        """
        Automatically notify customers on waitlist when a booking is cancelled.
        Called from action_cancel() to offer the slot to waiting customers.
        
        Search criteria:
        - Same facility as cancelled booking
        - Preferred date within ±2 days of cancelled booking start date
        - Status 'waiting'
        - FIFO order (oldest request first)
        """
        self.ensure_one()
        
        # Only process for confirmed bookings that are being cancelled
        if not self.facility_id or not self.start_datetime:
            return
        
        # Get the booking date (not datetime) for comparison
        booking_date = self.start_datetime.date()
        
        # Calculate date range: ±2 days
        from datetime import timedelta as td
        date_min = booking_date - td(days=2)
        date_max = booking_date + td(days=2)
        
        # Search for waiting customers
        Waitlist = self.env['sports.waitlist']
        waiting_customers = Waitlist.search([
            ('facility_id', '=', self.facility_id.id),
            ('status', '=', 'waiting'),
            '|',
            ('preferred_date', '=', False),  # Include customers without specific date preference
            '&',
            ('preferred_date', '>=', date_min),
            ('preferred_date', '<=', date_max),
        ], order='create_date asc', limit=1)
        
        if not waiting_customers:
            _logger.info(
                'No waitlist customers found for facility %s on date %s (±2 days)',
                self.facility_id.name, booking_date
            )
            return
        
        waitlist_entry = waiting_customers[0]
        
        # Build pre-filled booking URL parameters
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        booking_url = f"{base_url}/sports/booking/create"
        
        # Add URL parameters for pre-filling the booking form
        url_params = [
            f"facility_id={self.facility_id.id}",
            f"customer_id={waitlist_entry.customer_id.id}",
            f"date={booking_date.strftime('%Y-%m-%d')}",
        ]
        
        # Add time parameters if available from cancelled booking
        if self.start_datetime:
            start_time = self.start_datetime.hour + (self.start_datetime.minute / 60.0)
            url_params.append(f"start_time={start_time}")
        
        if self.end_datetime:
            end_time = self.end_datetime.hour + (self.end_datetime.minute / 60.0)
            url_params.append(f"end_time={end_time}")
        
        # Construct full URL
        full_booking_url = f"{booking_url}?{'&'.join(url_params)}"
        
        # Update waitlist entry status
        waitlist_entry.write({
            'status': 'notified',
            'notification_sent': True,
        })
        
        # Send notification email with booking link
        try:
            # Try to use email template if it exists
            template = self.env.ref('sport_facility_system.email_template_waitlist_notification', 
                                   raise_if_not_found=False)
            
            if template:
                # Add booking URL to template context
                ctx = dict(self.env.context)
                ctx.update({
                    'booking_url': full_booking_url,
                    'cancelled_booking': self,
                    'booking_date': booking_date,
                    'start_time': self.start_datetime.strftime('%H:%M') if self.start_datetime else '',
                    'end_time': self.end_datetime.strftime('%H:%M') if self.end_datetime else '',
                })
                template.with_context(ctx).send_mail(waitlist_entry.id, force_send=True)
            else:
                # Fallback: send simple email if template doesn't exist
                mail_values = {
                    'subject': _('Facility Available - %s') % self.facility_id.name,
                    'body_html': _(
                        '<p>Dear %s,</p>'
                        '<p>Good news! The facility <strong>%s</strong> is now available for booking on <strong>%s</strong>.</p>'
                        '<p>This slot became available due to a cancellation. '
                        'Please book as soon as possible as it is offered on a first-come, first-served basis.</p>'
                        '<p><a href="%s" style="background-color: #28a745; color: white; padding: 10px 20px; '
                        'text-decoration: none; border-radius: 5px; display: inline-block;">'
                        'Book Now</a></p>'
                        '<p>If you are no longer interested, please disregard this email.</p>'
                        '<p>Best regards,<br/>Sports Booking Team</p>'
                    ) % (
                        waitlist_entry.customer_id.name,
                        self.facility_id.name,
                        booking_date.strftime('%B %d, %Y'),
                        full_booking_url
                    ),
                    'email_to': waitlist_entry.customer_email,
                    'email_from': self.env.user.email or 'noreply@example.com',
                }
                self.env['mail.mail'].create(mail_values).send()
            
            _logger.info(
                'Waitlist notification sent to %s for facility %s on %s (booking URL: %s)',
                waitlist_entry.customer_id.name,
                self.facility_id.name,
                booking_date,
                full_booking_url
            )
            
        except Exception as e:
            # Log error but don't fail - waitlist entry status already updated
            _logger.error(
                'Failed to send waitlist notification email to %s: %s',
                waitlist_entry.customer_id.name, str(e)
            )
        
        return waitlist_entry
    
    def generate_recurring_bookings(self):
        """
        Generate child bookings based on recurrence settings.
        Called automatically from action_confirm() when is_recurring=True.
        
        Creates a series of bookings with the same facility, customer, equipment,
        and time slots but on different dates according to recurrence_type.
        """
        self.ensure_one()
        
        # Validation: Check if recurring is enabled
        if not self.is_recurring:
            raise ValidationError(_(
                'Cannot generate recurring bookings: is_recurring is not enabled.'
            ))
        
        # Validation: Check if recurrence type is set
        if not self.recurrence_type:
            raise ValidationError(_(
                'Cannot generate recurring bookings: recurrence_type must be set '
                '(daily, weekly, or monthly).'
            ))
        
        # Validation: Check if at least one stop condition is set
        if not self.recurrence_count and not self.recurrence_end_date:
            raise ValidationError(_(
                'Cannot generate recurring bookings: either recurrence_count or '
                'recurrence_end_date must be specified.'
            ))
        
        # Calculate duration for consistent booking length
        booking_duration = self.duration
        
        # Track created bookings
        created_bookings = self.env['sports.booking']
        failed_bookings = []
        
        # Starting point for next occurrence
        current_start = self.start_datetime
        current_end = self.end_datetime
        occurrence_count = 0
        
        # Loop to create recurring bookings
        while True:
            # Calculate next occurrence date
            if self.recurrence_type == 'daily':
                current_start = current_start + timedelta(days=1)
                current_end = current_end + timedelta(days=1)
            elif self.recurrence_type == 'weekly':
                current_start = current_start + timedelta(days=7)
                current_end = current_end + timedelta(days=7)
            elif self.recurrence_type == 'monthly':
                current_start = current_start + relativedelta(months=1)
                current_end = current_end + relativedelta(months=1)
            else:
                raise ValidationError(_(
                    'Invalid recurrence_type: %s. Must be daily, weekly, or monthly.'
                ) % self.recurrence_type)
            
            occurrence_count += 1
            
            # Check stop conditions
            if self.recurrence_count and occurrence_count >= self.recurrence_count:
                break
            
            if self.recurrence_end_date:
                # Convert datetime to date for comparison
                next_booking_date = current_start.date()
                if next_booking_date > self.recurrence_end_date:
                    break
            
            # Prepare child booking values
            booking_vals = {
                'facility_id': self.facility_id.id,
                'customer_id': self.customer_id.id,
                'start_datetime': current_start,
                'end_datetime': current_end,
                'equipment_ids': [(6, 0, self.equipment_ids.ids)],
                'status': 'draft',  # Child bookings start as draft
                'notes': _('Recurring booking (Occurrence %d) generated from %s') % (
                    occurrence_count, self.booking_reference
                ),
                'parent_booking_id': self.id,
                'is_recurring': False,  # Child bookings are not themselves recurring
            }
            
            try:
                # Check if slot is available before creating
                overlapping = self.search([
                    ('facility_id', '=', self.facility_id.id),
                    ('status', 'in', ['draft', 'confirmed']),
                    ('start_datetime', '<', current_end),
                    ('end_datetime', '>', current_start),
                ])
                
                if overlapping:
                    failed_bookings.append({
                        'occurrence': occurrence_count,
                        'date': current_start,
                        'reason': _('Facility not available - conflicts with booking %s') % 
                                 overlapping[0].booking_reference
                    })
                    _logger.warning(
                        'Skipping recurring booking occurrence %d for %s: slot not available',
                        occurrence_count, self.booking_reference
                    )
                    continue
                
                # Create the child booking
                child_booking = self.create(booking_vals)
                created_bookings |= child_booking
                
                _logger.info(
                    'Created recurring booking %s (occurrence %d) from parent %s',
                    child_booking.booking_reference, occurrence_count, self.booking_reference
                )
                
            except Exception as e:
                failed_bookings.append({
                    'occurrence': occurrence_count,
                    'date': current_start,
                    'reason': str(e)
                })
                _logger.error(
                    'Failed to create recurring booking occurrence %d for %s: %s',
                    occurrence_count, self.booking_reference, str(e)
                )
        
        # Log summary
        _logger.info(
            'Recurring booking generation complete for %s: %d created, %d failed',
            self.booking_reference, len(created_bookings), len(failed_bookings)
        )
        
        # If all bookings failed, raise error
        if not created_bookings and failed_bookings:
            failure_details = '\n'.join([
                _('Occurrence %d (%s): %s') % (
                    fb['occurrence'], 
                    fb['date'].strftime('%Y-%m-%d %H:%M'),
                    fb['reason']
                )
                for fb in failed_bookings[:5]  # Show first 5 failures
            ])
            raise UserError(_(
                'Failed to create any recurring bookings. Details:\n%s%s'
            ) % (failure_details, '\n...' if len(failed_bookings) > 5 else ''))
        
        # If some bookings failed, add note to parent
        if failed_bookings:
            failure_summary = _('\nRecurring Booking Generation: %d created, %d failed') % (
                len(created_bookings), len(failed_bookings)
            )
            self.write({'notes': (self.notes or '') + failure_summary})
        
        return created_bookings    def action_reset_to_draft(self):
        """Reset booking to draft status"""
        for record in self:
            if record.status == 'completed':
                raise ValidationError(_('Completed bookings cannot be reset to draft.'))
            record.write({'status': 'draft'})
        return True

    @api.model
    def _cron_send_booking_reminders(self):
        """
        Scheduled action to send booking reminders for bookings happening in the next 24 hours
        Runs daily at 9:00 AM
        """
        from datetime import datetime
        
        # Calculate time range: now to now + 24 hours
        now = fields.Datetime.now()
        tomorrow = now + timedelta(hours=24)
        
        # Search for confirmed bookings starting in the next 24 hours
        upcoming_bookings = self.env['sports.booking'].search([
            ('start_datetime', '>=', now),
            ('start_datetime', '<=', tomorrow),
            ('status', '=', 'confirmed'),
        ])
        
        _logger.info(
            'Booking reminder cron started. Found %d bookings in the next 24 hours',
            len(upcoming_bookings)
        )
        
        # Send reminder email to each booking
        reminder_count = 0
        error_count = 0
        
        for booking in upcoming_bookings:
            try:
                template = self.env.ref('sport_facility_system.email_template_booking_reminder', 
                                       raise_if_not_found=False)
                if template:
                    template.send_mail(booking.id, force_send=True)
                    reminder_count += 1
                    _logger.info(
                        'Reminder email sent for booking %s (Customer: %s, Facility: %s, Start: %s)',
                        booking.booking_reference,
                        booking.customer_id.name,
                        booking.facility_id.name,
                        booking.start_datetime
                    )
                else:
                    _logger.warning('Reminder email template not found')
                    error_count += 1
            except Exception as e:
                error_count += 1
                _logger.error(
                    'Failed to send reminder email for booking %s: %s',
                    booking.booking_reference,
                    str(e)
                )
        
        _logger.info(
            'Booking reminder cron completed. Sent: %d, Errors: %d, Total: %d',
            reminder_count,
            error_count,
            len(upcoming_bookings)
        )
        
        return True

    @api.model
    def _cron_archive_expired_bookings(self):
        """
        Scheduled action to archive old completed bookings (older than 30 days)
        Runs daily to keep the active booking list clean
        """
        from datetime import datetime
        
        # Calculate the cutoff date: 30 days ago from now
        now = fields.Datetime.now()
        cutoff_date = now - timedelta(days=30)
        
        # Search for completed bookings older than 30 days
        expired_bookings = self.env['sports.booking'].search([
            ('status', '=', 'completed'),
            ('end_datetime', '<', cutoff_date),
            ('active', '=', True),
        ])
        
        _logger.info(
            'Archive expired bookings cron started. Found %d bookings to archive',
            len(expired_bookings)
        )
        
        # Archive the bookings by setting active=False
        archived_count = 0
        error_count = 0
        
        for booking in expired_bookings:
            try:
                booking.write({'active': False})
                archived_count += 1
                _logger.debug(
                    'Archived booking %s (Customer: %s, End Date: %s)',
                    booking.booking_reference,
                    booking.customer_id.name,
                    booking.end_datetime
                )
            except Exception as e:
                error_count += 1
                _logger.error(
                    'Failed to archive booking %s: %s',
                    booking.booking_reference,
                    str(e)
                )
        
        _logger.info(
            'Archive expired bookings cron completed. Archived: %d, Errors: %d, Total: %d',
            archived_count,
            error_count,
            len(expired_bookings)
        )
        
        return True

    def name_get(self):
        result = []
        for record in self:
            name = f"{record.booking_reference} - {record.facility_id.name if record.facility_id else 'N/A'}"
            result.append((record.id, name))
        return result
