# controllers/attendance_api.py
from odoo import http
from odoo.http import request
from datetime import datetime, time, timedelta
from dateutil.relativedelta import relativedelta
import pytz
import logging
import json
import math
import io
import csv

_logger = logging.getLogger(__name__)

class CSSampling(http.Controller):
    @http.route('/web/v2/cs/chat-sampling', type='json', auth='user', methods=['POST'], csrf=False)
    def cs_chat_sampling(self, **kw):
        """Handle chat sampling operations"""
        try:
            operation = kw.get('operation', 'create')
            
            if operation == 'create':
                return self._create_chat_sampling(kw)
            elif operation == 'get':
                return self._get_chat_sampling(kw)
            elif operation == 'update':
              return self._update_chat_sampling(kw)
            elif operation == 'delete':
                return self._delete_chat_sampling(kw)
            else:
                return {'status': 'error', 'message': 'Invalid operation'}
                
        except Exception as e:
            _logger.error(f"Error in cs_chat_sampling: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _create_chat_sampling(self, data):
        """Create new chat sampling record"""
        required_fields = ['cs_id', 'date', 'total_chats', 'responded_ontime']
        if not all(data.get(field) for field in required_fields):
            return {'status': 'error', 'message': 'Missing required fields'}

        values = {
            'cs_id': int(data['cs_id']),
            'date': data['date'],
            'total_chats': int(data['total_chats']),
            'responded_ontime': int(data['responded_ontime']),
            'notes': data.get('notes', ''),
            'controller_id': request.env.user.employee_id.id 
        }

        sampling = request.env['cs.chat.sampling'].sudo().create(values)
        
        if data.get('complete', False):
            sampling.action_done()

        return {
            'status': 'success',
            'data': {
                'id': sampling.id,
                'name': sampling.name,
                'response_rate': sampling.response_rate
            }
        }

    def _get_chat_sampling(self, data):
        """Get chat sampling records"""
        domain = []
        
        if data.get('cs_id'):
            domain.append(('cs_id', '=', int(data['cs_id'])))
        if data.get('date_from'):
            domain.append(('date', '>=', data['date_from']))
        if data.get('date_to'):
            domain.append(('date', '<=', data['date_to']))

        samplings = request.env['cs.chat.sampling'].sudo().search(domain)
        
        return {
            'status': 'success',
            'data': [{
                'id': record.id,
                'cs_id': record.cs_id.id,  # Ambil ID numerik
                'cs_name': record.cs_id.name,  # Ambil nama CS
                'name': record.name,
                'date': record.date,
                'total_chats': record.total_chats,
                'responded_ontime': record.responded_ontime,
                'response_rate': record.response_rate,
                'notes': record.notes,
                'state': record.state,
                'controller_id': record.controller_id.id,  # Tambahkan ini
                'controller_name': record.controller_id.name  # Tambahkan ini
            } for record in samplings]
        }
    
    # create update function
    def _update_chat_sampling(self, data):
        """Update existing chat sampling record"""
        if not data.get('id'):
          return {'status': 'error', 'message': 'Missing chat sampling ID'}

        sampling = request.env['cs.chat.sampling'].sudo().browse(int(data['id']))
        if not sampling.exists():
          return {'status': 'error', 'message': 'Chat sampling not found'}

        update_values = {}
        optional_fields = {
          'total_chats': int,
          'responded_ontime': int,
          'notes': str
        }

        for field, field_type in optional_fields.items():
          if field in data:
            update_values[field] = field_type(data[field])

        if data.get('controller_id'):  # Optional override controller
            update_values['controller_id'] = int(data['controller_id'])
        elif not sampling.controller_id:  # Set if not yet set
            update_values['controller_id'] = request.env.user.employee_id.id

        if update_values:
          sampling.write(update_values)

        if data.get('complete', False):
          sampling.action_done()

        return {
          'status': 'success',
          'data': {
            'id': sampling.id,
            'name': sampling.name,
            'response_rate': sampling.response_rate
          }
        }
    
    # create delete function
    def _delete_chat_sampling(self, data):
        """Delete existing chat sampling record"""
        if not data.get('id'):
            return {'status': 'error', 'message': 'Missing chat sampling ID'}

        sampling = request.env['cs.chat.sampling'].sudo().browse(int(data['id']))
        if not sampling.exists():
            return {'status': 'error', 'message': 'Chat sampling not found'}

        sampling.unlink()
        return {'status': 'success'}
    
    @http.route('/web/v2/cs/leads-verification', type='json', auth='user', methods=['POST'], csrf=False)
    def cs_leads_verification(self, **kw):
        """Handle leads verification operations"""
        try:
            operation = kw.get('operation', 'create')
            
            if operation == 'create':
                # Hanya check field yang wajib
                required_fields = ['cs_id', 'date']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Missing required fields'}

                values = {
                    'cs_id': int(kw['cs_id']),
                    'date': kw['date'],
                    'controller_id': request.env.user.employee_id.id 
                }

                # Optional fields
                optional_fields = {
                    'system_leads_count': int,
                    'actual_leads_count': int,
                    'notes': str
                }

                for field, field_type in optional_fields.items():
                    if field in kw:
                        values[field] = field_type(kw[field])

                # Create verification record
                verification = request.env['cs.leads.verification'].sudo().create(values)

                # Create verification lines if provided
                if kw.get('verification_lines'):
                    for line in kw['verification_lines']:
                        line['verification_id'] = verification.id
                        request.env['cs.leads.verification.line'].sudo().create(line)

                if kw.get('complete', False):
                    verification.action_done()

                return {
                    'status': 'success',
                    'data': {
                        'id': verification.id,
                        'name': verification.name,
                        'accuracy_rate': verification.accuracy_rate,
                        'state': verification.state,
                        'controller_id': verification.controller_id.id,  # Tambahkan ini
                        'controller_name': verification.controller_id.name  # Tambahkan ini
                    }
                }

            elif operation == 'get':
                domain = []
                if kw.get('cs_id'):
                    domain.append(('cs_id', '=', int(kw['cs_id'])))
                if kw.get('date_from'):
                    domain.append(('date', '>=', kw['date_from']))
                if kw.get('date_to'):
                    domain.append(('date', '<=', kw['date_to']))

                verifications = request.env['cs.leads.verification'].sudo().search(domain)
                return {
                    'status': 'success',
                    'data': [{
                        'id': record.id,
                        'name': record.name,
                        'date': record.date,
                        'cs_id': record.cs_id.id,
                        'cs_name': record.cs_id.name,
                        'system_leads_count': record.system_leads_count,
                        'actual_leads_count': record.actual_leads_count,
                        'missing_leads_count': record.missing_leads_count,
                        'accuracy_rate': record.accuracy_rate,
                        'state': record.state,
                        'controller_id': record.controller_id.id,  # Tambahkan ini
                        'controller_name': record.controller_id.name,  # Tambahkan ini
                        'verification_lines': [{
                            'lead_source': line.lead_source,
                            'customer_name': line.customer_name,
                            'order_reference': line.order_reference,
                            'problem_type': line.problem_type,
                            'notes': line.notes
                        } for line in record.verification_line_ids] if record.verification_line_ids else []
                    } for record in verifications]
                }
                
            elif operation == 'update':
                if not kw.get('id'):
                    return {'status': 'error', 'message': 'Missing verification ID'}
                    
                verification = request.env['cs.leads.verification'].sudo().browse(int(kw['id']))
                if not verification.exists():
                    return {'status': 'error', 'message': 'Verification not found'}
                    
                update_values = {}
                optional_fields = {
                    'system_leads_count': int,
                    'actual_leads_count': int,
                    'notes': str
                }

                for field, field_type in optional_fields.items():
                    if field in kw:
                        update_values[field] = field_type(kw[field])
                        
                if update_values:
                    verification.write(update_values)
                    
                if kw.get('verification_lines'):
                    # Hapus lines lama jika ada
                    verification.verification_line_ids.unlink()
                    # Buat lines baru
                    for line in kw['verification_lines']:
                        line['verification_id'] = verification.id
                        request.env['cs.leads.verification.line'].sudo().create(line)
                        
                if kw.get('complete', False):
                    verification.action_done()
                    
                return {
                    'status': 'success',
                    'data': {
                        'id': verification.id,
                        'name': verification.name,
                        'accuracy_rate': verification.accuracy_rate,
                        'state': verification.state
                    }
                }
            
            elif operation == 'delete':
                if not kw.get('id'):
                    return {'status': 'error', 'message': 'Missing verification ID'}
                    
                verification = request.env['cs.leads.verification'].sudo().browse(int(kw['id']))
                if not verification.exists():
                    return {'status': 'error', 'message': 'Verification not found'}
                
                try:
                    verification.verification_line_ids.unlink()
                    verification.unlink()
                    return {
                        'status': 'success',
                        'message': 'Leads verification berhasil dihapus'
                    }
                except Exception as e:
                    return {
                        'status': 'error',
                        'message': 'Gagal menghapus data: ' + str(e)
                    }

        except Exception as e:
            _logger.error(f"Error in cs_leads_verification: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v2/cs/contact-monitoring', type='json', auth='user', methods=['POST'], csrf=False)
    def cs_contact_monitoring(self, **kw):
        """Handle contact monitoring operations"""
        try:
            operation = kw.get('operation', 'create')
            
            if operation == 'create':
                required_fields = ['cs_id', 'date', 'total_customers']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Missing required fields'}

                values = {
                    'cs_id': int(kw['cs_id']),
                    'date': kw['date'],
                    'total_customers': int(kw['total_customers']),
                    'contacts_saved': int(kw.get('contacts_saved', 0)),
                    'story_posted': int(kw.get('story_posted', 0)),
                    'broadcast_sent': int(kw.get('broadcast_sent', 0)),
                    'notes': kw.get('notes', ''),
                    'controller_id': request.env.user.employee_id.id
                }

                monitoring = request.env['cs.contact.monitoring'].sudo().create(values)

                if kw.get('monitoring_lines'):
                    for line in kw['monitoring_lines']:
                        line['monitoring_id'] = monitoring.id
                        request.env['cs.contact.monitoring.line'].sudo().create(line)

                if kw.get('complete', False):
                    monitoring.action_done()

                return {
                    'status': 'success',
                    'data': {
                        'id': monitoring.id,
                        'name': monitoring.name,
                        'compliance_rate': monitoring.compliance_rate,
                        'state': monitoring.state,
                        'controller_id': monitoring.controller_id.id,  # Tambahkan ini
                        'controller_name': monitoring.controller_id.name  # Tambahkan ini
                    }
                }

            elif operation == 'get':
                domain = []
                if kw.get('cs_id'):
                    domain.append(('cs_id', '=', int(kw['cs_id'])))
                if kw.get('date_from'):
                    domain.append(('date', '>=', kw['date_from']))
                if kw.get('date_to'):
                    domain.append(('date', '<=', kw['date_to']))

                monitorings = request.env['cs.contact.monitoring'].sudo().search(domain)
                
                return {
                    'status': 'success',
                    'data': [{
                        'id': record.id,
                        'name': record.name,
                        'date': record.date,
                        'cs_id': record.cs_id.id,
                        'cs_name': record.cs_id.name,
                        'total_customers': record.total_customers,
                        'contacts_saved': record.contacts_saved,
                        'story_posted': record.story_posted,
                        'broadcast_sent': record.broadcast_sent,
                        'compliance_rate': record.compliance_rate,
                        'state': record.state,
                        'controller_id': record.controller_id.id,  # Tambahkan ini
                        'controller_name': record.controller_id.name,  # Tambahkan ini
                        'monitoring_lines': [{
                            'customer_name': line.customer_name,
                            'contact_saved': line.contact_saved,
                            'story_posted': line.story_posted,
                            'broadcast_sent': line.broadcast_sent,
                            'notes': line.notes
                        } for line in record.monitoring_line_ids]
                    } for record in monitorings]
                }
            
            elif operation == 'update':
                if not kw.get('id'):
                    return {'status': 'error', 'message': 'Missing monitoring ID'}
                    
                monitoring = request.env['cs.contact.monitoring'].sudo().browse(int(kw['id']))
                if not monitoring.exists():
                    return {'status': 'error', 'message': 'Monitoring not found'}
                
                update_values = {}
                optional_fields = {
                    'total_customers': int,
                    'contacts_saved': int,
                    'story_posted': int,
                    'broadcast_sent': int,
                    'notes': str
                }

                for field, field_type in optional_fields.items():
                    if field in kw:
                        update_values[field] = field_type(kw[field])
                        
                if update_values:
                    monitoring.write(update_values)
                
                # Update monitoring lines
                if kw.get('monitoring_lines'):
                    # Hapus lines lama
                    monitoring.monitoring_line_ids.unlink()
                    # Buat lines baru
                    for line in kw['monitoring_lines']:
                        line['monitoring_id'] = monitoring.id
                        request.env['cs.contact.monitoring.line'].sudo().create(line)
                        
                if kw.get('complete', False):
                    monitoring.action_done()
                    
                return {
                    'status': 'success',
                    'data': {
                        'id': monitoring.id,
                        'name': monitoring.name,
                        'compliance_rate': monitoring.compliance_rate,
                        'state': monitoring.state
                    }
                }
            
            elif operation == 'delete':
                if not kw.get('id'):
                    return {'status': 'error', 'message': 'Missing monitoring ID'}
                    
                monitoring = request.env['cs.contact.monitoring'].sudo().browse(int(kw['id']))
                if not monitoring.exists():
                    return {'status': 'error', 'message': 'Contact monitoring not found'}
                
                try:
                    monitoring.monitoring_line_ids.unlink()
                    monitoring.unlink()
                    return {
                        'status': 'success',
                        'message': 'Contact monitoring berhasil dihapus'
                    }
                except Exception as e:
                    return {
                        'status': 'error',
                        'message': 'Gagal menghapus data: ' + str(e)
                    }


        except Exception as e:
            _logger.error(f"Error in cs_contact_monitoring: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    @http.route('/web/v2/cs/finance-check', type='json', auth='user', methods=['POST'], csrf=False)
    def cs_finance_check(self, **kw):
        """Handle finance check operations"""
        try:
            operation = kw.get('operation', 'create')
            
            if operation == 'create':
                required_fields = ['cs_id', 'date']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Missing required fields'}

                values = {
                    'cs_id': int(kw['cs_id']),
                    'date': kw['date'],
                    'notes': kw.get('notes', ''),
                    'cash_amount': float(kw.get('cash_amount', 0.0)),  # Tambah field cash_amount
                    'controller_id': request.env.user.employee_id.id
                }

                check = request.env['cs.finance.check'].sudo().create(values)

                # Update check lines if provided
                if kw.get('check_lines'):
                    for line in kw['check_lines']:
                        line_id = check.check_line_ids.filtered(
                            lambda l: l.item_id.id == int(line['item_id'])
                        )
                        if line_id:
                            line_id.write({
                                'is_complete': line.get('is_complete', False),
                                'notes': line.get('notes', '')
                            })

                if kw.get('complete', False):
                    check.action_done()

                return {
                    'status': 'success',
                    'data': {
                        'id': check.id,
                        'name': check.name,
                        'completeness_rate': check.completeness_rate,
                        'state': check.state,
                        'controller_id': check.controller_id.id,  # Tambahkan ini
                        'controller_name': check.controller_id.name  # Tambahkan ini
                    }
                }

            elif operation == 'get':
                domain = []
                if kw.get('cs_id'):
                    domain.append(('cs_id', '=', int(kw['cs_id'])))
                if kw.get('date_from'):
                    domain.append(('date', '>=', kw['date_from']))
                if kw.get('date_to'):
                    domain.append(('date', '<=', kw['date_to']))

                checks = request.env['cs.finance.check'].sudo().search(domain)
                
                return {
                    'status': 'success',
                    'data': [{
                        'id': record.id,
                        'name': record.name,
                        'date': record.date,
                        'cs_id': record.cs_id.id,
                        'cs_name': record.cs_id.name,
                        'cash_amount': record.cash_amount,  # Tambah field di response
                        'completeness_rate': record.completeness_rate,
                        'state': record.state,
                        'controller_id': record.controller_id.id,  # Tambahkan ini
                        'controller_name': record.controller_id.name,  # Tambahkan ini
                        'check_lines': [{
                            'item_id': line.item_id.id,
                            'item_name': line.item_id.name,
                            'is_complete': line.is_complete,
                            'notes': line.notes
                        } for line in record.check_line_ids]
                    } for record in checks]
                }
            
            elif operation == 'delete':
                if not kw.get('id'):
                    return {'status': 'error', 'message': 'Missing check ID'}
                    
                check = request.env['cs.finance.check'].sudo().browse(int(kw['id']))
                if not check.exists():
                    return {'status': 'error', 'message': 'Check not found'}
                    
                try:
                    # Hapus check lines terlebih dahulu (jika perlu, tapi sebenarnya sudah ada ondelete='cascade')
                    check.check_line_ids.unlink()
                    # Hapus check header
                    check.unlink()
                    
                    return {
                        'status': 'success',
                        'message': 'Finance check berhasil dihapus'
                    }
                except Exception as e:
                    return {
                        'status': 'error',
                        'message': 'Gagal menghapus data: ' + str(e)
                    }

        except Exception as e:
            _logger.error(f"Error in cs_finance_check: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        
    @http.route('/web/v2/cs/finance-check/items', type='json', auth='user', methods=['POST'], csrf=False)
    def cs_finance_check_items(self, **kw):
        """Handle finance check items management"""
        try:
            operation = kw.get('operation', 'get')
            
            if operation == 'create':
                # Create new check item
                required_fields = ['name']
                if not all(kw.get(field) for field in required_fields):
                    return {'status': 'error', 'message': 'Missing required fields'}

                values = {
                    'name': kw['name'],
                    'description': kw.get('description', ''),
                    'active': kw.get('active', True)
                }

                item = request.env['cs.finance.check.item'].sudo().create(values)
                return {
                    'status': 'success',
                    'data': {
                        'id': item.id,
                        'name': item.name,
                        'description': item.description,
                        'active': item.active
                    }
                }

            elif operation == 'update':
                if not kw.get('id'):
                    return {'status': 'error', 'message': 'Missing item ID'}

                item = request.env['cs.finance.check.item'].sudo().browse(int(kw['id']))
                if not item.exists():
                    return {'status': 'error', 'message': 'Item not found'}

                update_values = {}
                if 'name' in kw:
                    update_values['name'] = kw['name']
                if 'description' in kw:
                    update_values['description'] = kw['description']
                if 'active' in kw:
                    update_values['active'] = kw['active']

                item.write(update_values)
                return {
                    'status': 'success',
                    'data': {
                        'id': item.id,
                        'name': item.name,
                        'description': item.description,
                        'active': item.active
                    }
                }

            elif operation == 'get':
                # Get check items
                domain = []
                if 'active' in kw:
                    domain.append(('active', '=', kw['active']))

                items = request.env['cs.finance.check.item'].sudo().search(domain)
                return {
                    'status': 'success',
                    'data': [{
                        'id': item.id,
                        'name': item.name,
                        'description': item.description,
                        'active': item.active
                    } for item in items]
                }
            
            elif operation == 'delete':
                if not kw.get('id'):
                    return {'status': 'error', 'message': 'Missing item ID'}
                    
                item = request.env['cs.finance.check.item'].sudo().browse(int(kw['id']))
                if not item.exists():
                    return {'status': 'error', 'message': 'Finance check item not found'}
                
                try:
                    item.unlink()
                    return {
                        'status': 'success',
                        'message': 'Finance check item berhasil dihapus'
                    }
                except Exception as e:
                    return {
                        'status': 'error',
                        'message': 'Gagal menghapus data: ' + str(e)
                    }

        except Exception as e:
            _logger.error(f"Error in cs_finance_check_items: {str(e)}")
            return {'status': 'error', 'message': str(e)}