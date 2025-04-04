from odoo import models, fields, api
from datetime import timedelta
# logging
import logging
import json
import math

_logger = logging.getLogger(__name__)

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    mechanic_id = fields.One2many('pitcar.mechanic.new', 'employee_id', string='Mechanic Reference')
    is_mechanic = fields.Boolean(string='Is Mechanic', compute='_compute_is_mechanic', store=True)
    position_id = fields.Many2one(
        related='mechanic_id.position_id',
        string='Mechanic Position',
        readonly=True
    )
    monthly_target = fields.Float(
        related='mechanic_id.monthly_target',
        string='Monthly Target',
        readonly=True
    )
    current_revenue = fields.Float(
        related='mechanic_id.current_revenue',
        string='Current Revenue',
        readonly=True
    )
    attendance_achievement = fields.Float(
        related='mechanic_id.attendance_achievement',
        string='Attendance Achievement',
        readonly=True
    )
    face_descriptor = fields.Text(
        string='Face Descriptor', 
        help='Face encoding data for recognition'
    )
    face_image = fields.Binary('Face Image', attachment=True, help='Compressed face image for verification')
    
    # def _get_public_fields(self):
    #     """ Extend public fields """
    #     public_fields = super()._get_public_fields()
    #     return public_fields + ['is_mechanic', 'mechanic_id']

    fingerprint_data = fields.Binary(string='Fingerprint Data', attachment=False, help='Fingerprint template data')
    fingerprint_registered = fields.Boolean(string='Fingerprint Registered', default=False)
    webauthn_credentials = fields.Text(string='WebAuthn Credentials', help='WebAuthn credential data for fingerprint/biometric')
    fingerprint_device_id = fields.Char(string='Fingerprint Device ID', help='ID of registered fingerprint device')
    
    def register_fingerprint(self, fingerprint_data=None, webauthn_data=None, device_id=None):
        """Register fingerprint data for employee"""
        self.ensure_one()
        try:
            if fingerprint_data:
                # Save raw fingerprint template if provided by compatible device
                self.fingerprint_data = fingerprint_data
            
            if webauthn_data:
                # Save WebAuthn credential data (for browser-based biometric)
                self.webauthn_credentials = json.dumps(webauthn_data)
            
            if device_id:
                # Save fingerprint device ID
                self.fingerprint_device_id = device_id
                
            # Mark as registered
            self.fingerprint_registered = True
            return True
        except Exception as e:
            _logger.error(f"Error registering fingerprint: {e}")
            return False

    
    def _get_public_fields(self):
        """ Extend public fields """
        public_fields = super()._get_public_fields()
        return public_fields + [
            'mechanic_id',
            'is_mechanic'
        ]
    
    def _euclidean_distance(self, arr1, arr2):
        """Calculate Euclidean distance between two arrays"""
        if len(arr1) != len(arr2):
            return float('inf')
        
        sum_sq = 0.0
        for i in range(len(arr1)):
            diff = arr1[i] - arr2[i]
            sum_sq += diff * diff
        return math.sqrt(sum_sq)

    def verify_face(self, face_descriptor, threshold=0.6):
        """Verify face match with registered face"""
        if not self.face_descriptor:
            _logger.info("No registered face descriptor found")
            return False
        
        try:
            stored = json.loads(self.face_descriptor)
            
            # Normalize arrays to same length if needed
            if len(stored) != len(face_descriptor):
                _logger.error("Descriptor length mismatch")
                return False
                
            # Calculate distance with more lenient threshold
            distance = self._euclidean_distance(stored, face_descriptor)
            _logger.info(f"Face match distance: {distance}, threshold: {threshold}")
            
            return distance <= threshold  # Mungkin perlu sesuaikan threshold jadi lebih besar

        except Exception as e:
            _logger.error(f"Face verification error: {str(e)}")
            return False

    @api.depends('mechanic_id')
    def _compute_is_mechanic(self):
        for employee in self:
            employee.is_mechanic = bool(employee.mechanic_id)

    def create_mechanic(self):
        self.ensure_one()
        if not self.mechanic_id:
            default_position = self.env.ref('pitcar_custom.default_mechanic_position', raise_if_not_found=False)
            mechanic = self.env['pitcar.mechanic.new'].create({
                'name': self.name,
                'employee_id': self.id,
                'position_id': default_position and default_position.id or False,
            })
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'pitcar.mechanic.new',
                'res_id': mechanic.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return True

    def attendance_manual(self, next_action, entered_pin=None):
        res = super(HrEmployee, self).attendance_manual(next_action, entered_pin)
        if self.is_mechanic:
            # Additional logic for mechanic attendance
            pass
        return res