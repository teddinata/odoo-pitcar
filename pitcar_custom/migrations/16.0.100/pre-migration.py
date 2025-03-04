from odoo import api, SUPERUSER_ID
from odoo.tools import logging

_logger = logging.getLogger(__name__)

def migrate(env, version):
    """
    Migrasi mentor_id dari pitcar.mechanic.new ke hr.employee dengan pembersihan constraint.
    """
    _logger.info("Starting migration of pitcar.mentor.request mentor_id from pitcar.mechanic.new to hr.employee")
    
    # Ambil semua record pitcar.mentor.request yang memiliki mentor_id
    mentor_requests = env['pitcar.mentor.request'].search([('mentor_id', '!=', False)])
    
    if not mentor_requests:
        _logger.info("No mentor requests with mentor_id found to migrate.")
        return
    
    # Mapping mekanik ke employee
    mechanics = env['pitcar.mechanic.new'].search([])
    mechanic_to_employee_map = {
        mechanic.id: mechanic.employee_id.id 
        for mechanic in mechanics 
        if mechanic.employee_id
    }
    
    # Update mentor_id
    for request in mentor_requests:
        old_mentor_id = request.mentor_id
        if isinstance(old_mentor_id, int):
            new_mentor_id = mechanic_to_employee_map.get(old_mentor_id)
        else:
            new_mentor_id = mechanic_to_employee_map.get(old_mentor_id.id) if old_mentor_id else False
        
        if new_mentor_id:
            _logger.info(f"Migrating mentor_id for request {request.id}: {old_mentor_id} -> {new_mentor_id}")
            request.write({'mentor_id': new_mentor_id})
        else:
            _logger.warning(f"No employee found for mechanic ID {old_mentor_id}. Setting mentor_id to False for request {request.id}.")
            request.write({'mentor_id': False})
    
    # Verifikasi dan log sisa data
    remaining_requests = env['pitcar.mentor.request'].search([('mentor_id', '!=', False)])
    if remaining_requests:
        _logger.warning(f"Found {len(remaining_requests)} requests still referencing old mentor_id after migration.")
        for req in remaining_requests:
            _logger.warning(f"Request {req.id} still has mentor_id: {req.mentor_id}")
    
    _logger.info("Migration completed.")