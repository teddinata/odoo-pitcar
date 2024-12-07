# models/work_location.py
from odoo import models, fields, api
from math import radians, sin, cos, sqrt, atan2

class WorkLocation(models.Model):
    _name = 'pitcar.work.location'
    _description = 'Work Location'

    name = fields.Char(string='Location Name', required=True)
    latitude = fields.Float(string='Latitude', digits=(16, 8), required=True)
    longitude = fields.Float(string='Longitude', digits=(16, 8), required=True)
    radius = fields.Integer(
        string='Allowed Radius (meters)', 
        default=100,
        help='Maximum allowed distance from this point for attendance'
    )
    active = fields.Boolean(default=True)
    address = fields.Text(string='Address')
    
    def calculate_distance(self, lat, lon):
        """
        Calculate distance using Haversine formula
        Returns distance in meters
        """
        R = 6371000  # Earth radius in meters

        lat1, lon1 = radians(self.latitude), radians(self.longitude)
        lat2, lon2 = radians(lat), radians(lon)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c

        return distance