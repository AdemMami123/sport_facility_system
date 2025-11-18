# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError
from datetime import datetime, timedelta
from odoo import fields


class TestSecurityAccess(TransactionCase):
    
    def setUp(self):
        """Set up test data for security tests"""
        super(TestSecurityAccess, self).setUp()
        
        # Get security groups
        self.group_sports_user = self.env.ref('sport_facility_system.group_sports_user')
        self.group_sports_manager = self.env.ref('sport_facility_system.group_sports_manager')
        
        # Create test facility
        self.facility = self.env['sports.facility'].sudo().create({
            'name': 'Test Security Facility',
            'facility_type': 'court',
            'capacity': 4,
            'hourly_rate': 30.00,
            'status': 'available',
            'operating_hours_start': 8.0,
            'operating_hours_end': 20.0,
        })
        
        # Create test equipment
        self.equipment = self.env['sports.equipment'].sudo().create({
            'name': 'Test Security Equipment',
            'equipment_type': 'ball',
            'total_quantity': 10,
            'quantity_available': 10,
            'rental_rate': 5.00,
            'condition': 'good',
        })
        
        # Create test customers (partners)
        self.customer1 = self.env['res.partner'].sudo().create({
            'name': 'Test Customer 1',
            'email': 'customer1@test.com',
        })
        
        self.customer2 = self.env['res.partner'].sudo().create({
            'name': 'Test Customer 2',
            'email': 'customer2@test.com',
        })
        
        # Create test users
        self.user_sports_user = self.env['res.users'].sudo().create({
            'name': 'Sports User Test',
            'login': 'sports_user_test',
            'email': 'sports.user@test.com',
            'partner_id': self.customer1.id,
            'groups_id': [(6, 0, [self.group_sports_user.id])],
        })
        
        self.user_sports_manager = self.env['res.users'].sudo().create({
            'name': 'Sports Manager Test',
            'login': 'sports_manager_test',
            'email': 'sports.manager@test.com',
            'groups_id': [(6, 0, [self.group_sports_manager.id])],
        })
        
        # Create another regular user
        self.user_sports_user2 = self.env['res.users'].sudo().create({
            'name': 'Sports User 2 Test',
            'login': 'sports_user2_test',
            'email': 'sports.user2@test.com',
            'partner_id': self.customer2.id,
            'groups_id': [(6, 0, [self.group_sports_user.id])],
        })
        
        # Define test datetime values
        self.start_datetime = datetime.now() + timedelta(days=1, hours=10)
        self.end_datetime = datetime.now() + timedelta(days=1, hours=12)
    
    def test_01_user_can_create_own_booking(self):
        """Test 1: Sports User can create their own booking"""
        # Switch to sports user context
        booking_model = self.env['sports.booking'].with_user(self.user_sports_user)
        
        # Create booking as sports user
        booking = booking_model.create({
            'facility_id': self.facility.id,
            'customer_id': self.customer1.id,  # User's own partner
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'status': 'draft',
        })
        
        # Assertions
        self.assertTrue(booking, "Sports user should be able to create booking")
        self.assertEqual(booking.customer_id.id, self.customer1.id,
                        "Booking should be created for the user's partner")
    
    def test_02_user_can_read_own_booking(self):
        """Test 2: Sports User can read their own booking"""
        # Create booking as admin
        booking = self.env['sports.booking'].sudo().create({
            'facility_id': self.facility.id,
            'customer_id': self.customer1.id,
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'status': 'draft',
        })
        
        # Switch to sports user context and try to read
        booking_as_user = booking.with_user(self.user_sports_user)
        
        # Should be able to read
        self.assertEqual(booking_as_user.customer_id.id, self.customer1.id,
                        "User should be able to read their own booking")
        self.assertTrue(booking_as_user.booking_reference,
                       "User should be able to access booking fields")
    
    def test_03_user_can_write_own_booking(self):
        """Test 3: Sports User can write/edit their own booking"""
        # Create booking as admin
        booking = self.env['sports.booking'].sudo().create({
            'facility_id': self.facility.id,
            'customer_id': self.customer1.id,
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'status': 'draft',
            'notes': 'Initial notes',
        })
        
        # Switch to sports user context and try to write
        booking_as_user = booking.with_user(self.user_sports_user)
        
        # Should be able to write/update
        booking_as_user.write({'notes': 'Updated by user'})
        
        # Verify update
        self.assertEqual(booking_as_user.notes, 'Updated by user',
                        "User should be able to update their own booking")
    
    def test_04_user_cannot_read_other_user_booking(self):
        """Test 4: Sports User cannot read other user's booking (AccessError expected)"""
        # Create booking for customer2 (different customer)
        booking = self.env['sports.booking'].sudo().create({
            'facility_id': self.facility.id,
            'customer_id': self.customer2.id,  # Different customer
            'start_datetime': self.start_datetime + timedelta(days=1),
            'end_datetime': self.end_datetime + timedelta(days=1),
            'status': 'draft',
        })
        
        # Switch to sports user (customer1) context
        booking_model = self.env['sports.booking'].with_user(self.user_sports_user)
        
        # Try to search for other user's booking - should not find it
        found_bookings = booking_model.search([('id', '=', booking.id)])
        
        self.assertEqual(len(found_bookings), 0,
                        "User should not be able to find other user's booking")
        
        # Try to read other user's booking directly - should raise AccessError
        with self.assertRaises(AccessError,
                             msg="User should not be able to read other user's booking"):
            booking.with_user(self.user_sports_user).read(['booking_reference', 'customer_id'])
    
    def test_05_user_cannot_write_other_user_booking(self):
        """Test 5: Sports User cannot write to other user's booking (AccessError expected)"""
        # Create booking for customer2
        booking = self.env['sports.booking'].sudo().create({
            'facility_id': self.facility.id,
            'customer_id': self.customer2.id,
            'start_datetime': self.start_datetime + timedelta(days=2),
            'end_datetime': self.end_datetime + timedelta(days=2),
            'status': 'draft',
            'notes': 'Original notes',
        })
        
        # Try to write to other user's booking - should raise AccessError
        with self.assertRaises(AccessError,
                             msg="User should not be able to write to other user's booking"):
            booking.with_user(self.user_sports_user).write({'notes': 'Unauthorized update'})
    
    def test_06_user_cannot_delete_own_booking(self):
        """Test 6: Sports User cannot delete their own booking (no unlink permission)"""
        # Create booking as admin
        booking = self.env['sports.booking'].sudo().create({
            'facility_id': self.facility.id,
            'customer_id': self.customer1.id,
            'start_datetime': self.start_datetime + timedelta(days=3),
            'end_datetime': self.end_datetime + timedelta(days=3),
            'status': 'draft',
        })
        
        # Try to delete own booking - should raise AccessError
        with self.assertRaises(AccessError,
                             msg="User should not be able to delete their own booking"):
            booking.with_user(self.user_sports_user).unlink()
    
    def test_07_manager_can_read_all_bookings(self):
        """Test 7: Sports Manager can read all bookings"""
        # Create bookings for different customers
        booking1 = self.env['sports.booking'].sudo().create({
            'facility_id': self.facility.id,
            'customer_id': self.customer1.id,
            'start_datetime': self.start_datetime + timedelta(days=4),
            'end_datetime': self.end_datetime + timedelta(days=4),
            'status': 'draft',
        })
        
        booking2 = self.env['sports.booking'].sudo().create({
            'facility_id': self.facility.id,
            'customer_id': self.customer2.id,
            'start_datetime': self.start_datetime + timedelta(days=5),
            'end_datetime': self.end_datetime + timedelta(days=5),
            'status': 'draft',
        })
        
        # Switch to manager context
        booking_model = self.env['sports.booking'].with_user(self.user_sports_manager)
        
        # Manager should be able to find all bookings
        all_bookings = booking_model.search([
            ('id', 'in', [booking1.id, booking2.id])
        ])
        
        self.assertEqual(len(all_bookings), 2,
                        "Manager should be able to find all bookings")
        
        # Manager should be able to read any booking
        booking1_as_manager = booking1.with_user(self.user_sports_manager)
        booking2_as_manager = booking2.with_user(self.user_sports_manager)
        
        self.assertEqual(booking1_as_manager.customer_id.id, self.customer1.id,
                        "Manager should be able to read booking 1")
        self.assertEqual(booking2_as_manager.customer_id.id, self.customer2.id,
                        "Manager should be able to read booking 2")
    
    def test_08_manager_can_write_all_bookings(self):
        """Test 8: Sports Manager can write to all bookings"""
        # Create booking for customer1
        booking = self.env['sports.booking'].sudo().create({
            'facility_id': self.facility.id,
            'customer_id': self.customer1.id,
            'start_datetime': self.start_datetime + timedelta(days=6),
            'end_datetime': self.end_datetime + timedelta(days=6),
            'status': 'draft',
            'notes': 'Initial notes',
        })
        
        # Manager should be able to write to any booking
        booking_as_manager = booking.with_user(self.user_sports_manager)
        booking_as_manager.write({'notes': 'Updated by manager'})
        
        # Verify update
        self.assertEqual(booking.notes, 'Updated by manager',
                        "Manager should be able to update any booking")
    
    def test_09_manager_can_delete_bookings(self):
        """Test 9: Sports Manager can delete any booking"""
        # Create booking for customer1
        booking = self.env['sports.booking'].sudo().create({
            'facility_id': self.facility.id,
            'customer_id': self.customer1.id,
            'start_datetime': self.start_datetime + timedelta(days=7),
            'end_datetime': self.end_datetime + timedelta(days=7),
            'status': 'draft',
        })
        
        booking_id = booking.id
        
        # Manager should be able to delete any booking
        booking.with_user(self.user_sports_manager).unlink()
        
        # Verify deletion
        deleted_booking = self.env['sports.booking'].sudo().search([('id', '=', booking_id)])
        self.assertEqual(len(deleted_booking), 0,
                        "Manager should be able to delete bookings")
    
    def test_10_user_list_only_own_bookings(self):
        """Test 10: Sports User search returns only their own bookings"""
        # Create multiple bookings for different customers
        booking_user1 = self.env['sports.booking'].sudo().create({
            'facility_id': self.facility.id,
            'customer_id': self.customer1.id,
            'start_datetime': self.start_datetime + timedelta(days=8),
            'end_datetime': self.end_datetime + timedelta(days=8),
            'status': 'draft',
        })
        
        booking_user2 = self.env['sports.booking'].sudo().create({
            'facility_id': self.facility.id,
            'customer_id': self.customer2.id,
            'start_datetime': self.start_datetime + timedelta(days=9),
            'end_datetime': self.end_datetime + timedelta(days=9),
            'status': 'draft',
        })
        
        # Search as user1 - should only see own bookings
        booking_model = self.env['sports.booking'].with_user(self.user_sports_user)
        user_bookings = booking_model.search([])
        
        # Verify only own bookings are returned
        self.assertIn(booking_user1.id, user_bookings.ids,
                     "User should see their own booking")
        self.assertNotIn(booking_user2.id, user_bookings.ids,
                        "User should not see other user's booking in search results")
    
    def test_11_manager_can_create_booking_for_any_customer(self):
        """Test 11: Sports Manager can create booking for any customer"""
        # Manager creates booking for customer1
        booking_model = self.env['sports.booking'].with_user(self.user_sports_manager)
        
        booking = booking_model.create({
            'facility_id': self.facility.id,
            'customer_id': self.customer1.id,
            'start_datetime': self.start_datetime + timedelta(days=10),
            'end_datetime': self.end_datetime + timedelta(days=10),
            'status': 'draft',
        })
        
        # Verify booking was created
        self.assertTrue(booking, "Manager should be able to create booking")
        self.assertEqual(booking.customer_id.id, self.customer1.id,
                        "Manager should be able to create booking for any customer")

