# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from odoo import fields


class TestSportsBooking(TransactionCase):
    
    def setUp(self):
        """Set up test data for booking tests"""
        super(TestSportsBooking, self).setUp()
        
        # Create test facility
        self.facility = self.env['sports.facility'].create({
            'name': 'Test Tennis Court',
            'facility_type': 'court',
            'capacity': 4,
            'hourly_rate': 25.00,
            'status': 'available',
            'location': 'Test Location',
            'operating_hours_start': 8.0,
            'operating_hours_end': 20.0,
        })
        
        # Create test equipment
        self.equipment1 = self.env['sports.equipment'].create({
            'name': 'Test Tennis Racket',
            'equipment_type': 'racket',
            'total_quantity': 10,
            'quantity_available': 10,
            'rental_rate': 5.00,
            'condition': 'excellent',
        })
        
        self.equipment2 = self.env['sports.equipment'].create({
            'name': 'Test Tennis Balls',
            'equipment_type': 'ball',
            'total_quantity': 20,
            'quantity_available': 20,
            'rental_rate': 2.00,
            'condition': 'good',
        })
        
        # Create test customer
        self.customer = self.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'test.customer@example.com',
            'phone': '+1-555-0123',
        })
        
        # Define test datetime values
        self.start_datetime = datetime.now() + timedelta(days=1, hours=10)
        self.end_datetime = datetime.now() + timedelta(days=1, hours=12)
    
    def test_booking_creation(self):
        """Test 1: Verify booking creates with correct reference"""
        # Create a booking
        booking = self.env['sports.booking'].create({
            'facility_id': self.facility.id,
            'customer_id': self.customer.id,
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'status': 'draft',
        })
        
        # Assertions
        self.assertTrue(booking, "Booking should be created")
        self.assertNotEqual(booking.booking_reference, 'New', 
                          "Booking reference should be auto-generated")
        self.assertEqual(booking.facility_id.id, self.facility.id,
                        "Facility should match")
        self.assertEqual(booking.customer_id.id, self.customer.id,
                        "Customer should match")
        self.assertEqual(booking.status, 'draft',
                        "Initial status should be draft")
        self.assertGreater(booking.duration, 0,
                         "Duration should be calculated")
        self.assertEqual(booking.duration, 2.0,
                        "Duration should be 2 hours")
    
    def test_double_booking_prevention(self):
        """Test 2: Try to create overlapping booking and assert ValidationError"""
        # Create first booking
        booking1 = self.env['sports.booking'].create({
            'facility_id': self.facility.id,
            'customer_id': self.customer.id,
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'status': 'confirmed',
        })
        
        self.assertTrue(booking1, "First booking should be created")
        
        # Try to create overlapping booking (should raise ValidationError)
        with self.assertRaises(ValidationError, 
                             msg="Should raise ValidationError for overlapping booking"):
            booking2 = self.env['sports.booking'].create({
                'facility_id': self.facility.id,
                'customer_id': self.customer.id,
                'start_datetime': self.start_datetime + timedelta(minutes=30),
                'end_datetime': self.end_datetime + timedelta(minutes=30),
                'status': 'confirmed',
            })
        
        # Test partial overlap at the start
        with self.assertRaises(ValidationError,
                             msg="Should raise ValidationError for partial overlap at start"):
            booking3 = self.env['sports.booking'].create({
                'facility_id': self.facility.id,
                'customer_id': self.customer.id,
                'start_datetime': self.start_datetime - timedelta(hours=1),
                'end_datetime': self.start_datetime + timedelta(minutes=30),
                'status': 'confirmed',
            })
        
        # Test partial overlap at the end
        with self.assertRaises(ValidationError,
                             msg="Should raise ValidationError for partial overlap at end"):
            booking4 = self.env['sports.booking'].create({
                'facility_id': self.facility.id,
                'customer_id': self.customer.id,
                'start_datetime': self.end_datetime - timedelta(minutes=30),
                'end_datetime': self.end_datetime + timedelta(hours=1),
                'status': 'confirmed',
            })
        
        # Verify booking on different facility is allowed (no overlap)
        other_facility = self.env['sports.facility'].create({
            'name': 'Test Basketball Court',
            'facility_type': 'court',
            'capacity': 10,
            'hourly_rate': 20.00,
            'status': 'available',
            'operating_hours_start': 8.0,
            'operating_hours_end': 20.0,
        })
        
        booking_different_facility = self.env['sports.booking'].create({
            'facility_id': other_facility.id,
            'customer_id': self.customer.id,
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'status': 'confirmed',
        })
        
        self.assertTrue(booking_different_facility,
                       "Booking on different facility should be allowed")
    
    def test_cost_calculation(self):
        """Test 3: Verify total_cost computes correctly with equipment"""
        # Create booking with equipment
        booking = self.env['sports.booking'].create({
            'facility_id': self.facility.id,
            'customer_id': self.customer.id,
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'equipment_ids': [(6, 0, [self.equipment1.id, self.equipment2.id])],
            'status': 'draft',
        })
        
        # Calculate expected cost
        # Facility: 25.00 * 2 hours = 50.00
        # Equipment1: 5.00 * 2 hours = 10.00
        # Equipment2: 2.00 * 2 hours = 4.00
        # Total: 50.00 + 10.00 + 4.00 = 64.00
        expected_cost = 64.00
        
        # Assertions
        self.assertEqual(booking.total_cost, expected_cost,
                        f"Total cost should be {expected_cost}")
        
        # Test booking without equipment
        booking_no_equipment = self.env['sports.booking'].create({
            'facility_id': self.facility.id,
            'customer_id': self.customer.id,
            'start_datetime': self.start_datetime + timedelta(days=1),
            'end_datetime': self.end_datetime + timedelta(days=1),
            'status': 'draft',
        })
        
        # Expected cost: 25.00 * 2 hours = 50.00
        expected_cost_no_equipment = 50.00
        
        self.assertEqual(booking_no_equipment.total_cost, expected_cost_no_equipment,
                        f"Total cost without equipment should be {expected_cost_no_equipment}")
    
    def test_membership_discount(self):
        """Test 4: Create membership and verify discount applied"""
        # Create membership for customer (20% discount)
        membership = self.env['sports.membership'].create({
            'member_id': self.customer.id,
            'membership_type': 'premium',
            'start_date': fields.Date.today() - timedelta(days=30),
            'end_date': fields.Date.today() + timedelta(days=335),
            'discount_percentage': 20.00,
            'status': 'active',
            'payment_status': 'paid',
            'membership_fee': 199.00,
        })
        
        # Create booking
        booking = self.env['sports.booking'].create({
            'facility_id': self.facility.id,
            'customer_id': self.customer.id,
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'equipment_ids': [(6, 0, [self.equipment1.id])],
            'status': 'draft',
        })
        
        # Calculate expected cost with discount
        # Facility: 25.00 * 2 hours = 50.00
        # Equipment1: 5.00 * 2 hours = 10.00
        # Subtotal: 60.00
        # Discount (20%): 60.00 * 0.20 = 12.00
        # Total: 60.00 - 12.00 = 48.00
        expected_cost_with_discount = 48.00
        
        # Assertions
        self.assertEqual(booking.total_cost, expected_cost_with_discount,
                        f"Total cost with 20% discount should be {expected_cost_with_discount}")
        
        # Test with VIP membership (30% discount)
        vip_customer = self.env['res.partner'].create({
            'name': 'VIP Customer',
            'email': 'vip@example.com',
        })
        
        vip_membership = self.env['sports.membership'].create({
            'member_id': vip_customer.id,
            'membership_type': 'vip',
            'start_date': fields.Date.today() - timedelta(days=10),
            'end_date': fields.Date.today() + timedelta(days=355),
            'discount_percentage': 30.00,
            'status': 'active',
            'payment_status': 'paid',
            'membership_fee': 399.00,
        })
        
        vip_booking = self.env['sports.booking'].create({
            'facility_id': self.facility.id,
            'customer_id': vip_customer.id,
            'start_datetime': self.start_datetime + timedelta(days=2),
            'end_datetime': self.end_datetime + timedelta(days=2),
            'status': 'draft',
        })
        
        # Facility: 25.00 * 2 hours = 50.00
        # Discount (30%): 50.00 * 0.30 = 15.00
        # Total: 50.00 - 15.00 = 35.00
        expected_vip_cost = 35.00
        
        self.assertEqual(vip_booking.total_cost, expected_vip_cost,
                        f"VIP total cost with 30% discount should be {expected_vip_cost}")
    
    def test_equipment_checkout(self):
        """Test 5: Confirm booking and verify equipment quantity decreases"""
        # Verify initial equipment quantity
        initial_quantity = self.equipment1.quantity_available
        self.assertEqual(initial_quantity, 10,
                        "Initial equipment quantity should be 10")
        
        # Create booking with equipment
        booking = self.env['sports.booking'].create({
            'facility_id': self.facility.id,
            'customer_id': self.customer.id,
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'equipment_ids': [(6, 0, [self.equipment1.id])],
            'status': 'draft',
        })
        
        # Equipment quantity should still be 10 (not checked out yet)
        self.assertEqual(self.equipment1.quantity_available, 10,
                        "Equipment quantity should remain 10 in draft status")
        
        # Confirm booking (should checkout equipment)
        booking.action_confirm()
        
        # Verify booking status changed
        self.assertEqual(booking.status, 'confirmed',
                        "Booking status should be confirmed")
        
        # Verify equipment quantity decreased
        self.assertEqual(self.equipment1.quantity_available, 9,
                        "Equipment quantity should decrease to 9 after checkout")
        
        # Complete booking (should return equipment)
        booking.action_complete()
        
        # Verify booking status changed
        self.assertEqual(booking.status, 'completed',
                        "Booking status should be completed")
        
        # Verify equipment quantity restored
        self.assertEqual(self.equipment1.quantity_available, 10,
                        "Equipment quantity should be restored to 10 after completion")
        
        # Test cancellation also restores equipment
        booking2 = self.env['sports.booking'].create({
            'facility_id': self.facility.id,
            'customer_id': self.customer.id,
            'start_datetime': self.start_datetime + timedelta(days=3),
            'end_datetime': self.end_datetime + timedelta(days=3),
            'equipment_ids': [(6, 0, [self.equipment1.id, self.equipment2.id])],
            'status': 'draft',
        })
        
        # Confirm booking
        booking2.action_confirm()
        
        # Verify quantities decreased
        self.assertEqual(self.equipment1.quantity_available, 9,
                        "Equipment1 quantity should be 9 after second booking")
        self.assertEqual(self.equipment2.quantity_available, 19,
                        "Equipment2 quantity should be 19 after booking")
        
        # Cancel booking (should restore equipment)
        booking2.action_cancel()
        
        # Verify booking status
        self.assertEqual(booking2.status, 'cancelled',
                        "Booking status should be cancelled")
        
        # Verify equipment quantities restored
        self.assertEqual(self.equipment1.quantity_available, 10,
                        "Equipment1 quantity should be restored to 10 after cancellation")
        self.assertEqual(self.equipment2.quantity_available, 20,
                        "Equipment2 quantity should be restored to 20 after cancellation")
