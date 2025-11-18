# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError, UserError
import json
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class SportsBookingController(http.Controller):
    """
    HTTP Controller for Sports Facility Booking System
    Handles public website routes for facility browsing and booking
    """

    @http.route('/sports/facilities', type='http', auth='public', website=True)
    def list_facilities(self, facility_type=None, **kwargs):
        """
        Display all available facilities with optional filtering by facility_type
        
        :param facility_type: Optional filter for facility type (court, gym, pool, field)
        :return: Rendered template with facilities list
        """
        try:
            # Build domain for facility search
            domain = [('active', '=', True)]
            
            # Add facility_type filter if provided
            if facility_type:
                domain.append(('facility_type', '=', facility_type))
            
            # Fetch facilities
            facilities = request.env['sports.facility'].sudo().search(domain, order='name')
            
            # Get all facility types for filter dropdown
            facility_types = request.env['sports.facility'].sudo()._fields['facility_type'].selection
            
            # Prepare values for template
            values = {
                'facilities': facilities,
                'facility_types': facility_types,
                'current_filter': facility_type,
                'page_name': 'Sports Facilities',
            }
            
            return request.render('sport_facility_system.facilities_list_template', values)
            
        except Exception as e:
            _logger.error('Error loading facilities: %s', str(e))
            return request.render('website.404')

    @http.route('/sports/booking/<int:facility_id>', type='http', auth='public', website=True)
    def booking_form(self, facility_id, **kwargs):
        """
        Display booking form for a specific facility
        
        :param facility_id: ID of the facility to book
        :return: Rendered booking form template
        """
        try:
            # Fetch the facility
            facility = request.env['sports.facility'].sudo().browse(facility_id)
            
            # Check if facility exists
            if not facility.exists():
                _logger.warning('Facility with ID %s not found', facility_id)
                return request.render('website.404')
            
            # Get available equipment for this facility
            equipment = request.env['sports.equipment'].sudo().search([
                ('facility_ids', 'in', [facility_id]),
                ('quantity_available', '>', 0),
                ('active', '=', True)
            ])
            
            # Get current user's partner if logged in
            partner = request.env.user.partner_id if request.env.user._is_public() is False else False
            
            # Prepare values for template
            values = {
                'facility': facility,
                'equipment': equipment,
                'partner': partner,
                'page_name': f'Book {facility.name}',
            }
            
            return request.render('sport_facility_system.booking_form_template', values)
            
        except Exception as e:
            _logger.error('Error loading booking form for facility %s: %s', facility_id, str(e))
            return request.render('website.404')

    @http.route('/sports/check_availability', type='json', auth='public', methods=['POST'], csrf=False)
    def check_availability(self, facility_id, date, **kwargs):
        """
        Check available time slots for a facility on a specific date
        Returns JSON response with available slots
        
        :param facility_id: ID of the facility
        :param date: Date string in format 'YYYY-MM-DD'
        :return: JSON dict with available time slots
        """
        try:
            # Validate inputs
            if not facility_id or not date:
                return {
                    'success': False,
                    'error': 'Missing required parameters: facility_id and date'
                }
            
            # Parse date
            try:
                booking_date = datetime.strptime(date, '%Y-%m-%d').date()
            except ValueError:
                return {
                    'success': False,
                    'error': 'Invalid date format. Use YYYY-MM-DD'
                }
            
            # Fetch facility
            facility = request.env['sports.facility'].sudo().browse(int(facility_id))
            
            if not facility.exists():
                return {
                    'success': False,
                    'error': 'Facility not found'
                }
            
            # Get facility operating hours
            operating_start = facility.operating_hours_start
            operating_end = facility.operating_hours_end
            
            # Get existing bookings for this facility on this date
            start_datetime = datetime.combine(booking_date, datetime.min.time())
            end_datetime = datetime.combine(booking_date, datetime.max.time())
            
            existing_bookings = request.env['sports.booking'].sudo().search([
                ('facility_id', '=', facility_id),
                ('status', 'in', ['draft', 'confirmed']),
                ('start_datetime', '>=', start_datetime),
                ('start_datetime', '<=', end_datetime)
            ])
            
            # Generate available time slots (1-hour intervals)
            available_slots = []
            current_hour = int(operating_start)
            end_hour = int(operating_end)
            
            while current_hour < end_hour:
                slot_start = current_hour
                slot_end = current_hour + 1
                
                # Check if this slot conflicts with any booking
                slot_start_dt = datetime.combine(booking_date, datetime.min.time().replace(hour=int(slot_start)))
                slot_end_dt = datetime.combine(booking_date, datetime.min.time().replace(hour=int(slot_end)))
                
                is_available = True
                for booking in existing_bookings:
                    if (booking.start_datetime < slot_end_dt and booking.end_datetime > slot_start_dt):
                        is_available = False
                        break
                
                if is_available:
                    available_slots.append({
                        'start': f"{int(slot_start):02d}:00",
                        'end': f"{int(slot_end):02d}:00",
                        'start_hour': slot_start,
                        'end_hour': slot_end
                    })
                
                current_hour += 1
            
            return {
                'success': True,
                'facility_name': facility.name,
                'date': date,
                'available_slots': available_slots,
                'hourly_rate': facility.hourly_rate,
                'currency': facility.currency_id.symbol if facility.currency_id else '$'
            }
            
        except Exception as e:
            _logger.error('Error checking availability: %s', str(e))
            return {
                'success': False,
                'error': f'An error occurred: {str(e)}'
            }

    @http.route('/sports/confirm_booking', type='http', auth='user', methods=['POST'], website=True, csrf=True)
    def confirm_booking(self, **post):
        """
        Create a new booking record from form submission
        Requires authenticated user
        
        :param post: Form data dictionary
        :return: Redirect to booking confirmation page or error page
        """
        try:
            # Validate required fields
            required_fields = ['facility_id', 'start_datetime', 'end_datetime']
            missing_fields = [field for field in required_fields if not post.get(field)]
            
            if missing_fields:
                return request.render('sport_facility_system.booking_error_template', {
                    'error': f"Missing required fields: {', '.join(missing_fields)}"
                })
            
            # Parse form data
            facility_id = int(post.get('facility_id'))
            start_datetime_str = post.get('start_datetime')
            end_datetime_str = post.get('end_datetime')
            equipment_ids = post.get('equipment_ids', '')
            notes = post.get('notes', '')
            
            # Parse datetimes
            try:
                start_datetime = datetime.strptime(start_datetime_str, '%Y-%m-%d %H:%M:%S')
                end_datetime = datetime.strptime(end_datetime_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    # Try alternative format
                    start_datetime = datetime.strptime(start_datetime_str, '%Y-%m-%dT%H:%M')
                    end_datetime = datetime.strptime(end_datetime_str, '%Y-%m-%dT%H:%M')
                except ValueError as e:
                    return request.render('sport_facility_system.booking_error_template', {
                        'error': f'Invalid datetime format: {str(e)}'
                    })
            
            # Validate datetime logic
            if end_datetime <= start_datetime:
                return request.render('sport_facility_system.booking_error_template', {
                    'error': 'End time must be after start time'
                })
            
            # Parse equipment IDs if provided
            equipment_id_list = []
            if equipment_ids:
                try:
                    # Handle comma-separated or JSON array
                    if isinstance(equipment_ids, str):
                        if equipment_ids.startswith('['):
                            equipment_id_list = json.loads(equipment_ids)
                        else:
                            equipment_id_list = [int(x.strip()) for x in equipment_ids.split(',') if x.strip()]
                except (ValueError, json.JSONDecodeError) as e:
                    _logger.warning('Error parsing equipment IDs: %s', str(e))
            
            # Get current user's partner
            customer = request.env.user.partner_id
            
            # Prepare booking values
            booking_vals = {
                'facility_id': facility_id,
                'customer_id': customer.id,
                'start_datetime': start_datetime,
                'end_datetime': end_datetime,
                'notes': notes,
                'status': 'draft',
            }
            
            # Add equipment if provided
            if equipment_id_list:
                booking_vals['equipment_ids'] = [(6, 0, equipment_id_list)]
            
            # Create booking record
            try:
                booking = request.env['sports.booking'].sudo().create(booking_vals)
                _logger.info('Booking created successfully: %s', booking.booking_reference)
                
                # Redirect to booking confirmation page
                return request.redirect(f'/sports/booking/confirmation/{booking.id}')
                
            except ValidationError as ve:
                _logger.warning('Validation error creating booking: %s', str(ve))
                return request.render('sport_facility_system.booking_error_template', {
                    'error': str(ve)
                })
            except Exception as e:
                _logger.error('Error creating booking: %s', str(e))
                return request.render('sport_facility_system.booking_error_template', {
                    'error': 'An error occurred while creating your booking. Please try again.'
                })
            
        except Exception as e:
            _logger.error('Error in confirm_booking: %s', str(e))
            return request.render('sport_facility_system.booking_error_template', {
                'error': 'An unexpected error occurred. Please contact support.'
            })

    @http.route('/sports/booking/confirmation/<int:booking_id>', type='http', auth='user', website=True)
    def booking_confirmation(self, booking_id, **kwargs):
        """
        Display booking confirmation page
        
        :param booking_id: ID of the created booking
        :return: Rendered confirmation template
        """
        try:
            # Fetch booking
            booking = request.env['sports.booking'].sudo().search([
                ('id', '=', booking_id),
                ('customer_id', '=', request.env.user.partner_id.id)
            ], limit=1)
            
            if not booking:
                return request.render('website.404')
            
            values = {
                'booking': booking,
                'page_name': 'Booking Confirmation',
            }
            
            return request.render('sport_facility_system.booking_confirmation_template', values)
            
        except Exception as e:
            _logger.error('Error loading booking confirmation: %s', str(e))
            return request.render('website.404')

    @http.route('/sports/my/bookings', type='http', auth='user', website=True)
    def my_bookings(self, **kwargs):
        """
        Display user's bookings list
        
        :return: Rendered template with user's bookings
        """
        try:
            # Fetch user's bookings
            bookings = request.env['sports.booking'].sudo().search([
                ('customer_id', '=', request.env.user.partner_id.id)
            ], order='start_datetime desc')
            
            values = {
                'bookings': bookings,
                'page_name': 'My Bookings',
            }
            
            return request.render('sport_facility_system.my_bookings_template', values)
            
        except Exception as e:
            _logger.error('Error loading user bookings: %s', str(e))
            return request.render('website.404')
