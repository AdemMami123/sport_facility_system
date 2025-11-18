# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class SportsEquipment(models.Model):
    _name = 'sports.equipment'
    _description = 'Sports Equipment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Equipment Name',
        required=True,
        index=True,
        tracking=True,
        help='Name of the equipment'
    )
    
    equipment_type = fields.Selection([
        ('ball', 'Ball'),
        ('racket', 'Racket'),
        ('net', 'Net'),
        ('mat', 'Mat'),
        ('weights', 'Weights'),
    ], string='Equipment Type', required=True,
       tracking=True,
       help='Type of sports equipment')
    
    quantity_available = fields.Integer(
        string='Quantity Available',
        default=0,
        tracking=True,
        help='Current quantity available for rental'
    )
    
    rental_rate = fields.Float(
        string='Rental Rate (Per Hour)',
        digits='Product Price',
        tracking=True,
        help='Hourly rental rate for this equipment'
    )
    
    condition = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ], string='Condition', default='good', required=True,
       tracking=True,
       help='Current condition of the equipment')
    
    facility_ids = fields.Many2many(
        'sports.facility',
        'sports_facility_equipment_rel',
        'equipment_id',
        'facility_id',
        string='Compatible Facilities',
        help='Facilities where this equipment can be used'
    )
    
    image = fields.Binary(
        string='Image',
        attachment=True,
        help='Image of the equipment'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to archive the equipment'
    )
    
    total_quantity = fields.Integer(
        string='Total Quantity',
        default=0,
        help='Total quantity of this equipment item'
    )
    
    quantity_in_use = fields.Integer(
        string='Quantity In Use',
        compute='_compute_quantity_in_use',
        store=True,
        help='Quantity currently checked out'
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

    _sql_constraints = [
        ('quantity_available_positive', 'CHECK(quantity_available >= 0)', 
         'Available quantity cannot be negative!'),
        ('total_quantity_positive', 'CHECK(total_quantity >= 0)', 
         'Total quantity cannot be negative!'),
    ]

    @api.depends('total_quantity', 'quantity_available')
    def _compute_quantity_in_use(self):
        for record in self:
            record.quantity_in_use = record.total_quantity - record.quantity_available

    @api.constrains('rental_rate')
    def _check_rental_rate(self):
        for record in self:
            if record.rental_rate < 0:
                raise ValidationError(_('Rental rate cannot be negative.'))

    @api.constrains('quantity_available', 'total_quantity')
    def _check_quantities(self):
        for record in self:
            if record.quantity_available > record.total_quantity:
                raise ValidationError(_(
                    'Available quantity cannot exceed total quantity.'
                ))

    def check_availability(self, quantity=1):
        """
        Check if the requested quantity of equipment is available
        
        :param quantity: Number of items to check availability for
        :return: True if available, False otherwise
        """
        self.ensure_one()
        return self.quantity_available >= quantity

    def checkout_equipment(self, quantity=1):
        """
        Checkout equipment by reducing the available quantity
        
        :param quantity: Number of items to checkout
        :return: True if successful
        :raises UserError: If insufficient quantity available
        """
        self.ensure_one()
        
        if not self.check_availability(quantity):
            raise UserError(_(
                'Insufficient quantity available. '
                'Requested: %s, Available: %s'
            ) % (quantity, self.quantity_available))
        
        self.quantity_available -= quantity
        return True

    def return_equipment(self, quantity=1):
        """
        Return equipment by increasing the available quantity
        
        :param quantity: Number of items to return
        :return: True if successful
        :raises ValidationError: If return would exceed total quantity
        """
        self.ensure_one()
        
        new_available = self.quantity_available + quantity
        if new_available > self.total_quantity:
            raise ValidationError(_(
                'Return quantity would exceed total quantity. '
                'Total: %s, Current Available: %s, Returning: %s'
            ) % (self.total_quantity, self.quantity_available, quantity))
        
        self.quantity_available = new_available
        return True

    @api.model
    def get_available_equipment(self, equipment_type=None, facility_id=None):
        """
        Get list of available equipment filtered by type and/or facility
        
        :param equipment_type: Filter by equipment type
        :param facility_id: Filter by compatible facility
        :return: Recordset of available equipment
        """
        domain = [('quantity_available', '>', 0), ('active', '=', True)]
        
        if equipment_type:
            domain.append(('equipment_type', '=', equipment_type))
        
        if facility_id:
            domain.append(('facility_ids', 'in', [facility_id]))
        
        return self.search(domain)

    def name_get(self):
        result = []
        for record in self:
            name = f"{record.name} ({record.quantity_available} available)"
            result.append((record.id, name))
        return result
