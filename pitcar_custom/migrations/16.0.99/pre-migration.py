from odoo import api, SUPERUSER_ID
from odoo.tools import logging

_logger = logging.getLogger(__name__)

def migrate(env, version):
    """
    Migrasi data mentor_id dari pitcar.mechanic.new ke hr.employee sebelum update modul.
    """
    _logger.info("Starting migration of pitcar.mentor.request mentor_id to hr.employee")
    
    # Ambil semua record pitcar.mentor.request yang memiliki mentor_id
    mentor_requests = env['pitcar.mentor.request'].search([('mentor_id', '!=', False)])
    
    if not mentor_requests:
        _logger.info("No mentor requests found to migrate.")
        return
    
    # Ambil semua mekanik untuk mapping ke employee
    mechanics = env['pitcar.mechanic.new'].search([])
    mechanic_to_employee_map = {
        mechanic.id: mechanic.employee_id.id 
        for mechanic in mechanics 
        if mechanic.employee_id  # Pastikan ada employee_id terkait
    }
    
    # Update mentor_id untuk setiap request
    for request in mentor_requests:
        old_mentor_id = request.mentor_id.id  # ID lama dari pitcar.mechanic.new
        new_mentor_id = mechanic_to_employee_map.get(old_mentor_id)  # Cari ID hr.employee yang sesuai
        
        if new_mentor_id:
            _logger.info(f"Migrating mentor_id for request {request.id}: {old_mentor_id} -> {new_mentor_id}")
            request.write({'mentor_id': new_mentor_id})
        else:
            # Jika tidak ada employee terkait, kosongkan mentor_id atau tangani sesuai kebutuhan
            _logger.warning(f"No employee found for mechanic ID {old_mentor_id} in request {request.id}. Setting mentor_id to False.")
            request.write({'mentor_id': False})
    
    _logger.info("Migration completed successfully.")