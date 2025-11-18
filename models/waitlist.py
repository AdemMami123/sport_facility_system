# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class SportsWaitlist(models.Model):
    _name = 'sports.waitlist'
    _description = 'Sports Facility Waitlist'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date asc'  # FIFO processing
    _rec_name = 'customer_id'

    customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Customer requesting to be notified when facility becomes available'
    )
    
    facility_id = fields.Many2one(
        'sports.facility',
        string='Facility',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Facility the customer is waiting for'
    )
    
    preferred_date = fields.Date(
        string='Preferred Date',
        tracking=True,
        help='Customer\'s preferred booking date (optional)'
    )
    
    preferred_time_start = fields.Float(
        string='Preferred Start Time',
        widget='float_time',
        tracking=True,
        help='Customer\'s preferred start time in 24-hour format (e.g., 14.5 = 14:30)'
    )
    
    preferred_time_end = fields.Float(
        string='Preferred End Time',
        widget='float_time',
        tracking=True,
        help='Customer\'s preferred end time in 24-hour format (e.g., 16.0 = 16:00)'
    )
    
    status = fields.Selection(
        selection=[
            ('waiting', 'Waiting'),
            ('notified', 'Notified'),
            ('booked', 'Booked'),
            ('expired', 'Expired'),
        ],
        string='Status',
        default='waiting',
        required=True,
        tracking=True,
        help='Current status of the waitlist entry'
    )
    
    notification_sent = fields.Boolean(
        string='Notification Sent',
        default=False,
        tracking=True,
        help='Indicates whether the customer has been notified of availability'
    )
    
    create_date = fields.Datetime(
        string='Request Date',
        readonly=True,
        help='Date and time when the waitlist entry was created'
    )
    
    # Additional helpful fields
    customer_email = fields.Char(
        string='Customer Email',
        related='customer_id.email',
        readonly=True,
        help='Customer email for notifications'
    )
    
    customer_phone = fields.Char(
        string='Customer Phone',
        related='customer_id.phone',
        readonly=True,
        help='Customer phone for notifications'
    )
    
    facility_name = fields.Char(
        string='Facility Name',
        related='facility_id.name',
        readonly=True,
        store=True,
        help='Facility name for easy reference'
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes or special requirements'
    )
    
    # Constraints
    @api.constrains('preferred_time_start', 'preferred_time_end')
    def _check_time_validity(self):
        """Validate that preferred times are valid and end time is after start time."""
        for record in self:
            if record.preferred_time_start or record.preferred_time_end:
                # Validate time range (0-24)
                if record.preferred_time_start and (record.preferred_time_start < 0 or record.preferred_time_start >= 24):
                    raise ValidationError(_(
                        'Preferred start time must be between 00:00 and 23:59. '
                        'Current value: %.2f'
                    ) % record.preferred_time_start)
                
                if record.preferred_time_end and (record.preferred_time_end < 0 or record.preferred_time_end > 24):
                    raise ValidationError(_(
                        'Preferred end time must be between 00:00 and 24:00. '
                        'Current value: %.2f'
                    ) % record.preferred_time_end)
                
                # Validate end time is after start time
                if record.preferred_time_start and record.preferred_time_end:
                    if record.preferred_time_end <= record.preferred_time_start:
                        raise ValidationError(_(
                            'Preferred end time (%.2f) must be after start time (%.2f).'
                        ) % (record.preferred_time_end, record.preferred_time_start))
    
    @api.constrains('preferred_date')
    def _check_preferred_date(self):
        """Validate that preferred date is not in the past."""
        for record in self:
            if record.preferred_date:
                today = fields.Date.today()
                if record.preferred_date < today:
                    raise ValidationError(_(
                        'Preferred date cannot be in the past. '
                        'Selected date: %s, Today: %s'
                    ) % (record.preferred_date, today))
    
    # Business logic methods
    def action_notify_customer(self):
        """
        Mark the waitlist entry as notified and send notification to customer.
        Can be called manually or automatically when a slot becomes available.
        """
        for record in self:
            if record.status != 'waiting':
                raise ValidationError(_(
                    'Only waitlist entries with status "Waiting" can be notified. '
                    'Current status: %s'
                ) % dict(record._fields['status'].selection).get(record.status))
            
            # Update status
            record.write({
                'status': 'notified',
                'notification_sent': True,
            })
            
            # Send email notification (template to be created)
            try:
                template = self.env.ref('sport_facility_system.email_template_waitlist_notification', 
                                       raise_if_not_found=False)
                if template:
                    template.send_mail(record.id, force_send=True)
                    _logger.info(
                        'Waitlist notification email sent to %s for facility %s',
                        record.customer_id.name, record.facility_id.name
                    )
            except Exception as e:
                _logger.error(
                    'Failed to send waitlist notification email to %s: %s',
                    record.customer_id.name, str(e)
                )
        
        return True
    
    def action_mark_booked(self):
        """
        Mark the waitlist entry as booked when customer completes a booking.
        Should be called when a booking is confirmed for this customer/facility.
        """
        for record in self:
            if record.status not in ['waiting', 'notified']:
                raise ValidationError(_(
                    'Only waitlist entries with status "Waiting" or "Notified" can be marked as booked.'
                ))
            
            record.write({'status': 'booked'})
            _logger.info(
                'Waitlist entry marked as booked for customer %s, facility %s',
                record.customer_id.name, record.facility_id.name
            )
        
        return True
    
    def action_mark_expired(self):
        """
        Mark the waitlist entry as expired.
        Can be called manually or by scheduled action for old entries.
        """
        for record in self:
            record.write({'status': 'expired'})
            _logger.info(
                'Waitlist entry marked as expired for customer %s, facility %s',
                record.customer_id.name, record.facility_id.name
            )
        
        return True
    
    @api.model
    def _cron_expire_old_waitlist_entries(self):
        """
        Scheduled action to automatically expire old waitlist entries.
        Expires entries that are:
        - Status 'notified' for more than 48 hours
        - Status 'waiting' with preferred_date in the past
        """
        from datetime import datetime, timedelta
        
        # Expire notified entries older than 48 hours
        expiry_time = datetime.now() - timedelta(hours=48)
        notified_expired = self.search([
            ('status', '=', 'notified'),
            ('write_date', '<', expiry_time),
        ])
        
        if notified_expired:
            notified_expired.action_mark_expired()
            _logger.info(
                'Expired %d notified waitlist entries (no response after 48 hours)',
                len(notified_expired)
            )
        
        # Expire waiting entries with past preferred dates
        today = fields.Date.today()
        past_date_expired = self.search([
            ('status', '=', 'waiting'),
            ('preferred_date', '!=', False),
            ('preferred_date', '<', today),
        ])
        
        if past_date_expired:
            past_date_expired.action_mark_expired()
            _logger.info(
                'Expired %d waiting waitlist entries (preferred date passed)',
                len(past_date_expired)
            )
        
        return True
    
    @api.model
    def get_waiting_customers_for_facility(self, facility_id, date=None, time_start=None, time_end=None):
        """
        Get list of customers waiting for a specific facility.
        Optionally filter by preferred date and time range.
        Returns recordset ordered by FIFO (create_date).
        
        :param facility_id: ID of the facility
        :param date: Optional date to match preferred_date
        :param time_start: Optional start time to check overlap
        :param time_end: Optional end time to check overlap
        :return: Recordset of sports.waitlist entries
        """
        domain = [
            ('facility_id', '=', facility_id),
            ('status', '=', 'waiting'),
        ]
        
        # Filter by preferred date if provided
        if date:
            domain.append(('preferred_date', '=', date))
        
        # Filter by time range if provided (check for overlap)
        if time_start is not None and time_end is not None:
            # Find entries where preferred times overlap with available slot
            # Overlap occurs when: start < preferred_end AND end > preferred_start
            domain.extend([
                ('preferred_time_start', '!=', False),
                ('preferred_time_end', '!=', False),
                ('preferred_time_start', '<', time_end),
                ('preferred_time_end', '>', time_start),
            ])
        
        # Search and return ordered by create_date (FIFO)
        return self.search(domain)
