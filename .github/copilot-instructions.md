# Sports Facility Booking System - AI Coding Instructions

## Project Overview
This is an **Odoo 17/18 custom module** for managing sports facility bookings with equipment rental, membership discounts, and automated workflows. The module follows Odoo's MVC architecture with Python models, XML views, and web controllers.

**Key Tech Stack:** Odoo 17.0, Python 3.10+, PostgreSQL, XML (QWeb templates)

## Architecture & Data Flow

### Core Models (5-model system in `models/`)
1. **`sports.facility`** - Facilities with operating hours, hourly rates, and capacity constraints
2. **`sports.booking`** - Central booking entity with state workflow (`draft → confirmed → completed/cancelled`)
3. **`sports.equipment`** - Rental equipment with quantity tracking (`quantity_available` vs `total_quantity`)
4. **`sports.membership`** - Customer memberships providing automatic booking discounts (5-25%)
5. **`sports.timeslot`** - Time slot availability computation (not fully integrated yet)

### Critical Data Flow Pattern
**Booking confirmation triggers equipment checkout:**
```python
booking.action_confirm()  # Changes status, calls equipment.checkout_equipment()
→ Validates availability via check_facility_availability()
→ Decrements equipment.quantity_available for each equipment_ids item
→ Sends email notification (non-blocking on failure)
```

**Cost calculation with membership discount:**
```python
_compute_total_cost() runs whenever facility_id, duration, equipment_ids, or customer_id changes
→ Base cost = (facility.hourly_rate + sum(equipment.rental_rate)) * duration
→ Applies active membership discount_percentage if customer has valid membership on start_datetime
→ Final cost stored in total_cost field
```

### State Workflow Enforcement
- Bookings transition: `draft → confirmed → completed` OR `draft/confirmed → cancelled`
- Equipment checkout only happens on `action_confirm()`, returns on `action_complete()` or `action_cancel()`
- Cancellation refund policy: 100% (48h+), 50% (24-48h), 25% (12-24h), 0% (<12h)

## Development Patterns & Conventions

### Model Design Standards
**Always use these Odoo decorators:**
- `@api.depends()` for computed fields - list ALL dependencies including related fields
- `@api.constrains()` for validation - include detailed error messages with field values
- `@api.onchange()` for UI updates only (not for business logic in backend)
- `store=True` on computed fields used in searches/reports (e.g., `duration`, `total_cost`)

**Constraint pattern example (from `booking.py`):**
```python
@api.constrains('start_datetime', 'end_datetime', 'facility_id', 'status')
def check_facility_availability(self):
    overlapping = self.search([
        ('id', '!=', record.id),
        ('facility_id', '=', record.facility_id.id),
        ('status', 'in', ['draft', 'confirmed']),  # Exclude cancelled
        ('start_datetime', '<', record.end_datetime),
        ('end_datetime', '>', record.start_datetime),
    ])
    if overlapping:
        raise ValidationError(_(
            'Facility "%s" is not available...\nConflicting booking: %s'
        ) % (record.facility_id.name, overlapping[0].booking_reference))
```

### Field Naming Conventions
- Foreign keys: `<model>_id` (e.g., `facility_id`, `customer_id`)
- Many2many: `<model>_ids` (e.g., `equipment_ids`)
- Computed fields: descriptive names with `compute='_compute_<fieldname>'`
- Always add `help='...'` text for user documentation

### Error Handling Philosophy
**Non-blocking external services:**
```python
try:
    template.send_mail(record.id, force_send=True)
except Exception as e:
    _logger.warning('Failed to send email: %s', str(e))
    # Don't raise - email failure shouldn't block booking confirmation
```

**Strict validation for business rules:**
```python
if not self.check_availability(quantity):
    raise UserError(_('Insufficient quantity. Requested: %s, Available: %s'))
```

## Testing Approach

### Test Structure (see `tests/test_booking.py`)
Uses `TransactionCase` for database rollback between tests. Each test is independent:

