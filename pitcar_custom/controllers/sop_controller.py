# controllers/sop_controller.py
# =====================================
# COMPLETE SOP CONTROLLER WITH MIGRATION ENDPOINTS
# =====================================

from odoo import http, fields
from odoo.http import request, Response
import logging
import re
import pytz
from datetime import datetime, timedelta
import math
from io import StringIO
import csv
import json
import time

_logger = logging.getLogger(__name__)

class SOPController(http.Controller):
    
    def _get_request_data(self):
        """Helper to handle JSONRPC request data"""
        try:
            if request.jsonrequest:
                params = request.jsonrequest.get('params', {})
                _logger.info(f"JSONRPC Params received: {params}")
                return params
            return {}
        except Exception as e:
            _logger.error(f"Error parsing request data: {str(e)}")
            return {}
    
    def _check_migration_permission(self):
        """Check if user has permission to run migration"""
        user = request.env.user
        
        # Only allow admin or specific group
        if not user.has_group('base.group_system'):
            return False, "Only system administrators can run migration"
        
        return True, "Permission granted"
    
    def _get_migration_lock(self):
        """Get/Set migration lock to prevent concurrent migrations"""
        lock_key = 'sop.migration.lock'
        
        # Check if migration is already running
        existing_lock = request.env['ir.config_parameter'].sudo().get_param(lock_key)
        
        if existing_lock:
            try:
                lock_data = json.loads(existing_lock)
                lock_time = datetime.fromisoformat(lock_data['timestamp'])
                
                # If lock is older than 1 hour, consider it stale
                if datetime.now() - lock_time > timedelta(hours=1):
                    _logger.warning("Stale migration lock detected, clearing...")
                    request.env['ir.config_parameter'].sudo().set_param(lock_key, '')
                else:
                    return False, f"Migration already running by {lock_data['user']} since {lock_data['timestamp']}"
            except:
                # Invalid lock data, clear it
                request.env['ir.config_parameter'].sudo().set_param(lock_key, '')
        
        # Set new lock
        lock_data = {
            'user': request.env.user.name,
            'timestamp': datetime.now().isoformat(),
            'process_id': f"migration_{int(time.time())}"
        }
        
        request.env['ir.config_parameter'].sudo().set_param(lock_key, json.dumps(lock_data))
        return True, "Lock acquired"
    
    def _release_migration_lock(self):
        """Release migration lock"""
        lock_key = 'sop.migration.lock'
        request.env['ir.config_parameter'].sudo().set_param(lock_key, '')
        
    def _get_employee_domain(self, role):
        """Get domain for employee based on role"""
        domains = {
            'sa': [],  # Using service.advisor model
            'mechanic': [],  # Using mechanic.new model
            'valet': [('job_id.name', 'ilike', 'valet')],
            'part_support': [('job_id.name', 'ilike', 'part')],
            'cs': [('job_id.name', 'ilike', 'customer service')],
            'lead_mechanic': [('job_id.name', 'ilike', 'lead mechanic')],
            'lead_cs': [('job_id.name', 'ilike', 'lead customer service')],
            'head_workshop': [('job_id.name', 'ilike', 'kepala bengkel')]
        }
        return domains.get(role, [])

    def _get_sop_domain(self, role=None, department=None, sampling_type=None, search=None):
        """Build domain for SOP search"""
        domain = [('active', '=', True)]
        
        if role:
            domain.append(('role', '=', role))
        if department:
            domain.append(('department', '=', department))
        if sampling_type:
            # If sampling_type is specified, get SOPs valid for that type
            if sampling_type == 'kaizen':
                domain.append(('sampling_type', 'in', ['kaizen', 'both']))
            elif sampling_type == 'lead':
                domain.append(('sampling_type', 'in', ['lead', 'both']))
        if search:
            for term in search.split():
                domain.extend(['|', '|',
                    ('name', 'ilike', term),
                    ('code', 'ilike', term),
                    ('description', 'ilike', term)
                ])
        
        return domain
    
    def _get_department_filters(self):
        """Get department filters based on migration status"""
        # Check if migration is active
        migration_active = request.env['ir.config_parameter'].sudo().get_param('sop.migration.active', default=False)
        
        if migration_active:
            # Show both old and new departments during migration
            return [
                # Old departments
                {'value': 'service', 'label': 'Service (Legacy)', 'legacy': True},
                {'value': 'sparepart', 'label': 'Spare Part (Legacy)', 'legacy': True},
                {'value': 'cs', 'label': 'Customer Service (Legacy)', 'legacy': True},
                # New departments
                {'value': 'mekanik', 'label': 'Mekanik', 'legacy': False},
                {'value': 'support', 'label': 'Support', 'legacy': False}
            ]
        else:
            # Show only new departments after migration
            return [
                {'value': 'mekanik', 'label': 'Mekanik'},
                {'value': 'support', 'label': 'Support'}
            ]
    
    def _get_role_filters(self):
        """Get role filters with department mapping"""
        return [
            # Mekanik department roles
            {'value': 'mechanic', 'label': 'Mechanic', 'department': 'mekanik'},
            {'value': 'lead_mechanic', 'label': 'Lead Mechanic', 'department': 'mekanik'},
            {'value': 'head_workshop', 'label': 'Kepala Bengkel', 'department': 'mekanik'},
            
            # Support department roles
            {'value': 'sa', 'label': 'Service Advisor', 'department': 'support'},
            {'value': 'valet', 'label': 'Valet Parking', 'department': 'support'},
            {'value': 'part_support', 'label': 'Part Support', 'department': 'support'},
            {'value': 'cs', 'label': 'Customer Service', 'department': 'support'},
            {'value': 'lead_cs', 'label': 'Lead Customer Service', 'department': 'support'}
        ]
    
    def _get_department_label(self, department):
        """Get department label (migration-aware)"""
        labels = {
            # Old departments
            'service': 'Service',
            'sparepart': 'Spare Part',
            'cs': 'Customer Service',
            # New departments
            'mekanik': 'Mekanik',
            'support': 'Support'
        }
        return labels.get(department, department)
    
    def _get_migration_summary(self):
        """Get migration summary statistics"""
        SOP = request.env['pitcar.sop'].sudo()
        
        total = SOP.search_count([('active', '=', True)])
        migrated = SOP.search_count([('active', '=', True), ('is_migrated', '=', True)])
        pending = total - migrated
        
        # Count by new departments
        mekanik_count = SOP.search_count([('active', '=', True), ('department_new', '=', 'mekanik')])
        support_count = SOP.search_count([('active', '=', True), ('department_new', '=', 'support')])
        
        return {
            'total': total,
            'migrated': migrated,
            'pending': pending,
            'progress_percentage': round((migrated / total * 100), 2) if total > 0 else 0,
            'new_structure': {
                'mekanik': mekanik_count,
                'support': support_count
            }
        }

    def _format_employee_info(self, sampling):
        """Format employee info based on role"""
        return {
            'service_advisor': [{
                'id': sa.id,
                'name': sa.name
            } for sa in sampling.sa_id] if sampling.sa_id else [],
            
            'mechanic': [{
                'id': mech.id,
                'name': mech.name
            } for mech in sampling.mechanic_id] if sampling.mechanic_id else [],
            
            'valet': [{
                'id': val.id,
                'name': val.name
            } for val in sampling.valet_id] if sampling.valet_id else [],
            
            'part_support': [{
                'id': ps.id,
                'name': ps.name
            } for ps in sampling.part_support_id] if sampling.part_support_id else [],
            
            'customer_service': [{
                'id': cs.id,
                'name': cs.name
            } for cs in sampling.cs_id] if sampling.cs_id else [],
            
            # Add new leadership roles
            'lead_mechanic': [{
                'id': lm.id,
                'name': lm.name
            } for lm in sampling.lead_mechanic_id] if sampling.lead_mechanic_id else [],
            
            'lead_customer_service': [{
                'id': lcs.id,
                'name': lcs.name
            } for lcs in sampling.lead_cs_id] if sampling.lead_cs_id else [],
            
            'head_workshop': [{
                'id': hw.id,
                'name': hw.name
            } for hw in sampling.head_workshop_id] if sampling.head_workshop_id else [],
        }

    # =====================================
    # MIGRATION ENDPOINTS
    # =====================================

    @http.route('/web/sop/migration/status', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_migration_status(self, **kw):
        """Get current migration status"""
        try:
            SOP = request.env['pitcar.sop'].sudo()
            
            # Check if migration is initialized
            migration_initialized = request.env['ir.config_parameter'].sudo().get_param('sop.migration.initialized', 'False')
            
            # Get basic counts
            total_sops = SOP.search_count([('active', '=', True)])
            migrated_sops = SOP.search_count([('active', '=', True), ('is_migrated', '=', True)])
            pending_sops = total_sops - migrated_sops
            
            # Get migration lock status
            lock_key = 'sop.migration.lock'
            migration_lock = request.env['ir.config_parameter'].sudo().get_param(lock_key)
            is_locked = bool(migration_lock)
            
            # Get department distribution
            dept_stats = {
                'legacy': {
                    'service': SOP.search_count([('active', '=', True), ('department_old', '=', 'service')]),
                    'sparepart': SOP.search_count([('active', '=', True), ('department_old', '=', 'sparepart')]),
                    'cs': SOP.search_count([('active', '=', True), ('department_old', '=', 'cs')])
                },
                'new': {
                    'mekanik': SOP.search_count([('active', '=', True), ('department_new', '=', 'mekanik')]),
                    'support': SOP.search_count([('active', '=', True), ('department_new', '=', 'support')])
                }
            }
            
            # Get recent migration activity
            recent_migrations = SOP.search([
                ('active', '=', True),
                ('is_migrated', '=', True),
                ('migration_date', '!=', False)
            ], order='migration_date desc', limit=5)
            
            recent_activity = []
            for sop in recent_migrations:
                recent_activity.append({
                    'code': sop.code,
                    'name': sop.name,
                    'old_dept': sop.department_old,
                    'new_dept': sop.department_new,
                    'migration_date': sop.migration_date.strftime('%Y-%m-%d %H:%M:%S')
                })
            
            return {
                'status': 'success',
                'data': {
                    'migration_status': {
                        'initialized': migration_initialized.lower() == 'true',
                        'total_sops': total_sops,
                        'migrated_sops': migrated_sops,
                        'pending_sops': pending_sops,
                        'progress_percentage': round((migrated_sops / total_sops * 100), 2) if total_sops > 0 else 0,
                        'is_locked': is_locked,
                        'lock_info': json.loads(migration_lock) if migration_lock else None
                    },
                    'department_stats': dept_stats,
                    'recent_activity': recent_activity,
                    'can_migrate': pending_sops > 0,
                    'can_rollback': migrated_sops > 0
                }
            }
        
        except Exception as e:
            _logger.error(f"Error in get_migration_status: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/migration/initialize', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def initialize_migration(self, **kw):
        """Initialize migration system - prepare existing data"""
        try:
            # Check permission
            has_permission, message = self._check_migration_permission()
            if not has_permission:
                return {'status': 'error', 'message': message}
            
            # Check if already initialized
            migration_initialized = request.env['ir.config_parameter'].sudo().get_param('sop.migration.initialized', 'False')
            if migration_initialized.lower() == 'true':
                return {'status': 'error', 'message': 'Migration already initialized'}
            
            # Get lock
            lock_acquired, lock_message = self._get_migration_lock()
            if not lock_acquired:
                return {'status': 'error', 'message': lock_message}
            
            try:
                # Step 1: Update existing records to set department_old
                _logger.info("Initializing migration: Setting department_old for existing records")
                
                request.env.cr.execute("""
                    UPDATE pitcar_sop 
                    SET department_old = department 
                    WHERE department_old IS NULL AND active = TRUE;
                """)
                
                updated_count = request.env.cr.rowcount
                request.env.cr.commit()
                
                # Step 2: Mark as initialized
                request.env['ir.config_parameter'].sudo().set_param('sop.migration.initialized', 'True')
                request.env['ir.config_parameter'].sudo().set_param('sop.migration.init_date', datetime.now().isoformat())
                
                # Step 3: Create initialization log
                request.env['ir.logging'].sudo().create({
                    'name': 'sop.migration',
                    'level': 'INFO',
                    'message': f'Migration initialized: {updated_count} records prepared',
                    'func': 'initialize_migration',
                    'path': 'sop_migration',
                    'line': 0,
                    'type': 'server'
                })
                
                return {
                    'status': 'success',
                    'message': f'Migration initialized successfully. {updated_count} records prepared.',
                    'data': {
                        'updated_count': updated_count,
                        'initialization_date': datetime.now().isoformat()
                    }
                }
            
            finally:
                # Always release lock
                self._release_migration_lock()
        
        except Exception as e:
            self._release_migration_lock()
            _logger.error(f"Error in initialize_migration: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/migration/execute', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def execute_migration(self, **kw):
        """Execute migration - move data to new structure"""
        try:
            # Check permission
            has_permission, message = self._check_migration_permission()
            if not has_permission:
                return {'status': 'error', 'message': message}
            
            # Check if initialized
            migration_initialized = request.env['ir.config_parameter'].sudo().get_param('sop.migration.initialized', 'False')
            if migration_initialized.lower() != 'true':
                return {'status': 'error', 'message': 'Migration not initialized. Please initialize first.'}
            
            # Get parameters
            batch_size = int(kw.get('batch_size', 100))  # Process in batches
            department_filter = kw.get('department_filter')  # Optional: migrate specific department
            dry_run = kw.get('dry_run', False)  # Preview mode
            
            # Get lock
            lock_acquired, lock_message = self._get_migration_lock()
            if not lock_acquired:
                return {'status': 'error', 'message': lock_message}
            
            try:
                # Build domain for records to migrate
                domain = [('active', '=', True), ('is_migrated', '=', False)]
                
                if department_filter and department_filter in ['service', 'sparepart', 'cs']:
                    domain.append(('department_old', '=', department_filter))
                
                # Get records to migrate
                SOP = request.env['pitcar.sop'].sudo()
                sops_to_migrate = SOP.search(domain, limit=batch_size)
                
                if not sops_to_migrate:
                    return {
                        'status': 'success',
                        'message': 'No records to migrate',
                        'data': {'migrated_count': 0}
                    }
                
                # Preview mode - just show what would be migrated
                if dry_run:
                    preview_data = []
                    for sop in sops_to_migrate:
                        if sop.role in ['mechanic', 'lead_mechanic', 'head_workshop']:
                            new_dept = 'mekanik'
                        else:
                            new_dept = 'support'
                        
                        preview_data.append({
                            'id': sop.id,
                            'code': sop.code,
                            'name': sop.name,
                            'role': sop.role,
                            'current_dept': sop.department_old,
                            'new_dept': new_dept
                        })
                    
                    return {
                        'status': 'success',
                        'message': f'Preview: {len(preview_data)} records would be migrated',
                        'data': {
                            'preview': preview_data,
                            'total_count': len(preview_data)
                        }
                    }
                
                # Execute actual migration
                migration_log = []
                success_count = 0
                error_count = 0
                
                for sop in sops_to_migrate:
                    try:
                        # Determine new department based on role
                        if sop.role in ['mechanic', 'lead_mechanic', 'head_workshop']:
                            new_dept = 'mekanik'
                        else:  # SA, valet, part_support, cs, lead_cs
                            new_dept = 'support'
                        
                        # Update record
                        sop.write({
                            'department_new': new_dept,
                            'is_migrated': True,
                            'migration_date': fields.Datetime.now()
                        })
                        
                        # Log success
                        migration_log.append({
                            'code': sop.code,
                            'name': sop.name,
                            'role': sop.role,
                            'old_dept': sop.department_old,
                            'new_dept': new_dept,
                            'status': 'success'
                        })
                        
                        success_count += 1
                        
                    except Exception as e:
                        # Log error
                        migration_log.append({
                            'code': sop.code,
                            'name': sop.name,
                            'role': sop.role,
                            'old_dept': sop.department_old,
                            'status': 'error',
                            'error': str(e)
                        })
                        
                        error_count += 1
                        _logger.error(f"Error migrating SOP {sop.code}: {str(e)}")
                
                # Commit changes
                request.env.cr.commit()
                
                # Create migration log entry
                request.env['ir.logging'].sudo().create({
                    'name': 'sop.migration',
                    'level': 'INFO',
                    'message': f'Migration batch completed: {success_count} success, {error_count} errors',
                    'func': 'execute_migration',
                    'path': 'sop_migration',
                    'line': 0,
                    'type': 'server'
                })
                
                return {
                    'status': 'success',
                    'message': f'Migration completed: {success_count} records migrated, {error_count} errors',
                    'data': {
                        'migrated_count': success_count,
                        'error_count': error_count,
                        'migration_log': migration_log,
                        'has_more': len(sops_to_migrate) == batch_size  # Indicate if more batches needed
                    }
                }
            
            finally:
                # Always release lock
                self._release_migration_lock()
        
        except Exception as e:
            self._release_migration_lock()
            _logger.error(f"Error in execute_migration: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/migration/rollback', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def rollback_migration(self, **kw):
        """Rollback migration - restore to original state"""
        try:
            # Check permission
            has_permission, message = self._check_migration_permission()
            if not has_permission:
                return {'status': 'error', 'message': message}
            
            # Get parameters
            batch_size = int(kw.get('batch_size', 100))
            department_filter = kw.get('department_filter')  # Optional: rollback specific department
            confirm = kw.get('confirm', False)  # Confirmation required
            
            if not confirm:
                return {'status': 'error', 'message': 'Rollback confirmation required'}
            
            # Get lock
            lock_acquired, lock_message = self._get_migration_lock()
            if not lock_acquired:
                return {'status': 'error', 'message': lock_message}
            
            try:
                # Build domain for records to rollback
                domain = [('active', '=', True), ('is_migrated', '=', True)]
                
                if department_filter and department_filter in ['mekanik', 'support']:
                    domain.append(('department_new', '=', department_filter))
                
                # Get records to rollback
                SOP = request.env['pitcar.sop'].sudo()
                sops_to_rollback = SOP.search(domain, limit=batch_size)
                
                if not sops_to_rollback:
                    return {
                        'status': 'success',
                        'message': 'No records to rollback',
                        'data': {'rollback_count': 0}
                    }
                
                # Execute rollback
                rollback_log = []
                success_count = 0
                error_count = 0
                
                for sop in sops_to_rollback:
                    try:
                        # Restore original state
                        sop.write({
                            'department_new': False,
                            'is_migrated': False,
                            'migration_date': False
                        })
                        
                        # Log success
                        rollback_log.append({
                            'code': sop.code,
                            'name': sop.name,
                            'restored_dept': sop.department_old,
                            'status': 'success'
                        })
                        
                        success_count += 1
                        
                    except Exception as e:
                        # Log error
                        rollback_log.append({
                            'code': sop.code,
                            'name': sop.name,
                            'status': 'error',
                            'error': str(e)
                        })
                        
                        error_count += 1
                        _logger.error(f"Error rolling back SOP {sop.code}: {str(e)}")
                
                # Commit changes
                request.env.cr.commit()
                
                # Create rollback log entry
                request.env['ir.logging'].sudo().create({
                    'name': 'sop.migration',
                    'level': 'WARNING',
                    'message': f'Migration rollback completed: {success_count} success, {error_count} errors',
                    'func': 'rollback_migration',
                    'path': 'sop_migration',
                    'line': 0,
                    'type': 'server'
                })
                
                return {
                    'status': 'success',
                    'message': f'Rollback completed: {success_count} records restored, {error_count} errors',
                    'data': {
                        'rollback_count': success_count,
                        'error_count': error_count,
                        'rollback_log': rollback_log,
                        'has_more': len(sops_to_rollback) == batch_size
                    }
                }
            
            finally:
                # Always release lock
                self._release_migration_lock()
        
        except Exception as e:
            self._release_migration_lock()
            _logger.error(f"Error in rollback_migration: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/migration/validate', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def validate_migration(self, **kw):
        """Validate migration results"""
        try:
            SOP = request.env['pitcar.sop'].sudo()
            
            # Get all active SOPs
            all_sops = SOP.search([('active', '=', True)])
            
            # Validation results
            validation_results = {
                'total_sops': len(all_sops),
                'migrated_sops': 0,
                'pending_sops': 0,
                'validation_errors': [],
                'warnings': [],
                'department_distribution': {
                    'mekanik': 0,
                    'support': 0
                },
                'role_distribution': {}
            }
            
            # Check each SOP
            for sop in all_sops:
                if sop.is_migrated:
                    validation_results['migrated_sops'] += 1
                    
                    # Validate role-department compatibility
                    if sop.department_new == 'mekanik':
                        validation_results['department_distribution']['mekanik'] += 1
                        
                        if sop.role not in ['mechanic', 'lead_mechanic', 'head_workshop']:
                            validation_results['validation_errors'].append({
                                'type': 'role_department_mismatch',
                                'sop_code': sop.code,
                                'sop_name': sop.name,
                                'role': sop.role,
                                'department': sop.department_new,
                                'message': f'Role {sop.role} should not be in mekanik department'
                            })
                    
                    elif sop.department_new == 'support':
                        validation_results['department_distribution']['support'] += 1
                        
                        if sop.role not in ['sa', 'valet', 'part_support', 'cs', 'lead_cs']:
                            validation_results['validation_errors'].append({
                                'type': 'role_department_mismatch',
                                'sop_code': sop.code,
                                'sop_name': sop.name,
                                'role': sop.role,
                                'department': sop.department_new,
                                'message': f'Role {sop.role} should not be in support department'
                            })
                    
                    # Count role distribution
                    if sop.role in validation_results['role_distribution']:
                        validation_results['role_distribution'][sop.role] += 1
                    else:
                        validation_results['role_distribution'][sop.role] = 1
                
                else:
                    validation_results['pending_sops'] += 1
                    
                    # Check if department_old is set
                    if not sop.department_old:
                        validation_results['warnings'].append({
                            'type': 'missing_department_old',
                            'sop_code': sop.code,
                            'sop_name': sop.name,
                            'message': 'Missing department_old field'
                        })
            
            # Calculate migration progress
            if validation_results['total_sops'] > 0:
                validation_results['migration_progress'] = round(
                    (validation_results['migrated_sops'] / validation_results['total_sops'] * 100), 2
                )
            else:
                validation_results['migration_progress'] = 0
            
            # Overall validation status
            if validation_results['validation_errors']:
                validation_status = 'failed'
                validation_message = f"Validation failed: {len(validation_results['validation_errors'])} errors found"
            elif validation_results['warnings']:
                validation_status = 'warning'
                validation_message = f"Validation passed with {len(validation_results['warnings'])} warnings"
            else:
                validation_status = 'success'
                validation_message = "All validations passed successfully"
            
            return {
                'status': validation_status,
                'message': validation_message,
                'data': validation_results
            }
        
        except Exception as e:
            _logger.error(f"Error in validate_migration: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/migration/logs', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_migration_logs(self, **kw):
        """Get migration logs"""
        try:
            # Parameters
            limit = int(kw.get('limit', 50))
            level = kw.get('level', 'INFO')  # INFO, WARNING, ERROR
            
            # Get logs
            logs = request.env['ir.logging'].sudo().search([
                ('name', '=', 'sop.migration'),
                ('level', '=', level)
            ], limit=limit, order='create_date desc')
            
            log_data = []
            for log in logs:
                log_data.append({
                    'id': log.id,
                    'level': log.level,
                    'message': log.message,
                    'func': log.func,
                    'create_date': log.create_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'type': log.type
                })
            
            return {
                'status': 'success',
                'data': {
                    'logs': log_data,
                    'total_count': len(log_data)
                }
            }
        
        except Exception as e:
            _logger.error(f"Error in get_migration_logs: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    # =====================================
    # EXISTING SOP ENDPOINTS (UPDATED)
    # =====================================

    @http.route('/web/sop/master/list', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_sop_list(self, **kw):
        try:
            # Parameters
            page = max(1, int(kw.get('page', 1)))
            limit = max(1, min(100, int(kw.get('limit', 25))))
            role = kw.get('role')
            department = kw.get('department')
            sampling_type = kw.get('sampling_type')
            search = (kw.get('search') or '').strip()
            
            # Migration-aware parameters
            show_migrated_only = kw.get('show_migrated_only', False)
            show_legacy_only = kw.get('show_legacy_only', False)
            
            # Sort parameters
            sort_by = kw.get('sort_by', 'code')
            sort_order = kw.get('sort_order', 'asc')
            
            # Build domain
            domain = [('active', '=', True)]
            
            # Migration filters
            if show_migrated_only:
                domain.append(('is_migrated', '=', True))
            elif show_legacy_only:
                domain.append(('is_migrated', '=', False))
            
            # Role filter
            if role:
                domain.append(('role', '=', role))
            
            # Department filter (handles both old and new)
            if department:
                if department in ['mekanik', 'support']:
                    # New department structure
                    domain.append(('department_new', '=', department))
                elif department in ['service', 'sparepart', 'cs']:
                    # Old department structure
                    domain.append(('department_old', '=', department))
            
            # Other filters
            if sampling_type:
                domain.append(('sampling_type', '=', sampling_type))
            
            # Search filter
            if search:
                for term in search.split():
                    domain.extend(['|', '|', '|', '|',
                        ('name', 'ilike', term),
                        ('code', 'ilike', term),
                        ('description', 'ilike', term),
                        ('notes', 'ilike', term),
                        ('document_url', 'ilike', term)
                    ])
            
            # Get data
            SOP = request.env['pitcar.sop'].sudo()
            total_count = SOP.search_count(domain)
            offset = (page - 1) * limit
            sops = SOP.search(domain, limit=limit, offset=offset, order=f'{sort_by} {sort_order}')

            # Format response
            rows = []
            for sop in sops:
                # Determine current department (migration-aware)
                current_dept = sop.department_new if sop.is_migrated else sop.department_old
                current_dept_label = self._get_department_label(current_dept)
                
                row = {
                    'id': sop.id,
                    'code': sop.code,
                    'name': sop.name,
                    'description': sop.description,
                    
                    # Migration-aware department fields
                    'department': current_dept,
                    'department_label': current_dept_label,
                    'department_old': sop.department_old,
                    'department_new': sop.department_new,
                    'is_migrated': sop.is_migrated,
                    'migration_date': sop.migration_date.strftime('%Y-%m-%d %H:%M:%S') if sop.migration_date else None,
                    
                    # Role info
                    'role': sop.role,
                    'role_label': dict(sop._fields['role'].selection).get(sop.role, ''),
                    
                    # Other fields
                    'sampling_type': sop.sampling_type,
                    'sampling_type_label': dict(sop._fields['sampling_type'].selection).get(sop.sampling_type, ''),
                    'activity_type': sop.activity_type,
                    'state': sop.state,
                    'notes': sop.notes,
                    'sequence': sop.sequence,
                    
                    # Migration status indicators
                    'migration_status': 'migrated' if sop.is_migrated else 'pending'
                }
                rows.append(row)

            # Migration summary
            migration_summary = self._get_migration_summary()

            return {
                'status': 'success',
                'data': {
                    'rows': rows,
                    'pagination': {
                        'total_items': total_count,
                        'total_pages': math.ceil(total_count / limit) if total_count > 0 else 1,
                        'current_page': page,
                        'items_per_page': limit,
                        'has_next': page * limit < total_count,
                        'has_previous': page > 1
                    },
                    'filters': {
                        'departments': self._get_department_filters(),
                        'roles': self._get_role_filters(),
                        'sampling_types': [
                            {'value': 'kaizen', 'label': 'Kaizen Team'},
                            {'value': 'lead', 'label': 'Leader'},
                            {'value': 'both', 'label': 'Both'}
                        ]
                    },
                    'migration_summary': migration_summary
                }
            }

        except Exception as e:
            _logger.error(f"Error dalam get_sop_list: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/sampling/available-orders', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_available_orders(self, **kw):
        """Get list of available sale orders for sampling"""
        try:
            # Get parameters from request
            page = max(1, int(kw.get('page', 1)))
            limit = max(1, min(100, int(kw.get('limit', 25))))
            search = (kw.get('search') or '').strip()
            is_sa = kw.get('is_sa')
            date_from = kw.get('date_from')
            date_to = kw.get('date_to')
            sampling_type = kw.get('sampling_type')  # New parameter

            # Debug log
            _logger.info(f"Received parameters: {kw}")

            # Base domain untuk sale orders yang aktif
            domain = [('state', 'in', ['draft', 'sent', 'sale', 'done'])]

            # Search dengan multiple terms
            if search:
                search_terms = search.split()
                for term in search_terms:
                    domain.extend(['|', '|', '|', '|',
                        ('name', 'ilike', term),
                        ('partner_car_id.number_plate', 'ilike', term),
                        ('car_mechanic_id_new.name', 'ilike', term),
                        ('service_advisor_id.name', 'ilike', term),
                        ('partner_id.name', 'ilike', term)
                    ])

            # Filter berdasarkan tipe SOP (SA/Mekanik)
            if isinstance(is_sa, bool):
                if is_sa:
                    domain.append(('service_advisor_id', '!=', False))
                else:
                    domain.append(('car_mechanic_id_new', '!=', False))
            elif isinstance(is_sa, str):
                if is_sa.lower() == 'true':
                    domain.append(('service_advisor_id', '!=', False))
                elif is_sa.lower() == 'false':
                    domain.append(('car_mechanic_id_new', '!=', False))

            # Date range filter
            if date_from:
                try:
                    domain.append(('create_date', '>=', date_from))
                except Exception as e:
                    _logger.warning(f"Invalid date_from format: {date_from}")

            if date_to:
                try:
                    domain.append(('create_date', '<=', date_to))
                except Exception as e:
                    _logger.warning(f"Invalid date_to format: {date_to}")

            # Use sudo() for consistent access
            SaleOrder = request.env['sale.order'].sudo()
            
            # Get total before pagination
            total_count = SaleOrder.search_count(domain)
            
            # Get records with pagination
            offset = (page - 1) * limit
            orders = SaleOrder.search(domain, limit=limit, offset=offset, order='create_date desc')

            rows = []
            for order in orders:
                # Format mechanic data
                mechanic_data = [{
                    'id': mech.id,
                    'name': mech.name,
                    'sampling_count': len(order.sop_sampling_ids.filtered(
                        lambda s: s.sop_id.role == 'mechanic' and mech.id in s.mechanic_id.ids
                    ))
                } for mech in order.car_mechanic_id_new] if order.car_mechanic_id_new else []

                # Format SA data
                sa_data = [{
                    'id': sa.id,
                    'name': sa.name,
                    'sampling_count': len(order.sop_sampling_ids.filtered(
                        lambda s: s.sop_id.role == 'sa' and sa.id in s.sa_id.ids
                    ))
                } for sa in order.service_advisor_id] if order.service_advisor_id else []

                row = {
                    'id': order.id,
                    'name': order.name,
                    'date': order.create_date.strftime('%Y-%m-%d %H:%M:%S') if order.create_date else None,
                    'car_info': {
                        'plate': order.partner_car_id.number_plate if order.partner_car_id else None,
                        'brand': order.partner_car_brand.name if order.partner_car_brand else None,
                        'type': order.partner_car_brand_type.name if order.partner_car_brand_type else None
                    },
                    'customer': {
                        'id': order.partner_id.id,
                        'name': order.partner_id.name
                    } if order.partner_id else None,
                    'employee_info': {
                        'mechanic': mechanic_data,
                        'service_advisor': sa_data
                    },
                    'sampling_count': {
                        'total': len(order.sop_sampling_ids),
                        'kaizen': len(order.sop_sampling_ids.filtered(lambda s: s.sampling_type == 'kaizen')),
                        'lead': len(order.sop_sampling_ids.filtered(lambda s: s.sampling_type == 'lead'))
                    }
                }
                rows.append(row)

            return {
                'status': 'success',
                'data': {
                    'rows': rows,
                    'pagination': {
                        'total_items': total_count,
                        'total_pages': math.ceil(total_count / limit) if total_count > 0 else 1,
                        'current_page': page,
                        'items_per_page': limit
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error in get_available_orders: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/sampling/create', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def create_sampling(self, **kw):
        """Create sampling with migration-aware department handling"""
        try:
            # Required parameters
            sale_order_id = kw.get('sale_order_id')
            sop_id = kw.get('sop_id')
            employee_ids = kw.get('employee_ids', [])
            notes = kw.get('notes')
            sampling_type = kw.get('sampling_type', 'kaizen')

            if not sale_order_id or not sop_id:
                return {
                    'status': 'error',
                    'message': 'Sale order and SOP are required'
                }

            # Get SOP and validate
            sop = request.env['pitcar.sop'].sudo().browse(sop_id)
            if not sop.exists():
                return {'status': 'error', 'message': 'SOP not found'}
            
            # Migration-aware department validation
            current_dept = sop.department_new if sop.is_migrated else sop.department_old
            
            # Log migration status for debugging
            _logger.info(f"Creating sampling for SOP {sop.code} - Migration status: {sop.is_migrated}, Current dept: {current_dept}")
            
            # Verifikasi compatibility sampling type
            if sop.sampling_type not in ['both', sampling_type]:
                return {
                    'status': 'error',
                    'message': f'SOP {sop.name} tidak dapat di-sampling oleh {sampling_type}, hanya oleh {sop.sampling_type}'
                }

            # Base values
            values = {
                'sale_order_id': sale_order_id,
                'sop_id': sop_id,
                'controller_id': request.env.user.employee_id.id,
                'notes': notes,
                'state': 'draft',
                'sampling_type': sampling_type
            }

            # Role-specific employee assignment (migration-aware)
            sale_order = request.env['sale.order'].sudo().browse(sale_order_id)
            
            if sop.role == 'sa':
                if not sale_order.service_advisor_id:
                    return {'status': 'error', 'message': 'Tidak ada Service Advisor yang ditugaskan'}
                values['sa_id'] = [(6, 0, sale_order.service_advisor_id.ids)]
            elif sop.role == 'mechanic':
                if not sale_order.car_mechanic_id_new:
                    return {'status': 'error', 'message': 'Tidak ada Mekanik yang ditugaskan'}
                values['mechanic_id'] = [(6, 0, sale_order.car_mechanic_id_new.ids)]
            elif sop.role == 'valet':
                if not employee_ids:
                    return {'status': 'error', 'message': 'Staff Valet harus dipilih'}
                values['valet_id'] = [(6, 0, employee_ids)]
            elif sop.role == 'part_support':
                if not employee_ids:
                    return {'status': 'error', 'message': 'Staff Part Support harus dipilih'}
                values['part_support_id'] = [(6, 0, employee_ids)]
            elif sop.role == 'cs':
                if not employee_ids:
                    return {'status': 'error', 'message': 'Staff Customer Service harus dipilih'}
                values['cs_id'] = [(6, 0, employee_ids)]
            elif sop.role == 'lead_mechanic':
                if not employee_ids:
                    return {'status': 'error', 'message': 'Lead Mechanic harus dipilih'}
                values['lead_mechanic_id'] = [(6, 0, employee_ids)]
            elif sop.role == 'lead_cs':
                if not employee_ids:
                    return {'status': 'error', 'message': 'Lead Customer Service harus dipilih'}
                values['lead_cs_id'] = [(6, 0, employee_ids)]
            elif sop.role == 'head_workshop':
                if not employee_ids:
                    return {'status': 'error', 'message': 'Kepala Bengkel harus dipilih'}
                values['head_workshop_id'] = [(6, 0, employee_ids)]

            # Create sampling
            sampling = request.env['pitcar.sop.sampling'].sudo().create(values)
            
            # Log sampling creation with migration context
            sampling.message_post(
                body=f"Sampling created for SOP in {current_dept} department (Migration: {'Yes' if sop.is_migrated else 'No'})",
                subject="Sampling Created"
            )

            return {
                'status': 'success',
                'data': {
                    'id': sampling.id,
                    'name': sampling.name,
                    'sale_order_id': sampling.sale_order_id.id,
                    'sop_id': sampling.sop_id.id,
                    'sampling_type': sampling.sampling_type,
                    'employee_info': self._format_employee_info(sampling),
                    'state': sampling.state,
                    'sop_migration_status': {
                        'is_migrated': sop.is_migrated,
                        'current_department': current_dept
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error dalam create_sampling: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/sampling/bulk-create', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def create_bulk_sampling(self, **kw):
        """Membuat beberapa SOP sampling untuk satu sale order"""
        try:
            # Extract parameters
            sale_order_id = kw.get('sale_order_id')
            sampling_data = kw.get('samplings', [])  # List of SOP samplings to create
            sampling_type = kw.get('sampling_type', 'kaizen')  # Default sampling type

            if not sale_order_id:
                return {'status': 'error', 'message': 'ID Sale Order wajib diisi'}
            if not sampling_data:
                return {'status': 'error', 'message': 'Tidak ada data sampling yang diberikan'}

            sale_order = request.env['sale.order'].sudo().browse(sale_order_id)
            if not sale_order.exists():
                return {'status': 'error', 'message': 'Sale Order tidak ditemukan'}

            # Dapatkan controller (penilai)
            controller = request.env.user.employee_id
            if not controller:
                return {'status': 'error', 'message': 'User saat ini tidak memiliki data karyawan'}

            created_samplings = []
            for data in sampling_data:
                sop_id = data.get('sop_id')
                notes = data.get('notes')
                data_sampling_type = data.get('sampling_type', sampling_type)  # Bisa individual per SOP

                if not sop_id:
                    continue

                sop = request.env['pitcar.sop'].sudo().browse(sop_id)
                if not sop.exists():
                    continue
                    
                # Verifikasi compatibility sampling type
                if sop.sampling_type not in ['both', data_sampling_type]:
                    _logger.warning(f"Skipping SOP {sop.name}: incompatible sampling type")
                    continue

                # Persiapkan nilai
                values = {
                    'sale_order_id': sale_order_id,
                    'sop_id': sop_id,
                    'controller_id': controller.id,
                    'notes': notes,
                    'state': 'draft',
                    'sampling_type': data_sampling_type
                }

                # Tangani penugasan karyawan berdasarkan role
                if sop.role == 'sa':
                    if sale_order.service_advisor_id:
                        values['sa_id'] = [(6, 0, sale_order.service_advisor_id.ids)]
                        _logger.info(f"Bulk create - assigning SA: {sale_order.service_advisor_id.ids}")
                elif sop.role == 'mechanic':
                    if sale_order.car_mechanic_id_new:
                        values['mechanic_id'] = [(6, 0, sale_order.car_mechanic_id_new.ids)]
                # Catatan: untuk role lain perlu employee_ids dari front-end yang tidak ada dalam bulk create

                # Buat sampling
                sampling = request.env['pitcar.sop.sampling'].sudo().create(values)
                # Verifikasi data
                if sop.role == 'sa':
                    _logger.info(f"Bulk create - Verified SA assigned: {sampling.sa_id.ids}")
                    
                created_samplings.append({
                    'id': sampling.id,
                    'name': sampling.name,
                    'sop_id': sampling.sop_id.id,
                    'sampling_type': sampling.sampling_type,
                    'employee_info': self._format_employee_info(sampling)
                })

            return {
                'status': 'success',
                'data': {
                    'sale_order_id': sale_order_id,
                    'samplings': created_samplings
                }
            }

        except Exception as e:
            _logger.error(f"Error dalam create_bulk_sampling: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/sampling/list', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_sampling_list(self, **kw):
        try:
            # Parameters
            page = max(1, int(kw.get('page', 1)))
            limit = max(1, min(100, int(kw.get('limit', 25))))
            search = (kw.get('search') or '').strip()
            month = kw.get('month', '').strip()
            role = kw.get('role')
            state = kw.get('state')
            result = kw.get('result')
            sampling_type = kw.get('sampling_type')  # Filter baru untuk tipe sampling

            domain = []

            # Month filter
            if month:
                domain.append(('month', '=', month))

            # Role filter
            if role:
                domain.append(('sop_id.role', '=', role))

            # State filter
            if state and state != 'all':
                domain.append(('state', '=', state))

            # Result filter
            if result and result != 'all':
                domain.append(('result', '=', result))
                
            # Sampling type filter
            if sampling_type and sampling_type != 'all':
                domain.append(('sampling_type', '=', sampling_type))

            # Search filter - tambahkan pencarian untuk role baru
            if search:
                domain.extend(['|', '|', '|', '|', '|', '|', '|', '|', '|', '|',
                    ('name', 'ilike', search),
                    ('sale_order_id.name', 'ilike', search),
                    ('sa_id.name', 'ilike', search),
                    ('mechanic_id.name', 'ilike', search),
                    ('valet_id.name', 'ilike', search),
                    ('part_support_id.name', 'ilike', search),
                    ('cs_id.name', 'ilike', search),
                    ('lead_mechanic_id.name', 'ilike', search),
                    ('lead_cs_id.name', 'ilike', search),
                    ('head_workshop_id.name', 'ilike', search),
                    ('sop_id.name', 'ilike', search),
                    ('sop_id.code', 'ilike', search)
                ])

            # Get data dengan sudo untuk akses konsisten
            Sampling = request.env['pitcar.sop.sampling'].sudo()
            total_count = Sampling.search_count(domain)
            offset = (page - 1) * limit
            samplings = Sampling.search(domain, limit=limit, offset=offset, order='create_date desc')

            # Format data
            rows = []
            for sampling in samplings:
                controller_data = None
                if sampling.controller_id:
                    controller_data = {
                        'id': sampling.controller_id.id,
                        'name': sampling.controller_id.name
                    }

                row = {
                    'id': sampling.id,
                    'name': sampling.name,
                    'date': sampling.date.strftime('%Y-%m-%d') if sampling.date else None,
                    'timestamps': {
                        'created': sampling.create_date.strftime('%Y-%m-%d %H:%M:%S') if sampling.create_date else None,
                        'updated': sampling.write_date.strftime('%Y-%m-%d %H:%M:%S') if sampling.write_date else None,
                        'validated': sampling.validation_date.strftime('%Y-%m-%d %H:%M:%S') if sampling.validation_date else None
                    },
                    'sale_order': {
                        'id': sampling.sale_order_id.id,
                        'name': sampling.sale_order_id.name,
                        'car_info': {
                            'plate': sampling.sale_order_id.partner_car_id.number_plate if sampling.sale_order_id.partner_car_id else None,
                            'brand': sampling.sale_order_id.partner_car_brand.name if sampling.sale_order_id.partner_car_brand else None,
                            'type': sampling.sale_order_id.partner_car_brand_type.name if sampling.sale_order_id.partner_car_brand_type else None
                        }
                    } if sampling.sale_order_id else None,
                    'sop': {
                        'id': sampling.sop_id.id,
                        'name': sampling.sop_id.name,
                        'code': sampling.sop_id.code,
                        'role': sampling.sop_id.role,
                        'role_label': dict(sampling.sop_id._fields['role'].selection).get(sampling.sop_id.role, ''),
                        'department': sampling.sop_id.department,
                        'department_label': dict(sampling.sop_id._fields['department'].selection).get(sampling.sop_id.department, ''),
                        'sampling_type': sampling.sop_id.sampling_type,
                        'sampling_type_label': dict(sampling.sop_id._fields['sampling_type'].selection).get(sampling.sop_id.sampling_type, '')
                    } if sampling.sop_id else None,
                    'sampling_type': sampling.sampling_type,
                    'sampling_type_label': dict(sampling._fields['sampling_type'].selection).get(sampling.sampling_type, ''),
                    'employee_info': self._format_employee_info(sampling),
                    'controller': controller_data,
                    'state': sampling.state,
                    'state_label': dict(sampling._fields['state'].selection).get(sampling.state, ''),
                    'result': sampling.result,
                    'result_label': dict(sampling._fields['result'].selection).get(sampling.result, '') if sampling.result else '',
                    'notes': sampling.notes
                }
                rows.append(row)

            return {
                'status': 'success',
                'data': {
                    'rows': rows,
                    'pagination': {
                        'total_items': total_count,
                        'total_pages': math.ceil(total_count / limit) if total_count > 0 else 1,
                        'current_page': page,
                        'items_per_page': limit
                    },
                    'filters': {
                        'roles': [
                            {'value': 'sa', 'label': 'Service Advisor'},
                            {'value': 'mechanic', 'label': 'Mechanic'},
                            {'value': 'lead_mechanic', 'label': 'Lead Mechanic'},
                            {'value': 'valet', 'label': 'Valet Parking'},
                            {'value': 'part_support', 'label': 'Part Support'},
                            {'value': 'cs', 'label': 'Customer Service'},
                            {'value': 'lead_cs', 'label': 'Lead Customer Service'},
                            {'value': 'head_workshop', 'label': 'Kepala Bengkel'}
                        ],
                        'states': [
                            {'value': 'draft', 'label': 'Draft'},
                            {'value': 'in_progress', 'label': 'In Progress'},
                            {'value': 'done', 'label': 'Done'}
                        ],
                        'results': [
                            {'value': 'pass', 'label': 'Lulus'},
                            {'value': 'fail', 'label': 'Tidak Lulus'}
                        ],
                        'sampling_types': [
                            {'value': 'kaizen', 'label': 'Tim Kaizen'},
                            {'value': 'lead', 'label': 'Leader'}
                        ]
                    }
                }
            }

        except Exception as e:
            _logger.error(f"Error dalam get_sampling_list: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/sampling/validate', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def validate_sampling(self, **kw):
        try:
            sampling_id = kw.get('sampling_id')
            result = kw.get('result')
            notes = kw.get('notes')
            
            if not sampling_id or not result:
                return {'status': 'error', 'message': 'ID Sampling dan hasil penilaian wajib diisi'}

            # Use sudo() untuk menghindari masalah hak akses
            sampling = request.env['pitcar.sop.sampling'].sudo().browse(sampling_id)
            if not sampling.exists():
                return {'status': 'error', 'message': 'Sampling tidak ditemukan'}

            # Log untuk debugging Service Advisor issue
            if sampling.sop_id.role == 'sa':
                _logger.info(f"Validating SA sampling: {sampling.id}, Current SA IDs: {sampling.sa_id.ids}")

            values = {
                'state': 'done',
                'result': result,
                'notes': notes,
                'validation_date': fields.Datetime.now()
            }

            # Pastikan nilai Service Advisor masih terbawa
            if sampling.sop_id.role == 'sa' and not sampling.sa_id and sampling.sale_order_id.service_advisor_id:
                _logger.info(f"Fixing missing SA data during validation: {sampling.sale_order_id.service_advisor_id.ids}")
                values['sa_id'] = [(6, 0, sampling.sale_order_id.service_advisor_id.ids)]

            sampling.write(values)
            
            # Verifikasi setelah update
            if sampling.sop_id.role == 'sa':
                _logger.info(f"After validation, SA IDs: {sampling.sa_id.ids}")
            
            return {
                'status': 'success',
                'data': {
                    'id': sampling.id,
                    'name': sampling.name,
                    'result': sampling.result,
                    'state': sampling.state,
                    'notes': sampling.notes,
                    'sampling_type': sampling.sampling_type,
                    'employee_info': self._format_employee_info(sampling)
                }
            }

        except Exception as e:
            _logger.error(f"Error dalam validate_sampling: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/sampling/summary', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_sampling_summary(self, **kw):
        """Dapatkan statistik ringkasan sampling komprehensif dan statistik umum"""
        try:
            params = self._get_request_data()
            month = kw.get('month') or params.get('month')
            sampling_type = kw.get('sampling_type') or params.get('sampling_type')
            include_statistics = kw.get('include_statistics') or params.get('include_statistics', False)
            
            if not month:
                return {'status': 'error', 'message': 'Parameter bulan wajib diisi'}

            Sampling = request.env['pitcar.sop.sampling'].sudo()
            SOP = request.env['pitcar.sop'].sudo()
            
            domain_base = [('month', '=', month)]
            domain_done = domain_base + [('state', '=', 'done')]
            
            # Filter berdasarkan tipe sampling jika ada
            if sampling_type:
                domain_base.append(('sampling_type', '=', sampling_type))
                domain_done.append(('sampling_type', '=', sampling_type))
            
            samplings = Sampling.search(domain_done)
            
            # Inisialisasi struktur ringkasan dengan semua peran
            summary = {
                'total': {
                    'total': 0,
                    'pass': 0,
                    'fail': 0,
                    'pass_rate': 0,
                    'fail_rate': 0
                },
                'month': month,
                'sampling_type': sampling_type,
                'roles': {
                    'sa': {
                        'total': 0,
                        'pass': 0,
                        'fail': 0,
                        'pass_rate': 0,
                        'fail_rate': 0,
                        'label': 'Service Advisor',
                        'details': []
                    },
                    'mechanic': {
                        'total': 0,
                        'pass': 0,
                        'fail': 0,
                        'pass_rate': 0,
                        'fail_rate': 0,
                        'label': 'Mechanic',
                        'details': []
                    },
                    'lead_mechanic': {
                        'total': 0,
                        'pass': 0,
                        'fail': 0,
                        'pass_rate': 0,
                        'fail_rate': 0,
                        'label': 'Lead Mechanic',
                        'details': []
                    },
                    'valet': {
                        'total': 0,
                        'pass': 0,
                        'fail': 0,
                        'pass_rate': 0,
                        'fail_rate': 0,
                        'label': 'Valet Parking',
                        'details': []
                    },
                    'part_support': {
                        'total': 0,
                        'pass': 0,
                        'fail': 0,
                        'pass_rate': 0,
                        'fail_rate': 0,
                        'label': 'Part Support',
                        'details': []
                    },
                    'cs': {
                        'total': 0,
                        'pass': 0,
                        'fail': 0,
                        'pass_rate': 0,
                        'fail_rate': 0,
                        'label': 'Customer Service',
                        'details': []
                    },
                    'lead_cs': {
                        'total': 0,
                        'pass': 0,
                        'fail': 0,
                        'pass_rate': 0,
                        'fail_rate': 0,
                        'label': 'Lead Customer Service',
                        'details': []
                    },
                    'head_workshop': {
                        'total': 0,
                        'pass': 0,
                        'fail': 0,
                        'pass_rate': 0,
                        'fail_rate': 0,
                        'label': 'Kepala Bengkel',
                        'details': []
                    }
                }
            }

            # Helper untuk memperbarui statistik
            def update_stats(stats_dict, result):
                stats_dict['total'] += 1
                stats_dict['pass'] += 1 if result == 'pass' else 0
                stats_dict['fail'] += 1 if result == 'fail' else 0

            # Helper untuk memperbarui statistik karyawan
            def update_employee_stats(employee_stats, employee, result):
                if employee.id not in employee_stats:
                    employee_stats[employee.id] = {
                        'id': employee.id,
                        'name': employee.name,
                        'total': 0,
                        'pass': 0,
                        'fail': 0,
                        'pass_rate': 0,
                        'fail_rate': 0
                    }
                update_stats(employee_stats[employee.id], result)

            # Inisialisasi kamus statistik karyawan
            employee_stats = {
                'sa': {},
                'mechanic': {},
                'lead_mechanic': {},
                'valet': {},
                'part_support': {},
                'cs': {},
                'lead_cs': {},
                'head_workshop': {}
            }

            # Proses semua sampling
            for sampling in samplings:
                role = sampling.sop_id.role
                result = sampling.result
                
                if role not in summary['roles']:
                    continue

                # Perbarui statistik total
                update_stats(summary['total'], result)
                
                # Perbarui statistik peran
                update_stats(summary['roles'][role], result)
                
                # Perbarui statistik karyawan berdasarkan peran
                if role == 'sa' and sampling.sa_id:
                    for employee in sampling.sa_id:
                        update_employee_stats(employee_stats['sa'], employee, result)
                elif role == 'mechanic' and sampling.mechanic_id:
                    for employee in sampling.mechanic_id:
                        update_employee_stats(employee_stats['mechanic'], employee, result)
                elif role == 'lead_mechanic' and sampling.lead_mechanic_id:
                    for employee in sampling.lead_mechanic_id:
                        update_employee_stats(employee_stats['lead_mechanic'], employee, result)
                elif role == 'valet' and sampling.valet_id:
                    for employee in sampling.valet_id:
                        update_employee_stats(employee_stats['valet'], employee, result)
                elif role == 'part_support' and sampling.part_support_id:
                    for employee in sampling.part_support_id:
                        update_employee_stats(employee_stats['part_support'], employee, result)
                elif role == 'cs' and sampling.cs_id:
                    for employee in sampling.cs_id:
                        update_employee_stats(employee_stats['cs'], employee, result)
                elif role == 'lead_cs' and sampling.lead_cs_id:
                    for employee in sampling.lead_cs_id:
                        update_employee_stats(employee_stats['lead_cs'], employee, result)
                elif role == 'head_workshop' and sampling.head_workshop_id:
                    for employee in sampling.head_workshop_id:
                        update_employee_stats(employee_stats['head_workshop'], employee, result)

            # Hitung tingkat kelulusan dan urut detail karyawan
            def calculate_rates(stats):
                if stats['total'] > 0:
                    stats['pass_rate'] = round((stats['pass'] / stats['total']) * 100, 2)
                    stats['fail_rate'] = round((stats['fail'] / stats['total']) * 100, 2)

            # Hitung tingkat untuk total keseluruhan
            calculate_rates(summary['total'])

            # Proses statistik masing-masing peran
            for role in summary['roles']:
                # Hitung tingkat untuk total peran
                calculate_rates(summary['roles'][role])
                
                # Proses detail karyawan untuk peran ini
                details = list(employee_stats[role].values())
                for detail in details:
                    calculate_rates(detail)
                
                # Urutkan berdasarkan tingkat kelulusan (menurun)
                details.sort(key=lambda x: x['pass_rate'], reverse=True)
                
                # Tambahkan peringkat
                for i, detail in enumerate(details, 1):
                    detail['rank'] = i
                
                summary['roles'][role]['details'] = details

            # Tambahkan statistik umum jika diminta
            if include_statistics:
                # Hitung total SOP aktif
                total_sops = SOP.search_count([('active', '=', True)])
                
                # Hitung total samplings per tipe
                total_samplings = Sampling.search_count(domain_base)
                kaizen_samplings = Sampling.search_count(domain_base + [('sampling_type', '=', 'kaizen')])
                lead_samplings = Sampling.search_count(domain_base + [('sampling_type', '=', 'lead')])
                
                # Hitung status
                done_samplings = Sampling.search_count(domain_base + [('state', '=', 'done')])
                passed_samplings = Sampling.search_count(domain_base + [('result', '=', 'pass')])
                failed_samplings = Sampling.search_count(domain_base + [('result', '=', 'fail')])
                
                # Hitung samplings per departemen
                service_samplings = Sampling.search_count(domain_base + [('sop_id.department', '=', 'service')])
                cs_samplings = Sampling.search_count(domain_base + [('sop_id.department', '=', 'cs')])
                sparepart_samplings = Sampling.search_count(domain_base + [('sop_id.department', '=', 'sparepart')])
                
                # Hitung persentase
                completion_rate = round((done_samplings / total_samplings * 100), 2) if total_samplings > 0 else 0
                pass_rate = round((passed_samplings / done_samplings * 100), 2) if done_samplings > 0 else 0
                
                # Tambahkan ke respons
                summary['statistics'] = {
                    'total_sops': total_sops,
                    'sampling_counts': {
                        'total': total_samplings,
                        'kaizen': kaizen_samplings,
                        'lead': lead_samplings,
                        'done': done_samplings,
                        'pass': passed_samplings,
                        'fail': failed_samplings
                    },
                    'department_counts': {
                        'service': service_samplings,
                        'cs': cs_samplings,
                        'sparepart': sparepart_samplings
                    },
                    'rates': {
                        'completion': completion_rate,
                        'pass': pass_rate
                    }
                }

            return {
                'status': 'success',
                'data': summary
            }

        except Exception as e:
            _logger.error(f"Error dalam get_sampling_summary: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    # =====================================
    # SOP MASTER CRUD ENDPOINTS
    # =====================================

    @http.route('/web/sop/master/create', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def create_sop(self, **kw):
        """Membuat SOP baru"""
        try:
            # Validasi data wajib
            required_fields = ['name', 'code', 'department', 'role']
            missing_fields = [field for field in required_fields if not kw.get(field)]
            
            if missing_fields:
                return {
                    'status': 'error', 
                    'message': f"Field berikut wajib diisi: {', '.join(missing_fields)}"
                }
            
            # Periksa apakah kode SOP sudah ada
            existing_code = request.env['pitcar.sop'].sudo().search([('code', '=', kw.get('code'))])
            if existing_code:
                return {'status': 'error', 'message': 'Kode SOP sudah digunakan'}
            
            vals = {
                'name': kw.get('name'),
                'code': kw.get('code'),
                'description': kw.get('description', ''),
                'department': kw.get('department'),
                'role': kw.get('role'),
                'sampling_type': kw.get('sampling_type', 'both'),
                'activity_type': kw.get('activity_type', 'pembuatan'),
                'state': kw.get('state', 'draft'),
                'review_state': kw.get('review_state', 'waiting'),
                'revision_state': kw.get('revision_state', 'no_revision'),
                'document_url': kw.get('document_url', ''),
                'socialization_state': kw.get('socialization_state', 'not_started'),
                'notes': kw.get('notes', ''),
                'sequence': kw.get('sequence', 10)
            }

            # Only add date fields if they have values
            if kw.get('date_start'):
                vals['date_start'] = kw.get('date_start')
            if kw.get('date_end'):
                vals['date_end'] = kw.get('date_end')
            if kw.get('socialization_date'):
                vals['socialization_date'] = kw.get('socialization_date')
            if kw.get('socialization_target_date'):
                vals['socialization_target_date'] = kw.get('socialization_target_date')
            
            # Buat SOP baru
            new_sop = request.env['pitcar.sop'].sudo().create(vals)
            
            return {
                'status': 'success',
                'message': 'SOP berhasil dibuat',
                'data': {'id': new_sop.id}
            }
        
        except Exception as e:
            _logger.error(f"Error di create_sop: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/master/update', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def update_sop(self, **kw):
        """Memperbarui data SOP"""
        try:
            sop_id = kw.get('id')
            if not sop_id:
                return {'status': 'error', 'message': 'ID SOP diperlukan'}
            
            sop = request.env['pitcar.sop'].sudo().browse(int(sop_id))
            if not sop.exists():
                return {'status': 'error', 'message': 'SOP tidak ditemukan'}
            
            # Periksa apakah kode SOP yang baru sudah ada (jika kode diubah)
            if kw.get('code') and kw.get('code') != sop.code:
                existing_code = request.env['pitcar.sop'].sudo().search([
                    ('code', '=', kw.get('code')),
                    ('id', '!=', sop.id)
                ])
                if existing_code:
                    return {'status': 'error', 'message': 'Kode SOP sudah digunakan'}
            
            # Siapkan values untuk update
            vals = {}
            
            # Update fields yang diubah
            update_fields = [
                'name', 'code', 'description', 'department', 'role', 'sampling_type',
                'activity_type', 'date_start', 'date_end', 'state', 'review_state',
                'revision_state', 'document_url', 'socialization_state', 'socialization_date', 
                'socialization_target_date', 'notes', 'sequence', 'active'
            ]
            
            for field in update_fields:
                if field in kw:
                    vals[field] = kw[field]
            
            # Update SOP
            sop.write(vals)
            
            return {
                'status': 'success',
                'message': 'SOP berhasil diperbarui'
            }
        
        except Exception as e:
            _logger.error(f"Error di update_sop: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/master/delete/<int:sop_id>', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def delete_sop(self, sop_id, **kw):
        """Hapus/Arsipkan SOP"""
        try:
            sop = request.env['pitcar.sop'].sudo().browse(int(sop_id))
            if not sop.exists():
                return {'status': 'error', 'message': 'SOP tidak ditemukan'}

            # Periksa apakah SOP digunakan dalam sampling
            if request.env['pitcar.sop.sampling'].sudo().search_count([('sop_id', '=', sop_id)]) > 0:
                # Hanya arsipkan jika SOP digunakan
                sop.write({'active': False})
                return {
                    'status': 'success',
                    'message': 'SOP telah diarsipkan karena digunakan dalam catatan sampling'
                }
            else:
                # Hapus jika tidak digunakan
                sop.unlink()
                return {
                    'status': 'success',
                    'message': 'SOP berhasil dihapus'
                }

        except Exception as e:
            _logger.error(f"Error dalam delete_sop: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/employees', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def get_employees_by_role(self, **kw):
        """Dapatkan daftar karyawan berdasarkan peran untuk sampling"""
        try:
            role = kw.get('role')
            if not role:
                return {'status': 'error', 'message': 'Parameter peran wajib diisi'}
                
            domain = self._get_employee_domain(role)
            
            # Penanganan khusus untuk model khusus
            if role == 'sa':
                # Service Advisor menggunakan model khusus
                employees = request.env['pitcar.service.advisor'].sudo().search([])
                rows = [{
                    'id': sa.id,
                    'name': sa.name
                } for sa in employees]
            elif role == 'mechanic':
                # Mechanic menggunakan model khusus
                employees = request.env['pitcar.mechanic.new'].sudo().search([])
                rows = [{
                    'id': mech.id,
                    'name': mech.name
                } for mech in employees]
            else:
                # Peran lain menggunakan model hr.employee dengan domain
                employees = request.env['hr.employee'].sudo().search(domain)
                rows = [{
                    'id': emp.id,
                    'name': emp.name,
                    'job': emp.job_id.name if emp.job_id else None
                } for emp in employees]
                
            return {
                'status': 'success',
                'data': {
                    'role': role,
                    'employees': rows
                }
            }
        
        except Exception as e:
            _logger.error(f"Error dalam get_employees_by_role: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/sop/config/migration', type='json', auth='user', methods=['POST'], csrf=False, cors='*')
    def configure_migration(self, **kw):
        """Configure migration settings"""
        try:
            action = kw.get('action')  # enable, disable, status
            
            if action == 'enable':
                # Enable migration mode
                request.env['ir.config_parameter'].sudo().set_param('sop.migration.active', 'True')
                return {
                    'status': 'success',
                    'message': 'Migration mode enabled',
                    'data': {'migration_active': True}
                }
            
            elif action == 'disable':
                # Disable migration mode
                request.env['ir.config_parameter'].sudo().set_param('sop.migration.active', 'False')
                return {
                    'status': 'success',
                    'message': 'Migration mode disabled',
                    'data': {'migration_active': False}
                }
            
            elif action == 'status':
                # Get migration status
                migration_active = request.env['ir.config_parameter'].sudo().get_param('sop.migration.active', default='False')
                return {
                    'status': 'success',
                    'data': {
                        'migration_active': migration_active.lower() == 'true',
                        'migration_summary': self._get_migration_summary()
                    }
                }
            
            else:
                return {'status': 'error', 'message': 'Invalid action'}
        
        except Exception as e:
            _logger.error(f"Error dalam configure_migration: {str(e)}")
            return {'status': 'error', 'message': str(e)}