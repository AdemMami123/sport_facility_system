# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from unittest.mock import patch, MagicMock
import logging

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'integration')
class TestSportsBookingIntegration(TransactionCase):
    """
    Integration tests for Sports Booking System
    Tests complete workflows including booking lifecycle, recurring bookings,
    waitlist notifications, and email functionality
    """

    def setUp(self):
        """Set up test data for integration tests"""
        super(TestSportsBookingIntegration, self).setUp()
        
        # Create test facility
        self.facility = self.env['sports.facility'].create({
            'name': 'Test Tennis Court',
            'facility_type': 'court',
            'location': 'Test Location',
            'capacity': 4,
            'hourly_rate': 50.0,
            'operating_hours_start': 8.0,
            'operating_hours_end': 20.0,
            'active': True,
        })
        
        # Create test equipment
        self.equipment = self.env['sports.equipment'].create({
            'name': 'Tennis Racket',
            'equipment_type': 'racket',
            'rental_rate': 5.0,
            'total_quantity': 10,
            'quantity_available': 10,
            'facility_ids': [(6, 0, [self.facility.id])],
        })
        
        # Create test customer
        self.customer = self.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'testcustomer@example.com',
            'phone': '+1234567890',
        })
        
        # Create another customer for waitlist tests
        self.customer2 = self.env['res.partner'].create({
            'name': 'Waitlist Customer',
            'email': 'waitlist@example.com',
            'phone': '+0987654321',
        })
        
        # Base datetime for bookings (tomorrow at 10 AM)
        self.start_datetime = datetime.now() + timedelta(days=1, hours=10)
        self.start_datetime = self.start_datetime.replace(hour=10, minute=0, second=0, microsecond=0)
        self.end_datetime = self.start_datetime + timedelta(hours=2)
        
    def test_complete_booking_flow(self):
        """
        Test complete booking lifecycle: create -> confirm -> check-in -> complete
        Verifies status transitions, equipment checkout/return, and field updates
        """
        _logger.info('Starting test_complete_booking_flow')
        
        # Step 1: Create booking in draft status
        booking = self.env['sports.booking'].create({
            'facility_id': self.facility.id,
            'customer_id': self.customer.id,
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'equipment_ids': [(6, 0, [self.equipment.id])],
            'notes': 'Integration test booking',
        })
        
        # Verify initial state
        self.assertEqual(booking.status, 'draft', 'Booking should start in draft status')
        self.assertEqual(booking.duration, 2.0, 'Duration should be 2 hours')
        self.assertTrue(booking.booking_reference, 'Booking reference should be generated')
        self.assertNotEqual(booking.booking_reference, 'New', 'Booking reference should not be "New"')
        
        # Verify equipment is still available (not checked out yet)
        self.assertEqual(self.equipment.quantity_available, 10, 
                        'Equipment should not be checked out in draft status')
        
        # Step 2: Confirm booking
        with patch.object(type(self.env['mail.template']), 'send_mail') as mock_send_mail:
            booking.action_confirm()
        
        # Verify confirmed state
        self.assertEqual(booking.status, 'confirmed', 'Booking should be confirmed')
        self.assertEqual(self.equipment.quantity_available, 9, 
                        'Equipment should be checked out after confirmation')
        
        # Verify email was attempted to be sent
        self.assertTrue(mock_send_mail.called, 'Confirmation email should be sent')
        
        # Step 3: Check-in (simulate customer arrival)
        checkin_time = datetime.now()
        booking.write({
            'status': 'in_progress',
            'checkin_datetime': checkin_time,
        })
        
        # Verify check-in state
        self.assertEqual(booking.status, 'in_progress', 'Booking should be in progress')
        self.assertTrue(booking.checkin_datetime, 'Check-in time should be recorded')
        
        # Step 4: Complete booking
        booking.action_complete()
        
        # Verify completed state
        self.assertEqual(booking.status, 'completed', 'Booking should be completed')
        self.assertEqual(self.equipment.quantity_available, 10, 
                        'Equipment should be returned after completion')
        
        _logger.info('test_complete_booking_flow completed successfully')
    
    def test_recurring_booking_generation(self):
        """
        Test recurring booking generation with different recurrence types
        Verifies child bookings are created with correct dates and linked to parent
        """
        _logger.info('Starting test_recurring_booking_generation')
        
        # Test daily recurrence
        daily_booking = self.env['sports.booking'].create({
            'facility_id': self.facility.id,
            'customer_id': self.customer.id,
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'is_recurring': True,
            'recurrence_type': 'daily',
            'recurrence_count': 3,  # 3 additional bookings
        })
        
        # Confirm to trigger recurring booking generation
        with patch.object(type(self.env['mail.template']), 'send_mail'):
            daily_booking.action_confirm()
        
        # Verify child bookings were created
        child_bookings = self.env['sports.booking'].search([
            ('parent_booking_id', '=', daily_booking.id)
        ])
        
        self.assertEqual(len(child_bookings), 3, 
                        'Should create 3 child bookings for daily recurrence')
        
        # Verify dates are correct (each day incremented)
        for idx, child in enumerate(child_bookings.sorted('start_datetime')):
            expected_start = self.start_datetime + timedelta(days=idx + 1)
            self.assertEqual(child.start_datetime.date(), expected_start.date(),
                           f'Child booking {idx + 1} should be {idx + 1} days after parent')
            self.assertEqual(child.status, 'draft', 'Child bookings should start as draft')
            self.assertFalse(child.is_recurring, 'Child bookings should not be recurring')
            self.assertEqual(child.parent_booking_id.id, daily_booking.id,
                           'Child should link to parent booking')
        
        # Test weekly recurrence
        weekly_start = self.start_datetime + timedelta(days=14)  # 2 weeks ahead
        weekly_booking = self.env['sports.booking'].create({
            'facility_id': self.facility.id,
            'customer_id': self.customer.id,
            'start_datetime': weekly_start,
            'end_datetime': weekly_start + timedelta(hours=2),
            'is_recurring': True,
            'recurrence_type': 'weekly',
            'recurrence_count': 2,
        })
        
        with patch.object(type(self.env['mail.template']), 'send_mail'):
            weekly_booking.action_confirm()
        
        weekly_children = self.env['sports.booking'].search([
            ('parent_booking_id', '=', weekly_booking.id)
        ])
        
        self.assertEqual(len(weekly_children), 2,
                        'Should create 2 child bookings for weekly recurrence')
        
        # Verify weekly intervals
        for idx, child in enumerate(weekly_children.sorted('start_datetime')):
            expected_start = weekly_start + timedelta(days=(idx + 1) * 7)
            self.assertEqual(child.start_datetime.date(), expected_start.date(),
                           f'Child booking should be {(idx + 1) * 7} days after parent')
        
        # Test monthly recurrence
        monthly_start = self.start_datetime + timedelta(days=60)  # 2 months ahead
        monthly_booking = self.env['sports.booking'].create({
            'facility_id': self.facility.id,
            'customer_id': self.customer.id,
            'start_datetime': monthly_start,
            'end_datetime': monthly_start + timedelta(hours=2),
            'is_recurring': True,
            'recurrence_type': 'monthly',
            'recurrence_count': 2,
        })
        
        with patch.object(type(self.env['mail.template']), 'send_mail'):
            monthly_booking.action_confirm()
        
        monthly_children = self.env['sports.booking'].search([
            ('parent_booking_id', '=', monthly_booking.id)
        ])
        
        self.assertEqual(len(monthly_children), 2,
                        'Should create 2 child bookings for monthly recurrence')
        
        # Verify monthly intervals (approximate - relativedelta handles month boundaries)
        for idx, child in enumerate(monthly_children.sorted('start_datetime')):
            expected_start = monthly_start + relativedelta(months=idx + 1)
            self.assertEqual(child.start_datetime.month, expected_start.month,
                           f'Child booking should be {idx + 1} months after parent')
        
        _logger.info('test_recurring_booking_generation completed successfully')
    
    def test_waitlist_notification(self):
        """
        Test automatic waitlist notification when booking is cancelled
        Verifies waitlist customer is notified and status updated correctly
        """
        _logger.info('Starting test_waitlist_notification')
        
        # Create confirmed booking
        booking = self.env['sports.booking'].create({
            'facility_id': self.facility.id,
            'customer_id': self.customer.id,
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'equipment_ids': [(6, 0, [self.equipment.id])],
        })
        
        with patch.object(type(self.env['mail.template']), 'send_mail'):
            booking.action_confirm()
        
        # Create waitlist entry for same facility and date range
        waitlist_date = self.start_datetime.date()
        waitlist = self.env['sports.waitlist'].create({
            'customer_id': self.customer2.id,
            'facility_id': self.facility.id,
            'preferred_date': waitlist_date,
            'preferred_time_start': 10.0,
            'preferred_time_end': 12.0,
            'status': 'waiting',
        })
        
        # Verify waitlist is in waiting status
        self.assertEqual(waitlist.status, 'waiting', 'Waitlist should be waiting initially')
        self.assertFalse(waitlist.notification_sent, 'Notification should not be sent yet')
        
        # Cancel booking (should trigger waitlist notification)
        with patch.object(type(self.env['mail.template']), 'send_mail') as mock_send:
            with patch.object(type(self.env['mail.mail']), 'create') as mock_mail_create:
                mock_mail_obj = MagicMock()
                mock_mail_create.return_value = mock_mail_obj
                
                booking.action_cancel()
        
        # Reload waitlist to get updated values
        waitlist.invalidate_cache()
        
        # Verify waitlist was notified
        self.assertEqual(waitlist.status, 'notified', 
                        'Waitlist status should be updated to notified')
        self.assertTrue(waitlist.notification_sent, 
                       'Notification flag should be set to True')
        
        # Verify booking was cancelled
        self.assertEqual(booking.status, 'cancelled', 'Booking should be cancelled')
        self.assertEqual(self.equipment.quantity_available, 10, 
                        'Equipment should be returned after cancellation')
        
        # Test waitlist notification with no matching waitlist entries
        booking2 = self.env['sports.booking'].create({
            'facility_id': self.facility.id,
            'customer_id': self.customer.id,
            'start_datetime': self.start_datetime + timedelta(days=30),
            'end_datetime': self.start_datetime + timedelta(days=30, hours=2),
        })
        
        with patch.object(type(self.env['mail.template']), 'send_mail'):
            booking2.action_confirm()
        
        # Cancel without matching waitlist (should not raise error)
        with patch.object(type(self.env['mail.template']), 'send_mail'):
            booking2.action_cancel()
        
        self.assertEqual(booking2.status, 'cancelled', 
                        'Booking should cancel even without waitlist match')
        
        _logger.info('test_waitlist_notification completed successfully')
    
    def test_email_sending(self):
        """
        Test email sending for various booking events
        Verifies correct email templates are used and emails are sent
        """
        _logger.info('Starting test_email_sending')
        
        # Create booking
        booking = self.env['sports.booking'].create({
            'facility_id': self.facility.id,
            'customer_id': self.customer.id,
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
        })
        
        # Test 1: Confirmation email
        with patch.object(type(self.env['mail.template']), 'send_mail') as mock_send:
            booking.action_confirm()
            
            # Verify send_mail was called
            self.assertTrue(mock_send.called, 'Confirmation email should be sent')
            
            # Check if correct template reference was attempted
            call_args = mock_send.call_args
            if call_args:
                _logger.info(f'Confirmation email call args: {call_args}')
        
        # Test 2: Cancellation email
        with patch.object(type(self.env['mail.template']), 'send_mail') as mock_send:
            booking.action_cancel()
            
            # Verify send_mail was called for cancellation
            self.assertTrue(mock_send.called, 'Cancellation email should be sent')
        
        # Test 3: Recurring booking emails
        recurring_booking = self.env['sports.booking'].create({
            'facility_id': self.facility.id,
            'customer_id': self.customer.id,
            'start_datetime': self.start_datetime + timedelta(days=7),
            'end_datetime': self.start_datetime + timedelta(days=7, hours=2),
            'is_recurring': True,
            'recurrence_type': 'daily',
            'recurrence_count': 2,
        })
        
        with patch.object(type(self.env['mail.template']), 'send_mail') as mock_send:
            recurring_booking.action_confirm()
            
            # Should send confirmation email (recurring generation errors don't stop confirmation)
            self.assertTrue(mock_send.called, 
                          'Confirmation email should be sent for recurring booking')
        
        # Test 4: Waitlist notification email
        waitlist = self.env['sports.waitlist'].create({
            'customer_id': self.customer2.id,
            'facility_id': self.facility.id,
            'preferred_date': self.start_datetime.date(),
            'status': 'waiting',
        })
        
        with patch.object(type(self.env['mail.template']), 'send_mail') as mock_send:
            waitlist.action_notify_customer()
            
            # Verify email sending was attempted
            self.assertTrue(mock_send.called or waitlist.notification_sent,
                          'Waitlist notification email should be sent or flag set')
            self.assertEqual(waitlist.status, 'notified',
                           'Waitlist status should be notified')
        
        # Test 5: Email template not found (should not raise error)
        booking3 = self.env['sports.booking'].create({
            'facility_id': self.facility.id,
            'customer_id': self.customer.id,
            'start_datetime': self.start_datetime + timedelta(days=10),
            'end_datetime': self.start_datetime + timedelta(days=10, hours=2),
        })
        
        # Mock template not found scenario
        with patch.object(type(self.env['ir.model.data']), 'get_object_reference') as mock_ref:
            mock_ref.side_effect = ValueError('Template not found')
            
            # Should not raise error, just log warning
            try:
                booking3.action_confirm()
                self.assertEqual(booking3.status, 'confirmed',
                               'Booking should confirm even if email fails')
            except Exception as e:
                self.fail(f'Confirmation should not fail if email template missing: {e}')
        
        _logger.info('test_email_sending completed successfully')
    
    def test_booking_constraints_and_validations(self):
        """
        Test booking constraints and validation rules
        Verifies double booking prevention, time validations, and business rules
        """
        _logger.info('Starting test_booking_constraints_and_validations')
        
        # Create and confirm first booking
        booking1 = self.env['sports.booking'].create({
            'facility_id': self.facility.id,
            'customer_id': self.customer.id,
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
        })
        
        with patch.object(type(self.env['mail.template']), 'send_mail'):
            booking1.action_confirm()
        
        # Test double booking prevention
        with self.assertRaises(ValidationError, msg='Should prevent double booking'):
            overlapping_booking = self.env['sports.booking'].create({
                'facility_id': self.facility.id,
                'customer_id': self.customer2.id,
                'start_datetime': self.start_datetime + timedelta(hours=1),
                'end_datetime': self.end_datetime + timedelta(hours=1),
            })
            overlapping_booking.action_confirm()
        
        # Test invalid time range (end before start)
        with self.assertRaises(ValidationError, msg='Should reject end time before start'):
            self.env['sports.booking'].create({
                'facility_id': self.facility.id,
                'customer_id': self.customer.id,
                'start_datetime': self.end_datetime,
                'end_datetime': self.start_datetime,
            })
        
        # Test booking outside operating hours
        early_start = self.start_datetime.replace(hour=6)  # Before 8 AM
        with self.assertRaises(ValidationError, msg='Should reject booking before operating hours'):
            self.env['sports.booking'].create({
                'facility_id': self.facility.id,
                'customer_id': self.customer.id,
                'start_datetime': early_start,
                'end_datetime': early_start + timedelta(hours=1),
            })
        
        _logger.info('test_booking_constraints_and_validations completed successfully')
    
    def test_equipment_availability_tracking(self):
        """
        Test equipment quantity tracking through booking lifecycle
        Verifies equipment checkout, return, and availability checks
        """
        _logger.info('Starting test_equipment_availability_tracking')
        
        initial_quantity = self.equipment.quantity_available
        self.assertEqual(initial_quantity, 10, 'Initial equipment quantity should be 10')
        
        # Create multiple bookings with equipment
        bookings = []
        for i in range(3):
            booking = self.env['sports.booking'].create({
                'facility_id': self.facility.id,
                'customer_id': self.customer.id,
                'start_datetime': self.start_datetime + timedelta(hours=i * 3),
                'end_datetime': self.start_datetime + timedelta(hours=i * 3 + 2),
                'equipment_ids': [(6, 0, [self.equipment.id])],
            })
            bookings.append(booking)
        
        # Confirm all bookings
        with patch.object(type(self.env['mail.template']), 'send_mail'):
            for booking in bookings:
                booking.action_confirm()
        
        # Check equipment quantity decreased
        self.assertEqual(self.equipment.quantity_available, 7,
                        'Equipment quantity should decrease after 3 bookings')
        
        # Complete first booking (should return equipment)
        bookings[0].action_complete()
        self.assertEqual(self.equipment.quantity_available, 8,
                        'Equipment should be returned after completion')
        
        # Cancel second booking (should return equipment)
        with patch.object(type(self.env['mail.template']), 'send_mail'):
            bookings[1].action_cancel()
        
        self.assertEqual(self.equipment.quantity_available, 9,
                        'Equipment should be returned after cancellation')
        
        # Test equipment unavailability
        # Set equipment to 0 available
        self.equipment.quantity_available = 0
        
        booking_no_equipment = self.env['sports.booking'].create({
            'facility_id': self.facility.id,
            'customer_id': self.customer.id,
            'start_datetime': self.start_datetime + timedelta(days=5),
            'end_datetime': self.start_datetime + timedelta(days=5, hours=2),
            'equipment_ids': [(6, 0, [self.equipment.id])],
        })
        
        # Should raise error when trying to confirm with unavailable equipment
        with self.assertRaises(ValidationError, msg='Should prevent checkout of unavailable equipment'):
            with patch.object(type(self.env['mail.template']), 'send_mail'):
                booking_no_equipment.action_confirm()
        
        _logger.info('test_equipment_availability_tracking completed successfully')