```python
class TestSportsBooking(TransactionCase):
    def setUp(self):
        # Create test data: facility, equipment, customer
        self.start_datetime = datetime.now() + timedelta(days=1, hours=10)
    
    def test_double_booking_prevention(self):
        # Create confirmed booking, then assert overlapping raises ValidationError
        with self.assertRaises(ValidationError):
            # Create overlapping booking
```

**Testing checklist for new features:**
1. Happy path - normal record creation/workflow
2. Constraint validation - assert `ValidationError` raised with invalid data
3. Computed field accuracy - verify calculations with known values
4. State transition logic - confirm status changes and side effects
5. Edge cases - null values, boundary conditions, multi-day bookings

## Web Integration

### Controller Pattern (`controllers/main.py`)
Public routes for website booking interface:
```python
@http.route('/sports/facilities', type='http', auth='public', website=True)
def list_facilities(self, facility_type=None, **kwargs):
    domain = [('active', '=', True)]
    facilities = request.env['sports.facility'].sudo().search(domain)
    return request.render('sport_facility_system.facilities_list_template', values)
```

**JSON API for AJAX:**
```python
@http.route('/sports/check_availability', type='json', auth='public', methods=['POST'], csrf=False)
def check_availability(self, facility_id, date, **kwargs):
    # Returns {'success': True, 'available_slots': [...], 'hourly_rate': 25.0}
```

### View Architecture (`views/`)
**Always include these view types for new models:**
1. Form view - with `<header>` for state buttons, `<sheet>` for fields, `<div class="oe_chatter">` for mail thread
2. Tree view - with `decoration-*` attributes for color coding by status
3. Search view - filters by status, date ranges, and `<searchpanel>` for faceted search
4. Calendar view (for time-based models) - `date_start`, `date_stop`, `color` by related field

**Button pattern in form views:**
```xml
<button name="action_confirm" string="Confirm" type="object" 
        states="draft" class="oe_highlight"
        confirm="Confirm this booking?"/>
```

## Module Configuration

### Manifest Dependencies (`__manifest__.py`)
Required modules: `base`, `web`, `website`, `calendar`, `sale_management`, `mail`
- `mail` enables `_inherit = ['mail.thread', 'mail.activity.mixin']` for Chatter
- `sale_management` provides `digits='Product Price'` for monetary fields

### Data Loading Order (critical!)
```python
'data': [
    'security/ir.model.access.csv',  # ALWAYS FIRST - defines model access
    'views/facility_views.xml',
    'views/booking_views.xml',
    'views/templates/assets.xml',   # JS/CSS must load before templates using them
    'views/menu.xml',                # Menu items reference views
]
```

## Common Pitfalls & Gotchas

1. **Timezone handling in duration calculation** - Always use `pytz` and localize UTC datetimes before computing hours
2. **Equipment quantity validation** - Check `quantity_available >= quantity` BEFORE decrementing (atomic operation)
3. **Membership discount timing** - Discount applies based on `start_datetime.date()`, not current date
4. **Double booking check** - Must exclude `status='cancelled'` bookings from overlap search
5. **Computed field dependencies** - Include `'field_id.subfield'` for related field changes (e.g., `'facility_id.hourly_rate'`)
6. **Many2many checkout** - Loop through `equipment_ids` and call `checkout_equipment(quantity=1)` for each

## Development Workflow

**Running tests:**
```bash
odoo-bin -c odoo.conf -d test_db -i sport_facility_system --test-enable --stop-after-init
```

**Module upgrade after code changes:**
```bash
odoo-bin -c odoo.conf -d dev_db -u sport_facility_system
```

**Access model via shell:**
```python
booking = env['sports.booking'].search([('status', '=', 'draft')], limit=1)
booking.action_confirm()  # Test workflow methods interactively
```

## Future Enhancements (TODOs)
- Add `security/ir.model.access.csv` for access control (currently missing)
- Integrate `sports.timeslot` model into booking availability checks
- Implement website templates (referenced in controllers but not created yet)
- Add automated tests for `facility`, `equipment`, and `membership` models
- Create email templates for confirmation/cancellation (refs exist but templates missing)
