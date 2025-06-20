# controllers/product_catalog_api.py
from odoo import http, fields
from odoo.http import request
import json
import logging
import re
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class ProductCatalogAPI(http.Controller):
    
    def _check_cost_price_access(self, user=None):
        """
        Cek apakah user boleh melihat cost price
        Returns: True jika boleh melihat, False jika tidak
        """
        if not user:
            user = request.env.user
        
        # Administrator selalu bisa lihat
        if user.id == 1:
            return True
        
        # Cek grup yang diizinkan
        allowed_groups = [
            'purchase.group_purchase_manager',
            'stock.group_stock_manager', 
            'account.group_account_manager',
            'base.group_system',
        ]
        
        for group_xml_id in allowed_groups:
            if user.has_group(group_xml_id):
                return True
        
        # Kondisi custom - manager dari department tertentu
        if user.employee_id:
            department = user.employee_id.department_id
            if department and department.name in ['Finance', 'Purchasing', 'Warehouse']:
                return True
        
        return False
    
    def _get_product_attachments(self, product):
        """
        Mendapatkan attachments untuk product dengan cara yang benar
        """
        try:
            attachments = []
            
            # Method 1: Cari di ir.attachment berdasarkan res_model dan res_id
            attachment_domain = [
                ('res_model', '=', 'product.template'),
                ('res_id', '=', product.id),
                ('public', '=', True)  # Hanya ambil yang public
            ]
            
            ir_attachments = request.env['ir.attachment'].sudo().search(attachment_domain)
            
            for attachment in ir_attachments:
                attachments.append({
                    'id': attachment.id,
                    'name': attachment.name or 'Unnamed file',
                    'mimetype': attachment.mimetype or '',
                    'size': attachment.file_size or 0,
                    'url': f'/web/content/{attachment.id}?download=true',
                    'is_image': attachment.mimetype.startswith('image/') if attachment.mimetype else False,
                    'create_date': attachment.create_date.isoformat() if attachment.create_date else None,
                })
            
            # Method 2: Jika product memiliki message_attachment_ids (dari mail module)
            if hasattr(product, 'message_attachment_ids'):
                for attachment in product.message_attachment_ids:
                    # Avoid duplicates
                    if not any(att['id'] == attachment.id for att in attachments):
                        attachments.append({
                            'id': attachment.id,
                            'name': attachment.name or 'Unnamed file',
                            'mimetype': attachment.mimetype or '',
                            'size': attachment.file_size or 0,
                            'url': f'/web/content/{attachment.id}?download=true',
                            'is_image': attachment.mimetype.startswith('image/') if attachment.mimetype else False,
                            'create_date': attachment.create_date.isoformat() if attachment.create_date else None,
                        })
            
            # Method 3: Jika ada custom field attachment_ids
            if hasattr(product, 'attachment_ids'):
                for attachment in product.attachment_ids:
                    # Avoid duplicates
                    if not any(att['id'] == attachment.id for att in attachments):
                        attachments.append({
                            'id': attachment.id,
                            'name': attachment.name or 'Unnamed file',
                            'mimetype': attachment.mimetype or '',
                            'size': attachment.file_size or 0,
                            'url': f'/web/content/{attachment.id}?download=true',
                            'is_image': attachment.mimetype.startswith('image/') if attachment.mimetype else False,
                            'create_date': attachment.create_date.isoformat() if attachment.create_date else None,
                        })
            
            return attachments
            
        except Exception as e:
            _logger.error(f"Error getting product attachments: {str(e)}")
            return []
    
    def _build_search_domain(self, search_query):
        """
        Membangun domain pencarian yang komprehensif dan benar
        """
        if not search_query:
            return []
        
        # Clean dan validasi search query
        search_query = search_query.strip()
        if not search_query or len(search_query) < 2:
            return []
        
        # Split search terms dengan berbagai delimiter
        search_terms = re.split(r'[\s,;]+', search_query.lower())
        search_terms = [term.strip() for term in search_terms if term.strip() and len(term) >= 2]
        
        if not search_terms:
            return []
        
        # Jika hanya satu term, buat domain OR sederhana
        if len(search_terms) == 1:
            term = search_terms[0]
            return [
                '|', '|', '|', '|', '|',
                ('name', 'ilike', term),
                ('default_code', 'ilike', term), 
                ('barcode', 'ilike', term),
                ('categ_id.name', 'ilike', term),
                ('categ_id.complete_name', 'ilike', term),
                ('description_sale', 'ilike', term)
            ]
        
        # Untuk multiple terms, cari produk yang mengandung SEMUA term (AND logic)
        domain_list = []
        for term in search_terms:
            term_domain = [
                '|', '|', '|', '|', '|',
                ('name', 'ilike', term),
                ('default_code', 'ilike', term),
                ('barcode', 'ilike', term),
                ('categ_id.name', 'ilike', term),
                ('categ_id.complete_name', 'ilike', term),
                ('description_sale', 'ilike', term)
            ]
            domain_list.append(term_domain)
        
        # Gabungkan dengan AND
        final_domain = domain_list[0]
        for additional_domain in domain_list[1:]:
            final_domain = ['&'] + final_domain + additional_domain
        
        return final_domain
    
    def _build_filter_domain(self, kw, access_level):
        """
        Membangun domain untuk filter-filter lainnya
        """
        domain = []
        
        # Filter basic berdasarkan access level
        if access_level == 'public':
            domain.extend([
                ('sale_ok', '=', True),
                ('active', '=', True),
            ])
        elif access_level in ['internal', 'manager']:
            # Internal bisa lihat semua, tapi bisa filter active
            active_only = kw.get('active_only')
            if active_only is None or str(active_only).lower() in ['true', '1', 'yes']:
                domain.append(('active', '=', True))
        
        # Filter by category - PERBAIKAN: pastikan tipe data benar
        if kw.get('categ_id'):
            try:
                categ_id = int(kw['categ_id'])
                domain.append(('categ_id', '=', categ_id))
            except (ValueError, TypeError):
                _logger.warning(f"Invalid categ_id: {kw.get('categ_id')}")
        
        elif kw.get('categ_ids'):
            try:
                if isinstance(kw['categ_ids'], list):
                    categ_ids = [int(x) for x in kw['categ_ids']]
                else:
                    categ_ids = [int(x) for x in json.loads(kw['categ_ids'])]
                domain.append(('categ_id', 'in', categ_ids))
            except (ValueError, TypeError, json.JSONDecodeError):
                _logger.warning(f"Invalid categ_ids: {kw.get('categ_ids')}")
        
        # Filter by type
        if kw.get('product_type'):
            valid_types = ['product', 'service', 'consu']
            if kw['product_type'] in valid_types:
                domain.append(('type', '=', kw['product_type']))
        
        # Filter by availability
        if kw.get('available_only'):
            if str(kw['available_only']).lower() in ['true', '1', 'yes']:
                domain.append(('qty_available', '>', 0))
        
        # Filter price range
        if kw.get('min_price'):
            try:
                min_price = float(kw['min_price'])
                domain.append(('list_price', '>=', min_price))
            except (ValueError, TypeError):
                _logger.warning(f"Invalid min_price: {kw.get('min_price')}")
        
        if kw.get('max_price'):
            try:
                max_price = float(kw['max_price'])
                domain.append(('list_price', '<=', max_price))
            except (ValueError, TypeError):
                _logger.warning(f"Invalid max_price: {kw.get('max_price')}")
        
        # Filter sale_ok untuk internal jika diminta
        if access_level in ['internal', 'manager'] and kw.get('sale_only'):
            if str(kw['sale_only']).lower() in ['true', '1', 'yes']:
                domain.append(('sale_ok', '=', True))
        
        # Filter purchase_ok untuk internal jika diminta
        if access_level in ['internal', 'manager'] and kw.get('purchase_only'):
            if str(kw['purchase_only']).lower() in ['true', '1', 'yes']:
                domain.append(('purchase_ok', '=', True))
        
        # Filter custom fields untuk internal/manager
        if access_level in ['internal', 'manager']:
            # Filter mandatory stock
            if kw.get('mandatory_stock_only'):
                if str(kw['mandatory_stock_only']).lower() in ['true', '1', 'yes']:
                    if hasattr(request.env['product.template'], '_fields') and 'is_mandatory_stock' in request.env['product.template']._fields:
                        domain.append(('is_mandatory_stock', '=', True))
            
            # Filter by inventory age category
            if kw.get('inventory_age_category'):
                valid_categories = ['new', 'medium', 'old', 'very_old']
                if kw['inventory_age_category'] in valid_categories:
                    if hasattr(request.env['product.template'], '_fields') and 'inventory_age_category' in request.env['product.template']._fields:
                        domain.append(('inventory_age_category', '=', kw['inventory_age_category']))
            
            # Filter by service duration
            if kw.get('has_service_duration'):
                if str(kw['has_service_duration']).lower() in ['true', '1', 'yes']:
                    if hasattr(request.env['product.template'], '_fields') and 'service_duration' in request.env['product.template']._fields:
                        domain.append(('service_duration', '>', 0))
            
            # Filter low stock
            if kw.get('low_stock_only'):
                if str(kw['low_stock_only']).lower() in ['true', '1', 'yes']:
                    domain.append(('qty_available', '<=', 5))
            
            # Filter below mandatory level
            if kw.get('below_mandatory_only'):
                if str(kw['below_mandatory_only']).lower() in ['true', '1', 'yes']:
                    if hasattr(request.env['product.template'], '_fields') and 'is_below_mandatory_level' in request.env['product.template']._fields:
                        domain.append(('is_below_mandatory_level', '=', True))
        
        return domain

    def _sort_products_by_stock(self, products, sort_order='desc'):
        """Quick fix untuk stock sorting"""
        try:
            # Convert recordset ke list dengan stock values
            product_stock_pairs = []
            for product in products:
                stock_qty = getattr(product, 'qty_available', 0) or 0
                product_stock_pairs.append((product, float(stock_qty)))
            
            # Sort berdasarkan stock
            reverse = sort_order == 'desc'
            sorted_pairs = sorted(product_stock_pairs, key=lambda x: x[1], reverse=reverse)
            
            # Return sorted recordset
            sorted_ids = [pair[0].id for pair in sorted_pairs]
            return request.env['product.template'].sudo().browse(sorted_ids)
        except Exception as e:
            _logger.error(f"Stock sorting error: {str(e)}")
            return products
        
    def _get_products_with_stock_sorting(self, domain, sort_field, sort_order, limit, offset):
        """
        Handle stock sorting dengan post-processing sederhana
        """
        if sort_field != 'qty_available':
            # Normal sorting untuk field lain
            order = f"{sort_field} {sort_order}"
            products = request.env['product.template'].sudo().search(
                domain, 
                limit=limit, 
                offset=offset, 
                order=order
            )
            total = request.env['product.template'].sudo().search_count(domain)
            return products, total
        
        # Special handling untuk qty_available
        try:
            # Ambil semua data untuk halaman saat ini + buffer
            buffer_size = limit * 3  # Ambil 3x lebih banyak untuk ensure correct sorting
            extended_limit = offset + buffer_size
            
            # Ambil data dengan default sorting
            all_products = request.env['product.template'].sudo().search(
                domain, 
                limit=extended_limit, 
                order='name asc'  # Fallback sorting
            )
            
            # Convert ke list untuk sorting
            products_with_stock = []
            for product in all_products:
                try:
                    stock_qty = product.qty_available if hasattr(product, 'qty_available') else 0.0
                    products_with_stock.append({
                        'product': product,
                        'stock': float(stock_qty)
                    })
                except:
                    products_with_stock.append({
                        'product': product,
                        'stock': 0.0
                    })
            
            # Sort berdasarkan stock
            reverse = sort_order == 'desc'
            sorted_products = sorted(products_with_stock, key=lambda x: x['stock'], reverse=reverse)
            
            # Apply pagination
            paginated_products = sorted_products[offset:offset + limit]
            products = request.env['product.template'].sudo().browse([p['product'].id for p in paginated_products])
            
            # Total count
            total = request.env['product.template'].sudo().search_count(domain)
            
            _logger.info(f"Stock sorting applied: {len(sorted_products)} total, showing {len(products)} for page")
            return products, total
            
        except Exception as e:
            _logger.error(f"Stock sorting failed: {str(e)}")
            # Fallback ke normal sorting
            products = request.env['product.template'].sudo().search(
                domain, 
                limit=limit, 
                offset=offset, 
                order='name asc'
            )
            total = request.env['product.template'].sudo().search_count(domain)
            return products, total

    
    def _prepare_product_template_data(self, product, access_level='public', include_variants=False, include_attachments=False):
        """
        Menyiapkan data product template sesuai access level
        """
        try:
            # Data dasar yang selalu ditampilkan
            data = {
                'id': product.id,
                'name': product.name,
                'default_code': product.default_code,
                'barcode': product.barcode,
                'list_price': product.list_price,
                'currency_id': {
                    'id': product.currency_id.id,
                    'name': product.currency_id.name,
                    'symbol': product.currency_id.symbol
                } if product.currency_id else None,
                'categ_id': {
                    'id': product.categ_id.id,
                    'name': product.categ_id.name,
                    'complete_name': product.categ_id.complete_name
                } if product.categ_id else None,
                'uom_id': {
                    'id': product.uom_id.id,
                    'name': product.uom_id.name
                } if product.uom_id else None,
                'type': product.type,
                'active': product.active,
                'sale_ok': product.sale_ok,
                'purchase_ok': product.purchase_ok,
                'tracking': product.tracking,
                'weight': product.weight,
                'volume': product.volume,
                'image_1920_url': f'/web/image/product.template/{product.id}/image_1920' if product.image_1920 else None,
                'image_128_url': f'/web/image/product.template/{product.id}/image_128' if product.image_128 else None,
            }
            
            # Tambahkan description berdasarkan access level
            if access_level in ['internal', 'manager']:
                data.update({
                    'description': product.description,
                    'description_purchase': product.description_purchase,
                    'description_sale': product.description_sale,
                })
            else:  # public
                data['description'] = product.description_sale
            
            # Stock information untuk internal dan manager
            if access_level in ['internal', 'manager']:
                data.update({
                    'qty_available': product.qty_available,
                    'virtual_available': product.virtual_available,
                    'incoming_qty': product.incoming_qty,
                    'outgoing_qty': product.outgoing_qty,
                })
                
                # Custom fields dari model Anda - dengan safety check
                if hasattr(product, 'inventory_age_days'):
                    data.update({
                        'inventory_age': getattr(product, 'inventory_age', None),
                        'inventory_age_days': getattr(product, 'inventory_age_days', None),
                        'inventory_age_category': getattr(product, 'inventory_age_category', None),
                    })
                
                if hasattr(product, 'is_mandatory_stock'):
                    data.update({
                        'is_mandatory_stock': getattr(product, 'is_mandatory_stock', False),
                        'min_mandatory_stock': getattr(product, 'min_mandatory_stock', 0),
                        'is_below_mandatory_level': getattr(product, 'is_below_mandatory_level', False),
                    })
                
                # Service fields
                if hasattr(product, 'service_duration'):
                    data.update({
                        'service_duration': getattr(product, 'service_duration', 0),
                        'flat_rate': getattr(product, 'flat_rate', False),
                        'flat_rate_value': getattr(product, 'flat_rate_value', 0),
                    })
            
            # Cost price - hanya untuk yang punya akses
            if access_level == 'manager' and self._check_cost_price_access():
                data.update({
                    'standard_price': product.standard_price,
                    'cost_price_visible': True,
                })
            else:
                data.update({
                    'standard_price': 0.0,
                    'cost_price_visible': False,
                    'cost_price_message': 'Access restricted' if access_level == 'internal' else None,
                })
            
            # Supplier information untuk internal dan manager
            if access_level in ['internal', 'manager'] and hasattr(product, 'seller_ids') and product.seller_ids:
                suppliers = []
                for seller in product.seller_ids[:3]:  # Max 3 suppliers
                    supplier_data = {
                        'id': seller.id,
                        'partner_id': {
                            'id': seller.partner_id.id,
                            'name': seller.partner_id.name,
                        },
                        'product_code': seller.product_code,
                        'min_qty': seller.min_qty,
                        'delay': seller.delay,
                    }
                    # Price hanya untuk manager
                    if access_level == 'manager':
                        supplier_data['price'] = seller.price
                    suppliers.append(supplier_data)
                data['suppliers'] = suppliers
            
            # Variants jika diminta
            if include_variants and hasattr(product, 'product_variant_ids') and product.product_variant_ids:
                variants = []
                for variant in product.product_variant_ids:
                    variant_data = self._prepare_product_variant_data(variant, access_level)
                    variants.append(variant_data)
                data['variants'] = variants
            else:
                data['variant_count'] = len(product.product_variant_ids) if hasattr(product, 'product_variant_ids') else 1
            
            # Attachments jika diminta dan access internal/manager
            if include_attachments and access_level in ['internal', 'manager']:
                attachments = self._get_product_attachments(product)
                data['attachments'] = attachments
            
            return data
            
        except Exception as e:
            _logger.error(f"Error preparing product template data for product {product.id}: {str(e)}")
            return {'error': str(e)}
    
    def _prepare_product_variant_data(self, variant, access_level='public'):
        """Menyiapkan data product variant"""
        try:
            data = {
                'id': variant.id,
                'default_code': variant.default_code,
                'barcode': variant.barcode,
                'lst_price': variant.lst_price,
                'weight': variant.weight,
                'volume': variant.volume,
                'active': variant.active,
                'product_template_attribute_value_ids': [
                    {
                        'id': pav.id,
                        'attribute_id': {
                            'id': pav.attribute_id.id,
                            'name': pav.attribute_id.name,
                        },
                        'product_attribute_value_id': {
                            'id': pav.product_attribute_value_id.id,
                            'name': pav.product_attribute_value_id.name,
                        }
                    } for pav in variant.product_template_attribute_value_ids
                ] if hasattr(variant, 'product_template_attribute_value_ids') else [],
                'image_variant_1920_url': f'/web/image/product.product/{variant.id}/image_variant_1920' if variant.image_variant_1920 else None,
            }
            
            # Stock untuk internal/manager
            if access_level in ['internal', 'manager']:
                data.update({
                    'qty_available': variant.qty_available,
                    'virtual_available': variant.virtual_available,
                })
            
            # Cost price untuk manager dengan akses
            if access_level == 'manager' and self._check_cost_price_access():
                data['standard_price'] = variant.standard_price
            
            return data
            
        except Exception as e:
            _logger.error(f"Error preparing variant data: {str(e)}")
            return {'error': str(e)}
    
    @http.route('/web/v2/catalog/products', type='json', auth='user', methods=['POST'], csrf=False)
    def get_products(self, **kw):
        """
        Endpoint utama untuk mengambil data produk dengan filter komprehensif
        """
        try:
            # Parse parameters
            access_level = kw.get('access_level', 'public')
            include_variants = str(kw.get('include_variants', False)).lower() in ['true', '1', 'yes']
            include_attachments = str(kw.get('include_attachments', False)).lower() in ['true', '1', 'yes']
            
            # Validasi access level
            if access_level not in ['public', 'internal', 'manager']:
                if access_level == 'user':
                    access_level = 'internal'
                else:
                    access_level = 'public'
            
            # Build domain dari filter-filter
            domain = self._build_filter_domain(kw, access_level)
            
            # Tambahkan search domain jika ada
            if kw.get('search'):
                search_domain = self._build_search_domain(kw['search'])
                if search_domain:
                    # Gabungkan search domain dengan filter domain
                    if domain:
                        domain = ['&'] + domain + search_domain
                    else:
                        domain = search_domain
            
            # Sorting
            sort_field = kw.get('sort_field', 'name')
            allowed_sort_fields = ['name', 'default_code', 'list_price', 'qty_available', 'categ_id', 'create_date']
            if access_level in ['internal', 'manager']:
                allowed_sort_fields.extend(['standard_price'])
                # Only add custom fields if they exist
                if hasattr(request.env['product.template'], '_fields') and 'inventory_age_days' in request.env['product.template']._fields:
                    allowed_sort_fields.append('inventory_age_days')
            
            if sort_field not in allowed_sort_fields:
                sort_field = 'name'
            
            sort_order = kw.get('sort_order', 'asc')
            if sort_order not in ['asc', 'desc']:
                sort_order = 'asc'
            
            order = f"{sort_field} {sort_order}"
            
            # Pagination
            page = max(1, int(kw.get('page', 1)))
            limit = max(1, min(100, int(kw.get('limit', 20))))  # Max 100 per page
            offset = (page - 1) * limit
            
            # Log untuk debugging
            _logger.info(f"Product catalog search - Access: {access_level}")
            _logger.info(f"Search query: {kw.get('search')}")
            _logger.info(f"Final domain: {domain}")
            _logger.info(f"Sort: {order}, Page: {page}, Limit: {limit}")
            
            # Cari produk
            # products = request.env['product.template'].sudo().search(
            #     domain, 
            #     limit=limit, 
            #     offset=offset, 
            #     order=order
            # )

            # products, total = self._get_products_with_stock_sorting(
            #     domain, sort_field, sort_order, limit, offset
            # )

            if sort_field == 'qty_available':
                # Special handling untuk stock sorting
                all_products = request.env['product.template'].sudo().search(domain, order='name asc')
                sorted_products = self._sort_products_by_stock(all_products, sort_order)
                # Apply pagination setelah sorting
                products = sorted_products[offset:offset + limit]
            else:
                # Normal sorting untuk field lain
                products = request.env['product.template'].sudo().search(
                    domain, 
                    limit=limit, 
                    offset=offset, 
                    order=order
                )

            total = request.env['product.template'].sudo().search_count(domain)
            
            _logger.info(f"Search results: Found {len(products)} products out of {total} total")
            
            # Prepare data
            product_data = []
            for product in products:
                data = self._prepare_product_template_data(
                    product, 
                    access_level=access_level,
                    include_variants=include_variants,
                    include_attachments=include_attachments
                )
                product_data.append(data)
            
            # Response
            total_pages = (total + limit - 1) // limit if limit > 0 else 1
            
            response = {
                'status': 'success',
                'data': product_data,
                'pagination': {
                    'page': page,
                    'limit': limit,
                    'total': total,
                    'total_pages': total_pages
                },
                'access_info': {
                    'access_level': access_level,
                    'cost_price_accessible': self._check_cost_price_access() if access_level == 'manager' else False,
                    'user_id': request.env.user.id,
                    'user_name': request.env.user.name
                },
                'debug_info': {
                    'domain_used': domain,
                    'search_query': kw.get('search'),
                    'filters_applied': {k: v for k, v in kw.items() if k not in ['access_level', 'include_variants', 'include_attachments', 'page', 'limit', 'sort_field', 'sort_order']}
                }
            }
            
            return response
            
        except Exception as e:
            _logger.error(f"Error in get_products: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/catalog/product/<int:product_id>', type='json', auth='user', methods=['POST'], csrf=False)
    def get_product_detail(self, product_id, **kw):
        """
        Endpoint untuk mendapatkan detail produk by ID
        """
        try:
            access_level = kw.get('access_level', 'public')
            include_variants = str(kw.get('include_variants', True)).lower() in ['true', '1', 'yes']
            include_attachments = str(kw.get('include_attachments', True)).lower() in ['true', '1', 'yes']
            
            _logger.info(f"Getting product detail for ID: {product_id}, access_level: {access_level}")
            
            product = request.env['product.template'].sudo().browse(product_id)
            
            if not product.exists():
                return {'status': 'error', 'message': 'Product not found'}
            
            # Check access for non-public
            if access_level == 'public' and (not product.sale_ok or not product.active):
                return {'status': 'error', 'message': 'Product not available'}
            
            data = self._prepare_product_template_data(
                product,
                access_level=access_level,
                include_variants=include_variants,
                include_attachments=include_attachments
            )
            
            _logger.info(f"Product detail prepared successfully for ID: {product_id}")
            
            return {
                'status': 'success',
                'data': data,
                'access_info': {
                    'access_level': access_level,
                    'cost_price_accessible': self._check_cost_price_access() if access_level == 'manager' else False
                }
            }
            
        except Exception as e:
            _logger.error(f"Error in get_product_detail: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/catalog/categories', type='json', auth='user', methods=['POST'], csrf=False)
    def get_categories(self, **kw):
        """
        Endpoint untuk mendapatkan kategori produk
        """
        try:
            access_level = kw.get('access_level', 'public')
            include_product_count = str(kw.get('include_product_count', True)).lower() in ['true', '1', 'yes']
            
            domain = []
            
            # Filter parent category
            if kw.get('parent_id'):
                domain.append(('parent_id', '=', int(kw['parent_id'])))
            elif kw.get('top_level_only'):
                domain.append(('parent_id', '=', False))
            
            categories = request.env['product.category'].sudo().search(domain, order='name asc')
            
            category_data = []
            for category in categories:
                data = {
                    'id': category.id,
                    'name': category.name,
                    'complete_name': category.complete_name,
                    'parent_id': {
                        'id': category.parent_id.id,
                        'name': category.parent_id.name
                    } if category.parent_id else None,
                    'child_ids': [{'id': child.id, 'name': child.name} for child in category.child_id],
                }
                
                # Product count
                if include_product_count:
                    count_domain = [('categ_id', '=', category.id)]
                    if access_level == 'public':
                        count_domain.extend([('sale_ok', '=', True), ('active', '=', True)])
                    
                    product_count = request.env['product.template'].sudo().search_count(count_domain)
                    data['product_count'] = product_count
                
                category_data.append(data)
            
            return {
                'status': 'success',
                'data': category_data,
                'total': len(category_data)
            }
            
        except Exception as e:
            _logger.error(f"Error in get_categories: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/catalog/search/suggestions', type='json', auth='user', methods=['POST'], csrf=False)
    def get_search_suggestions(self, **kw):
        """
        Endpoint untuk autocomplete/suggestion saat search
        """
        try:
            query = kw.get('query', '').strip()
            access_level = kw.get('access_level', 'public')
            limit = int(kw.get('limit', 10))
            
            if len(query) < 2:  # Minimal 2 karakter
                return {'status': 'success', 'data': []}
            
            # Build basic domain berdasarkan access level
            domain = self._build_filter_domain({}, access_level)
            
            # Tambahkan search domain
            search_domain = self._build_search_domain(query)
            if search_domain:
                if domain:
                    domain = ['&'] + domain + search_domain
                else:
                    domain = search_domain
            else:
                return {'status': 'success', 'data': []}
            
            products = request.env['product.template'].sudo().search(domain, limit=limit, order='name asc')
            
            suggestions = []
            for product in products:
                suggestions.append({
                    'id': product.id,
                    'name': product.name,
                    'default_code': product.default_code,
                    'category': product.categ_id.name if product.categ_id else None,
                    'price': product.list_price,
                })
            
            return {'status': 'success', 'data': suggestions}
            
        except Exception as e:
            _logger.error(f"Error in get_search_suggestions: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @http.route('/web/v2/catalog/stats', type='json', auth='user', methods=['POST'], csrf=False)
    def get_catalog_stats(self, **kw):
        """
        Endpoint untuk mendapatkan statistik katalog
        """
        try:
            access_level = kw.get('access_level', 'public')
            
            stats = {}
            
            # Build domain berdasarkan access level
            base_domain = self._build_filter_domain({}, access_level)
            
            stats['total_products'] = request.env['product.template'].sudo().search_count(base_domain)
            
            # By category
            categories = request.env['product.category'].sudo().search([])
            category_stats = []
            for category in categories:
                cat_domain = base_domain + [('categ_id', '=', category.id)]
                count = request.env['product.template'].sudo().search_count(cat_domain)
                if count > 0:
                    category_stats.append({
                        'category_id': category.id,
                        'category_name': category.name,
                        'product_count': count
                    })
            
            stats['by_category'] = sorted(category_stats, key=lambda x: x['product_count'], reverse=True)
            
            # Additional stats untuk internal/manager
            if access_level in ['internal', 'manager']:
                stats['low_stock_count'] = request.env['product.template'].sudo().search_count([
                    ('active', '=', True),
                    ('qty_available', '<=', 5)
                ])
                
                # Check if custom fields exist before using them
                if hasattr(request.env['product.template'], '_fields') and 'is_below_mandatory_level' in request.env['product.template']._fields:
                    stats['mandatory_stock_below_min'] = request.env['product.template'].sudo().search_count([
                        ('active', '=', True),
                        ('is_below_mandatory_level', '=', True)
                    ])
            
            return {'status': 'success', 'data': stats}
            
        except Exception as e:
            _logger.error(f"Error in get_catalog_stats: {str(e)}")
            return {'status': 'error', 'message': str(e)}