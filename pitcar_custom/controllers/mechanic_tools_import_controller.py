from odoo import http
from odoo.http import request
import logging
import base64
import csv
import io
import json
import tempfile
import os
from datetime import datetime

_logger = logging.getLogger(__name__)

class MechanicToolsImportController(http.Controller):
    
    # Tambahkan parameter mapping ke fungsi import_tools_http
    @http.route('/web/mechanic/tools/import', type='http', auth='user', methods=['POST'], csrf=False)
    def import_tools_http(self, **kw):
        """Handle file upload via HTTP POST for tools import"""
        try:
            import_file = kw.get('import_file')
            if not import_file:
                return json.dumps({
                    'status': 'error',
                    'message': 'No file uploaded'
                })
                
            # Get parameters
            delimiter = kw.get('delimiter', ',')
            import_type = kw.get('import_type', 'tools')
            
            try:
                # Get column mapping if provided
                column_mapping = {}
                mapping_str = kw.get('column_mapping', '{}')
                if mapping_str:
                    column_mapping = json.loads(mapping_str)
            except Exception as e:
                _logger.warning(f"Failed to parse column mapping: {str(e)}")
                column_mapping = {}
            
            # Process file content in binary mode (no encoding assumption)
            file_content = import_file.read()
            
            # Simpan ke temporary file
            file_ext = os.path.splitext(import_file.filename)[1].lower() if hasattr(import_file, 'filename') else '.csv'
            fd, temp_path = tempfile.mkstemp(suffix=file_ext)
            
            try:
                with os.fdopen(fd, 'wb') as temp_file:
                    temp_file.write(file_content)
                
                # Process the import - pass file extension to choose appropriate parser
                result = self._process_import(temp_path, delimiter, import_type, column_mapping)
                return json.dumps(result)
                
            finally:
                # Remove temp file
                try:
                    os.unlink(temp_path)
                except (OSError, IOError):
                    pass
            
        except Exception as e:
            _logger.error(f"Error in import_tools_http: {str(e)}", exc_info=True)
            return json.dumps({
                'status': 'error',
                'message': str(e)
            })
    
    @http.route('/web/mechanic/tools/import/json', type='json', auth='user', methods=['POST'], csrf=False)
    def import_tools_json(self, **kw):
        """
        Handle direct JSON import for tools
        
        Expected parameters:
        - tools: List of tool dictionaries for import
        - categories: List of category dictionaries for import
        - checks: List of check dictionaries for import
        
        Only one of the above parameters should be provided based on the type of import.
        """
        try:
            tools = kw.get('tools')
            categories = kw.get('categories')
            checks = kw.get('checks')
            
            if tools:
                return self._import_tools_from_json(tools)
            elif categories:
                return self._import_categories_from_json(categories)
            elif checks:
                return self._import_checks_from_json(checks)
            else:
                return {
                    'status': 'error',
                    'message': 'No import data provided'
                }
                
        except Exception as e:
            _logger.error("Error in import_tools_json: %s", str(e))
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _process_import(self, file_path, delimiter, import_type, column_mapping=None):
        """Process the import based on file type with optional column mapping"""
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # Handle Excel files (XLS, XLSX)
            if file_ext in ['.xls', '.xlsx']:
                return self._process_excel_import(file_path, import_type, column_mapping)
            
            # Handle CSV files dengan berbagai encoding
            else:
                # Coba dengan beberapa encoding
                encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
                data_rows = []
                header = []
                
                for encoding in encodings:
                    try:
                        with open(file_path, 'r', encoding=encoding) as f:
                            reader = csv.reader(f, delimiter=delimiter)
                            rows = list(reader)
                            if rows:
                                header = rows[0]
                                data_rows = rows[1:]
                                break  # Berhasil membaca file
                    except UnicodeDecodeError:
                        continue  # Coba encoding lain
                    except Exception as e:
                        _logger.error(f"Error reading CSV with {encoding}: {str(e)}")
                        continue
                
                if not header:
                    return {
                        'status': 'error',
                        'message': 'Failed to read CSV file with any encoding'
                    }
                
                # Convert headers to lowercase
                original_headers = [h.strip() for h in header]
                header_lower = [h.lower().strip() for h in header]
                
                # Apply column mapping if provided
                if column_mapping:
                    mapped_headers = []
                    for h in original_headers:
                        # Look for exact match first, then case-insensitive
                        if h in column_mapping:
                            mapped_headers.append(column_mapping[h])
                        elif h.lower() in {k.lower(): v for k, v in column_mapping.items()}:
                            mapped_key = next(k for k in column_mapping.keys() if k.lower() == h.lower())
                            mapped_headers.append(column_mapping[mapped_key])
                        else:
                            mapped_headers.append(h)
                    
                    header_lower = [h.lower().strip() for h in mapped_headers]
                    _logger.info(f"Applied column mapping. Original: {original_headers}, Mapped: {mapped_headers}")
                
                if import_type == 'tools':
                    return self._import_tools_from_csv(header_lower, data_rows)
                elif import_type == 'categories':
                    return self._import_categories_from_csv(header_lower, data_rows)
                elif import_type == 'checks':
                    return self._import_checks_from_csv(header_lower, data_rows)
                else:
                    return {
                        'status': 'error',
                        'message': f'Invalid import type: {import_type}'
                    }
                
        except Exception as e:
            _logger.error(f"Error processing import: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': str(e)
            }
        
    def _process_excel_import(self, file_path, import_type, column_mapping=None):
        """Process Excel files for import"""
        try:
            import xlrd
            import openpyxl
            
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # Data yang akan diproses
            headers = []
            data_rows = []
            
            if file_ext == '.xlsx':
                try:
                    # Gunakan openpyxl untuk XLSX files tanpa membaca sebagai text
                    workbook = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
                    sheet = workbook.active
                    
                    # Process rows
                    for i, row in enumerate(sheet.rows):
                        if i == 0:
                            # Headers
                            headers = [str(cell.value).strip() if cell.value is not None else '' for cell in row]
                        else:
                            # Data rows
                            data_row = []
                            for cell in row:
                                # Tangani berbagai tipe data dengan benar
                                if cell.value is None:
                                    data_row.append('')
                                elif isinstance(cell.value, (int, float)):
                                    data_row.append(cell.value)
                                else:
                                    data_row.append(str(cell.value))
                            
                            if any(data_row):  # Skip empty rows
                                data_rows.append(data_row)
                except Exception as e:
                    _logger.error(f"Error processing XLSX with openpyxl: {str(e)}")
                    # Fallback ke pendekatan lain jika openpyxl gagal
                    raise
                            
            elif file_ext == '.xls':
                # Untuk file XLS, gunakan xlrd yang lebih stabil
                workbook = xlrd.open_workbook(file_path)
                sheet = workbook.sheet_by_index(0)
                
                # Get headers
                headers = []
                for col in range(sheet.ncols):
                    cell_value = sheet.cell_value(0, col)
                    headers.append(str(cell_value).strip())
                
                # Get data rows
                for row_idx in range(1, sheet.nrows):
                    row = []
                    for col_idx in range(sheet.ncols):
                        cell = sheet.cell(row_idx, col_idx)
                        if cell.ctype == xlrd.XL_CELL_DATE:
                            # Tangani format tanggal dengan benar
                            date_tuple = xlrd.xldate_as_tuple(cell.value, workbook.datemode)
                            row.append(f"{date_tuple[0]}-{date_tuple[1]:02d}-{date_tuple[2]:02d}")
                        else:
                            row.append(str(cell.value) if cell.value != '' else '')
                    
                    if any(row):  # Skip empty rows
                        data_rows.append(row)
            else:
                return {
                    'status': 'error',
                    'message': f'Unsupported file format: {file_ext}'
                }
            
            # Hapus karakter non-UTF8 dari headers jika perlu
            cleaned_headers = []
            for header in headers:
                # Hapus karakter khusus, atur encoding
                cleaned_header = ''.join(c for c in header if c.isprintable())
                cleaned_headers.append(cleaned_header)
            
            headers = cleaned_headers
            
            # Apply column mapping if provided
            original_headers = headers
            if column_mapping:
                mapped_headers = []
                for h in original_headers:
                    # Look for exact match first, then case-insensitive
                    if h in column_mapping:
                        mapped_headers.append(column_mapping[h])
                    elif h.lower() in {k.lower(): v for k, v in column_mapping.items()}:
                        mapped_key = next(k for k in column_mapping.keys() if k.lower() == h.lower())
                        mapped_headers.append(column_mapping[mapped_key])
                    else:
                        mapped_headers.append(h)
                
                headers = mapped_headers
                _logger.info(f"Applied column mapping. Original: {original_headers}, Mapped: {headers}")
            
            # Convert headers to lowercase for processing
            header_lower = [h.lower().strip() for h in headers]
            
            # Process the import based on type
            if import_type == 'tools':
                return self._import_tools_from_csv(header_lower, data_rows)
            elif import_type == 'categories':
                return self._import_categories_from_csv(header_lower, data_rows)
            elif import_type == 'checks':
                return self._import_checks_from_csv(header_lower, data_rows)
            else:
                return {
                    'status': 'error',
                    'message': f'Invalid import type: {import_type}'
                }
                
        except ImportError as e:
            return {
                'status': 'error',
                'message': f'Missing required library for Excel processing: {str(e)}. Please install xlrd and openpyxl.'
            }
        except Exception as e:
            _logger.error("Error processing Excel import: %s", str(e))
            return {
                'status': 'error',
                'message': f'Error processing Excel file: {str(e)}'
            }
    
    def _import_tools_from_csv(self, header, data_rows):
        """Import tools from CSV data"""
        required_fields = ['name']
        
        # Check required fields
        for field in required_fields:
            if field not in header:
                return {
                    'status': 'error',
                    'message': f'Required field "{field}" not found in the file header.'
                }
        
        # Convert data to JSON format
        tools = []
        for row in data_rows:
            if not row or not any(row):  # Skip empty rows
                continue
                
            tool = {}
            for i, field in enumerate(header):
                if i < len(row) and row[i]:
                    tool[field] = row[i]
            
            tools.append(tool)
        
        # Process the tools data
        return self._import_tools_from_json(tools)
    
    def _import_categories_from_csv(self, header, data_rows):
        """Import categories from CSV data"""
        required_fields = ['name']
        
        # Check required fields
        for field in required_fields:
            if field not in header:
                return {
                    'status': 'error',
                    'message': f'Required field "{field}" not found in the file header.'
                }
        
        # Convert data to JSON format
        categories = []
        for row in data_rows:
            if not row or not any(row):  # Skip empty rows
                continue
                
            category = {}
            for i, field in enumerate(header):
                if i < len(row) and row[i]:
                    category[field] = row[i]
            
            categories.append(category)
        
        # Process the categories data
        return self._import_categories_from_json(categories)
    
    def _import_checks_from_csv(self, header, data_rows):
        """Import checks from CSV data"""
        required_fields = ['mechanic', 'date']
        
        # Check required fields
        for field in required_fields:
            if field not in header:
                return {
                    'status': 'error',
                    'message': f'Required field "{field}" not found in the file header.'
                }
        
        # Convert data to JSON format
        checks = []
        for row in data_rows:
            if not row or not any(row):  # Skip empty rows
                continue
                
            check = {}
            for i, field in enumerate(header):
                if i < len(row) and row[i]:
                    check[field] = row[i]
            
            checks.append(check)
        
        # Process the checks data
        return self._import_checks_from_json(checks)
    
    def _import_tools_from_json(self, tools_data):
        """Import tools from JSON data"""
        if not tools_data:
            return {
                'status': 'error',
                'message': 'No tool data provided'
            }
        
        tools_created = 0
        tools_updated = 0
        tools_skipped = 0
        errors = []
        
        for tool_idx, tool_data in enumerate(tools_data, start=1):
            try:
                name = tool_data.get('name')
                
                if not name:
                    tools_skipped += 1
                    errors.append(f"Tool #{tool_idx}: Skipped due to missing name")
                    continue
                
                # Prepare values
                values = {
                    'name': name,
                }
                
                # Add optional fields
                optional_fields = {
                    'code': 'code',
                    'description': 'description',
                    'qty_expected': 'qty_expected',
                    'location': 'location',
                    'serial_number': 'serial_number',
                    'state': 'state',
                    'notes': 'notes',
                }
                
                for key, field in optional_fields.items():
                    if key in tool_data:
                        values[field] = tool_data[key]
                
                # Handle numeric fields
                if 'qty_expected' in values:
                    try:
                        values['qty_expected'] = int(float(values['qty_expected']))
                    except (ValueError, TypeError):
                        values['qty_expected'] = 1
                
                # Handle dates
                date_fields = {
                    'purchase_date': 'purchase_date',
                    'warranty_end_date': 'warranty_end_date',
                    'last_maintenance_date': 'last_maintenance_date',
                }
                
                for key, field in date_fields.items():
                    if key in tool_data and tool_data[key]:
                        try:
                            values[field] = datetime.strptime(tool_data[key], '%Y-%m-%d').date()
                        except ValueError:
                            errors.append(f"Tool #{tool_idx}: Invalid date format for {key}: {tool_data[key]}")
                
                # Handle related fields
                if 'category' in tool_data and tool_data['category']:
                    category_name = tool_data['category']
                    category = request.env['pitcar.tool.category'].sudo().search([('name', '=', category_name)], limit=1)
                    if not category:
                        # Create category if it doesn't exist
                        category = request.env['pitcar.tool.category'].sudo().create({
                            'name': category_name,
                        })
                    values['category_id'] = category.id
                
                if 'mechanic' in tool_data and tool_data['mechanic']:
                    mechanic_name = tool_data['mechanic']
                    mechanic = request.env['hr.employee'].sudo().search([
                        ('name', '=', mechanic_name),
                        ('job_id.name', 'ilike', 'mechanic'),
                    ], limit=1)
                    if mechanic:
                        values['mechanic_id'] = mechanic.id
                        # Set to assigned state if mechanic is provided
                        values['state'] = 'assigned'
                        values['date_assigned'] = datetime.now().date()
                    else:
                        errors.append(f"Tool #{tool_idx}: Mechanic not found: {mechanic_name}")
                
                if 'maintenance_frequency' in tool_data:
                    freq = tool_data['maintenance_frequency'].lower()
                    valid_freqs = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly']
                    if freq in valid_freqs:
                        values['maintenance_frequency'] = freq
                    else:
                        errors.append(f"Tool #{tool_idx}: Invalid maintenance frequency: {freq}")
                
                if 'state' in values:
                    state = values['state'].lower()
                    valid_states = ['available', 'assigned', 'maintenance', 'lost', 'damaged']
                    if state not in valid_states:
                        errors.append(f"Tool #{tool_idx}: Invalid state: {state}")
                        values['state'] = 'available'
                
                # Check if tool already exists
                existing_tool = None
                if values.get('code'):
                    existing_tool = request.env['pitcar.mechanic.hand.tool'].sudo().search([
                        ('code', '=', values['code']),
                    ], limit=1)
                
                if not existing_tool:
                    existing_tool = request.env['pitcar.mechanic.hand.tool'].sudo().search([
                        ('name', '=', values['name']),
                    ], limit=1)
                
                if existing_tool:
                    # Update existing tool
                    existing_tool.write(values)
                    tools_updated += 1
                else:
                    # Create new tool
                    request.env['pitcar.mechanic.hand.tool'].sudo().create(values)
                    tools_created += 1
                
            except Exception as e:
                tools_skipped += 1
                errors.append(f"Tool #{tool_idx}: {str(e)}")
                _logger.error("Error importing tool #%s: %s", tool_idx, str(e))
        
        return {
            'status': 'success',
            'data': {
                'created': tools_created,
                'updated': tools_updated,
                'skipped': tools_skipped,
                'errors': errors[:10],  # Limit to first 10 errors
                'total_errors': len(errors)
            }
        }
    
    def _import_categories_from_json(self, categories_data):
        """Import categories from JSON data"""
        if not categories_data:
            return {
                'status': 'error',
                'message': 'No category data provided'
            }
        
        categories_created = 0
        categories_updated = 0
        categories_skipped = 0
        errors = []
        
        # First pass: create categories without parent relationships
        categories_map = {}  # name -> id mapping
        
        for cat_idx, cat_data in enumerate(categories_data, start=1):
            try:
                name = cat_data.get('name')
                
                if not name:
                    categories_skipped += 1
                    errors.append(f"Category #{cat_idx}: Skipped due to missing name")
                    continue
                
                # Prepare values
                values = {
                    'name': name,
                    'description': cat_data.get('description', ''),
                }
                
                # Check if category already exists
                existing_category = request.env['pitcar.tool.category'].sudo().search([
                    ('name', '=', name),
                ], limit=1)
                
                if existing_category:
                    # Update existing category
                    existing_category.write(values)
                    categories_map[name] = existing_category.id
                    categories_updated += 1
                else:
                    # Create new category
                    new_category = request.env['pitcar.tool.category'].sudo().create(values)
                    categories_map[name] = new_category.id
                    categories_created += 1
                
            except Exception as e:
                categories_skipped += 1
                errors.append(f"Category #{cat_idx}: {str(e)}")
                _logger.error("Error importing category #%s: %s", cat_idx, str(e))
        
        # Second pass: update parent relationships
        parent_updates = 0
        
        for cat_idx, cat_data in enumerate(categories_data, start=1):
            try:
                name = cat_data.get('name')
                parent_name = cat_data.get('parent')
                
                if not name or not parent_name:
                    continue
                
                category_id = categories_map.get(name)
                parent_id = categories_map.get(parent_name)
                
                if category_id and parent_id and category_id != parent_id:  # Avoid self-reference
                    request.env['pitcar.tool.category'].sudo().browse(category_id).write({
                        'parent_id': parent_id
                    })
                    parent_updates += 1
                
            except Exception as e:
                errors.append(f"Category #{cat_idx}: Error setting parent: {str(e)}")
                _logger.error("Error setting parent for category #%s: %s", cat_idx, str(e))
        
        return {
            'status': 'success',
            'data': {
                'created': categories_created,
                'updated': categories_updated,
                'parent_updates': parent_updates,
                'skipped': categories_skipped,
                'errors': errors[:10],  # Limit to first 10 errors
                'total_errors': len(errors)
            }
        }
    
    def _import_checks_from_json(self, checks_data):
        """Import checks from JSON data"""
        if not checks_data:
            return {
                'status': 'error',
                'message': 'No check data provided'
            }
        
        checks_created = 0
        checks_updated = 0
        checks_skipped = 0
        check_lines_processed = 0
        errors = []
        
        # Group records by mechanic and date
        grouped_checks = {}
        for check_idx, check_data in enumerate(checks_data, start=1):
            try:
                mechanic_name = check_data.get('mechanic')
                date_str = check_data.get('date')
                
                if not mechanic_name or not date_str:
                    checks_skipped += 1
                    errors.append(f"Check #{check_idx}: Skipped due to missing mechanic or date")
                    continue
                
                key = (mechanic_name, date_str)
                if key not in grouped_checks:
                    grouped_checks[key] = []
                
                grouped_checks[key].append((check_idx, check_data))
                
            except Exception as e:
                checks_skipped += 1
                errors.append(f"Check #{check_idx}: {str(e)}")
                _logger.error("Error grouping check #%s: %s", check_idx, str(e))
        
        # Process each unique check
        for (mechanic_name, date_str), check_records in grouped_checks.items():
            try:
                # Find mechanic
                mechanic = request.env['hr.employee'].sudo().search([
                    ('name', '=', mechanic_name),
                    ('job_id.name', 'ilike', 'mechanic'),
                ], limit=1)
                
                if not mechanic:
                    for check_idx, _ in check_records:
                        errors.append(f"Check #{check_idx}: Mechanic not found: {mechanic_name}")
                    continue
                
                # Parse date
                try:
                    check_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    for check_idx, _ in check_records:
                        errors.append(f"Check #{check_idx}: Invalid date format: {date_str}")
                    continue
                
                # Get first record for check data
                _, first_check = check_records[0]
                
                # Check if a check already exists for this mechanic and date
                existing_check = request.env['pitcar.mechanic.tool.check'].sudo().search([
                    ('mechanic_id', '=', mechanic.id),
                    ('date', '=', check_date),
                ], limit=1)
                
                if existing_check:
                    check = existing_check
                    # Update notes if provided
                    if 'notes' in first_check:
                        check.write({'notes': first_check['notes']})
                    checks_updated += 1
                else:
                    # Create new check
                    check = request.env['pitcar.mechanic.tool.check'].sudo().create({
                        'mechanic_id': mechanic.id,
                        'date': check_date,
                        'notes': first_check.get('notes', ''),
                    })
                    checks_created += 1
                
                # Process all check records to update check lines
                for check_idx, check_data in check_records:
                    tool_data = {
                        'tool_name': check_data.get('tool_name'),
                        'tool_code': check_data.get('tool_code'),
                        'qty_actual': check_data.get('qty_actual'),
                        'physical_condition': check_data.get('physical_condition'),
                        'line_notes': check_data.get('line_notes'),
                    }
                    
                    # Skip if no tool identifier is provided
                    if not tool_data['tool_name'] and not tool_data['tool_code']:
                        continue
                    
                    # Find tool
                    tool = None
                    if tool_data['tool_code']:
                        tool = request.env['pitcar.mechanic.hand.tool'].sudo().search([
                            ('code', '=', tool_data['tool_code']),
                        ], limit=1)
                    
                    if not tool and tool_data['tool_name']:
                        tool = request.env['pitcar.mechanic.hand.tool'].sudo().search([
                            ('name', '=', tool_data['tool_name']),
                        ], limit=1)
                    
                    if not tool:
                        errors.append(f"Check #{check_idx}: Tool not found: {tool_data['tool_code'] or tool_data['tool_name']}")
                        continue
                    
                    # Find or create check line
                    check_line = request.env['pitcar.mechanic.tool.check.line'].sudo().search([
                        ('check_id', '=', check.id),
                        ('tool_id', '=', tool.id),
                    ], limit=1)
                    
                    line_values = {}
                    
                    if tool_data['qty_actual']:
                        try:
                            line_values['qty_actual'] = int(float(tool_data['qty_actual']))
                        except (ValueError, TypeError):
                            errors.append(f"Check #{check_idx}: Invalid quantity: {tool_data['qty_actual']}")
                    
                    if tool_data['physical_condition']:
                        condition = tool_data['physical_condition'].lower()
                        valid_conditions = ['good', 'fair', 'poor', 'damaged', 'missing']
                        if condition in valid_conditions:
                            line_values['physical_condition'] = condition
                        else:
                            errors.append(f"Check #{check_idx}: Invalid condition: {tool_data['physical_condition']}")
                    
                    if tool_data['line_notes']:
                        line_values['notes'] = tool_data['line_notes']
                    
                    if check_line:
                        # Update existing line
                        if line_values:
                            check_line.write(line_values)
                            check_lines_processed += 1
                    else:
                        # Create new line
                        line_values.update({
                            'check_id': check.id,
                            'tool_id': tool.id,
                            'qty_expected': tool.qty_expected,
                        })
                        request.env['pitcar.mechanic.tool.check.line'].sudo().create(line_values)
                        check_lines_processed += 1
                
                # Set check state if provided
                if 'state' in first_check and first_check['state'] == 'done' and check.state != 'done':
                    check.sudo().action_done()
                
            except Exception as e:
                checks_skipped += 1
                errors.append(f"Check for {mechanic_name}/{date_str}: {str(e)}")
                _logger.error("Error processing check %s/%s: %s", mechanic_name, date_str, str(e))
        
        return {
            'status': 'success',
            'data': {
                'created': checks_created,
                'updated': checks_updated,
                'check_lines': check_lines_processed,
                'skipped': checks_skipped,
                'errors': errors[:10],  # Limit to first 10 errors
                'total_errors': len(errors)
            }
        }