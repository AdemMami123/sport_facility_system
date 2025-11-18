odoo.define('sports_booking.booking_form', function (require) {
    'use strict';

    var ajax = require('web.ajax');
    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var _t = core._t;

    /**
     * Sports Booking Form Module
     * Handles dynamic form interactions, availability checking, and cost calculations
     */
    var BookingForm = {
        facilityId: null,
        facilityRate: 0,
        currencySymbol: '$',
        currentUserId: null,
        membershipDiscount: 0,
        selectedEquipment: [],
        
        /**
         * Initialize the booking form
         */
        init: function() {
            var self = this;
            
            // Get facility data from form
            this.facilityId = $('#booking_form input[name="facility_id"]').val();
            this.facilityRate = parseFloat($('#booking_form').data('facility-rate') || 0);
            this.currencySymbol = $('#booking_form').data('currency-symbol') || '$';
            this.currentUserId = $('#booking_form').data('user-id');
            
            // Bind event listeners
            this._bindEvents();
            
            // Set minimum date to today
            this._setMinimumDate();
            
            // Load membership discount if user is logged in
            if (this.currentUserId) {
                this._loadMembershipDiscount();
            }
            
            console.log('Booking form initialized');
        },
        
        /**
         * Bind all event listeners
         */
        _bindEvents: function() {
            var self = this;
            
            // Date picker change event
            $('#booking_date').on('change', function() {
                self._onDateChange($(this).val());
            });
            
            // Time slot change event
            $('#time_slot').on('change', function() {
                self._onTimeSlotChange();
            });
            
            // Equipment checkbox change event
            $(document).on('change', '.equipment-checkbox', function() {
                self._onEquipmentChange();
            });
            
            // Form submit validation
            $('#booking_form').on('submit', function(e) {
                return self._validateForm(e);
            });
            
            // Required field validation for enabling submit button
            $('input[required], select[required]').on('change keyup', function() {
                self._updateSubmitButton();
            });
        },
        
        /**
         * Set minimum date to today
         */
        _setMinimumDate: function() {
            var today = new Date().toISOString().split('T')[0];
            $('#booking_date').attr('min', today);
        },
        
        /**
         * Load membership discount for logged-in user via AJAX
         */
        _loadMembershipDiscount: function() {
            var self = this;
            
            ajax.jsonRpc('/sports/get_membership_discount', 'call', {
                user_id: this.currentUserId
            }).then(function(result) {
                if (result.success && result.discount) {
                    self.membershipDiscount = parseFloat(result.discount);
                    console.log('Membership discount loaded:', self.membershipDiscount + '%');
                    
                    // Show discount notification
                    if (self.membershipDiscount > 0) {
                        self._showDiscountNotification(self.membershipDiscount);
                    }
                }
            }).catch(function(error) {
                console.warn('Could not load membership discount:', error);
            });
        },
        
        /**
         * Show membership discount notification
         */
        _showDiscountNotification: function(discount) {
            var $notification = $('<div class="alert alert-success alert-dismissible fade show mt-3" role="alert">' +
                '<i class="fa fa-gift mr-2"></i>' +
                '<strong>Member Discount Applied!</strong> You will receive a ' + discount + '% discount on your booking.' +
                '<button type="button" class="close" data-dismiss="alert" aria-label="Close">' +
                '<span aria-hidden="true">&times;</span>' +
                '</button>' +
                '</div>');
            
            $('#booking_form').prepend($notification);
        },
        
        /**
         * Handle date change event - load available time slots
         */
        _onDateChange: function(selectedDate) {
            var self = this;
            
            if (!selectedDate) {
                return;
            }
            
            console.log('Date changed:', selectedDate);
            
            // Reset time slot
            $('#time_slot').prop('disabled', true).html('<option value="">Loading available slots...</option>');
            $('#submit_booking').prop('disabled', true);
            
            // Show loading spinner
            this._showLoading(true);
            
            // Call AJAX to check availability
            ajax.jsonRpc('/sports/check_availability', 'call', {
                facility_id: parseInt(this.facilityId),
                date: selectedDate
            }).then(function(result) {
                self._showLoading(false);
                
                if (result.success) {
                    self._populateTimeSlots(result.available_slots);
                    
                    // Update facility rate if provided in response
                    if (result.hourly_rate) {
                        self.facilityRate = parseFloat(result.hourly_rate);
                    }
                    if (result.currency) {
                        self.currencySymbol = result.currency;
                    }
                    
                    console.log('Available slots loaded:', result.available_slots.length);
                } else {
                    self._showError('Error loading time slots: ' + (result.error || 'Unknown error'));
                    $('#time_slot').html('<option value="">No available slots for this date</option>');
                }
            }).catch(function(error) {
                self._showLoading(false);
                self._showError('Failed to load available time slots. Please try again.');
                console.error('AJAX error:', error);
                $('#time_slot').html('<option value="">Error loading slots</option>');
            });
        },
        
        /**
         * Populate time slot dropdown with available slots
         */
        _populateTimeSlots: function(slots) {
            var $timeSlot = $('#time_slot');
            
            if (!slots || slots.length === 0) {
                $timeSlot.html('<option value="">No available slots for this date</option>');
                return;
            }
            
            var options = '<option value="">Select a time slot</option>';
            
            slots.forEach(function(slot) {
                options += '<option value="' + slot.start + '-' + slot.end + '" ' +
                          'data-start="' + slot.start_hour + '" ' +
                          'data-end="' + slot.end_hour + '">' +
                          slot.start + ' - ' + slot.end + '</option>';
            });
            
            $timeSlot.html(options).prop('disabled', false);
        },
        
        /**
         * Handle time slot change event - calculate cost
         */
        _onTimeSlotChange: function() {
            this._calculateTotalCost();
            this._updateHiddenDatetimeFields();
            this._updateSubmitButton();
        },
        
        /**
         * Handle equipment checkbox change event - calculate cost
         */
        _onEquipmentChange: function() {
            this._calculateTotalCost();
        },
        
        /**
         * Calculate total cost based on time slot and equipment
         */
        _calculateTotalCost: function() {
            var self = this;
            var $timeSlot = $('#time_slot option:selected');
            
            // Check if time slot is selected
            if (!$timeSlot.val()) {
                $('#total_cost').text('0.00');
                $('#cost_breakdown').text('Select date and time slot to calculate');
                return;
            }
            
            // Calculate duration
            var startHour = parseFloat($timeSlot.data('start'));
            var endHour = parseFloat($timeSlot.data('end'));
            var duration = endHour - startHour;
            
            if (isNaN(duration) || duration <= 0) {
                console.error('Invalid duration calculated');
                return;
            }
            
            // Calculate facility cost
            var facilityCost = duration * this.facilityRate;
            var equipmentCost = 0;
            
            // Calculate equipment cost
            this.selectedEquipment = [];
            $('.equipment-checkbox:checked').each(function() {
                var $checkbox = $(this);
                var equipmentId = $checkbox.val();
                var rate = parseFloat($checkbox.data('rate')) || 0;
                var equipmentItemCost = rate * duration;
                
                equipmentCost += equipmentItemCost;
                
                self.selectedEquipment.push({
                    id: equipmentId,
                    name: $checkbox.closest('.equipment-card').find('strong').text(),
                    rate: rate,
                    cost: equipmentItemCost
                });
            });
            
            // Calculate subtotal
            var subtotal = facilityCost + equipmentCost;
            
            // Apply membership discount
            var discountAmount = 0;
            if (this.membershipDiscount > 0) {
                discountAmount = (subtotal * this.membershipDiscount) / 100;
            }
            
            // Calculate final total
            var totalCost = subtotal - discountAmount;
            
            // Update display
            $('#total_cost').text(totalCost.toFixed(2));
            
            // Build cost breakdown
            var breakdown = 'Facility: ' + facilityCost.toFixed(2) + ' ' + this.currencySymbol;
            
            if (equipmentCost > 0) {
                breakdown += ' + Equipment: ' + equipmentCost.toFixed(2) + ' ' + this.currencySymbol;
            }
            
            if (discountAmount > 0) {
                breakdown += ' - Discount (' + this.membershipDiscount + '%): ' + 
                            discountAmount.toFixed(2) + ' ' + this.currencySymbol;
            }
            
            $('#cost_breakdown').text(breakdown);
            
            console.log('Cost calculated:', {
                facility: facilityCost,
                equipment: equipmentCost,
                discount: discountAmount,
                total: totalCost
            });
        },
        
        /**
         * Update hidden datetime fields for form submission
         */
        _updateHiddenDatetimeFields: function() {
            var date = $('#booking_date').val();
            var $timeSlot = $('#time_slot option:selected');
            
            if (date && $timeSlot.val()) {
                var startHour = parseInt($timeSlot.data('start'));
                var endHour = parseInt($timeSlot.data('end'));
                
                // Format datetime strings
                var startDatetime = date + ' ' + startHour.toString().padStart(2, '0') + ':00:00';
                var endDatetime = date + ' ' + endHour.toString().padStart(2, '0') + ':00:00';
                
                $('#start_datetime').val(startDatetime);
                $('#end_datetime').val(endDatetime);
                
                console.log('Hidden datetime fields updated:', startDatetime, endDatetime);
            }
        },
        
        /**
         * Update submit button state based on form validity
         */
        _updateSubmitButton: function() {
            var isValid = this._checkFormValidity();
            $('#submit_booking').prop('disabled', !isValid);
        },
        
        /**
         * Check if all required form fields are filled
         */
        _checkFormValidity: function() {
            var isValid = true;
            
            // Check required fields
            $('input[required], select[required]').each(function() {
                if (!$(this).val() || $(this).val().trim() === '') {
                    isValid = false;
                    return false; // Break loop
                }
            });
            
            // Check if time slot is selected
            if (!$('#time_slot').val()) {
                isValid = false;
            }
            
            return isValid;
        },
        
        /**
         * Validate form before submission
         */
        _validateForm: function(e) {
            var self = this;
            
            // Check basic validity
            if (!this._checkFormValidity()) {
                e.preventDefault();
                this._showError('Please fill in all required fields');
                return false;
            }
            
            // Validate email format
            var email = $('#customer_email').val();
            var emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(email)) {
                e.preventDefault();
                this._showError('Please enter a valid email address');
                return false;
            }
            
            // Validate phone format (basic check)
            var phone = $('#customer_phone').val();
            if (phone.length < 10) {
                e.preventDefault();
                this._showError('Please enter a valid phone number');
                return false;
            }
            
            // Validate date is not in the past
            var selectedDate = new Date($('#booking_date').val());
            var today = new Date();
            today.setHours(0, 0, 0, 0);
            
            if (selectedDate < today) {
                e.preventDefault();
                this._showError('Booking date cannot be in the past');
                return false;
            }
            
            // Show loading spinner during submission
            this._showLoading(true);
            $('#submit_booking').prop('disabled', true).html(
                '<i class="fa fa-spinner fa-spin mr-2"></i>Processing...'
            );
            
            console.log('Form validation passed, submitting...');
            return true;
        },
        
        /**
         * Show/hide loading spinner
         */
        _showLoading: function(show) {
            if (show) {
                // Create loading overlay if it doesn't exist
                if ($('#booking_loading_overlay').length === 0) {
                    var $overlay = $('<div id="booking_loading_overlay" style="' +
                        'position: fixed; top: 0; left: 0; width: 100%; height: 100%; ' +
                        'background: rgba(0,0,0,0.5); z-index: 9999; display: flex; ' +
                        'align-items: center; justify-content: center;">' +
                        '<div class="text-center" style="background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">' +
                        '<i class="fa fa-spinner fa-spin fa-3x text-primary mb-3"></i>' +
                        '<h4>Loading...</h4>' +
                        '<p class="text-muted mb-0">Please wait</p>' +
                        '</div>' +
                        '</div>');
                    $('body').append($overlay);
                }
                $('#booking_loading_overlay').fadeIn(200);
            } else {
                $('#booking_loading_overlay').fadeOut(200);
            }
        },
        
        /**
         * Show error message
         */
        _showError: function(message) {
            Dialog.alert(this, message, {
                title: _t('Error'),
                confirm_callback: function() {
                    // Reset submit button
                    $('#submit_booking').prop('disabled', false).html(
                        '<i class="fa fa-check-circle mr-2"></i>Confirm Booking'
                    );
                }
            });
        },
        
        /**
         * Show success message
         */
        _showSuccess: function(message) {
            Dialog.alert(this, message, {
                title: _t('Success')
            });
        }
    };
    
    /**
     * Initialize on document ready
     */
    $(document).ready(function() {
        // Only initialize if booking form exists on the page
        if ($('#booking_form').length) {
            BookingForm.init();
        }
    });
    
    // Export module
    return BookingForm;
});
