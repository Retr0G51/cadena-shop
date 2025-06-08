"""
API de productos para PedidosSaaS
CRUD completo y operaciones avanzadas
"""
from flask import jsonify, request
from decimal import Decimal
from app.api import bp
from app.api.auth import token_required
from app.models import Product
from app.models.inventory import StockItem, Warehouse
from app.extensions import db
from app.utils import paginate_query

@bp.route('/products', methods=['GET'])
@token_required
def get_products():
    """
    Obtiene lista de productos con paginación y filtros
    
    Query params:
        - page: Número de página (default: 1)
        - per_page: Items por página (default: 20, max: 100)
        - active: Filtrar por activos (true/false)
        - category: Filtrar por categoría
        - search: Búsqueda por nombre
        - sort: Campo de ordenamiento (name, price, created_at)
        - order: Orden (asc, desc)
    
    Returns:
        {
            "success": true,
            "data": [...],
            "pagination": {
                "page": 1,
                "per_page": 20,
                "total": 100,
                "pages": 5
            }
        }
    """
    user = request.current_api_user
    
    # Query base
    query = Product.query.filter_by(user_id=user.id)
    
    # Filtros
    if request.args.get('active') is not None:
        is_active = request.args.get('active').lower() == 'true'
        query = query.filter_by(is_active=is_active)
    
    if request.args.get('category'):
        query = query.filter_by(category=request.args.get('category'))
    
    if request.args.get('search'):
        search = f"%{request.args.get('search')}%"
        query = query.filter(Product.name.ilike(search))
    
    # Ordenamiento
    sort_field = request.args.get('sort', 'created_at')
    sort_order = request.args.get('order', 'desc')
    
    if sort_field in ['name', 'price', 'created_at', 'stock']:
        if sort_order == 'asc':
            query = query.order_by(getattr(Product, sort_field).asc())
        else:
            query = query.order_by(getattr(Product, sort_field).desc())
    
    # Paginación
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Serializar productos
    products = []
    for product in paginated.items:
        product_data = product.to_dict()
        
        # Agregar información de stock si está habilitado
        if product.track_stock:
            stock_items = StockItem.query.filter_by(product_id=product.id).all()
            product_data['stock_info'] = {
                'total_stock': sum(item.quantity for item in stock_items),
                'available_stock': sum(item.available_quantity for item in stock_items),
                'warehouses': [
                    {
                        'warehouse_id': item.warehouse_id,
                        'warehouse_name': item.warehouse.name,
                        'quantity': float(item.quantity),
                        'available': float(item.available_quantity)
                    }
                    for item in stock_items
                ]
            }
        
        products.append(product_data)
    
    return jsonify({
        'success': True,
        'data': products,
        'pagination': {
            'page': paginated.page,
            'per_page': paginated.per_page,
            'total': paginated.total,
            'pages': paginated.pages,
            'has_prev': paginated.has_prev,
            'has_next': paginated.has_next
        }
    })

@bp.route('/products/<int:product_id>', methods=['GET'])
@token_required
def get_product(product_id):
    """
    Obtiene un producto específico
    
    Args:
        product_id: ID del producto
    
    Returns:
        Información detallada del producto
    """
    user = request.current_api_user
    
    product = Product.query.filter_by(
        id=product_id,
        user_id=user.id
    ).first()
    
    if not product:
        return jsonify({
            'success': False,
            'message': 'Product not found'
        }), 404
    
    product_data = product.to_dict()
    
    # Incluir información adicional
    if product.track_stock:
        stock_items = StockItem.query.filter_by(product_id=product.id).all()
        product_data['stock_info'] = {
            'total_stock': sum(item.quantity for item in stock_items),
            'available_stock': sum(item.available_quantity for item in stock_items),
            'warehouses': [
                {
                    'warehouse_id': item.warehouse_id,
                    'warehouse_name': item.warehouse.name,
                    'quantity': float(item.quantity),
                    'available': float(item.available_quantity),
                    'reserved': float(item.reserved_quantity),
                    'min_stock': float(item.min_stock),
                    'reorder_point': float(item.reorder_point) if item.reorder_point else None
                }
                for item in stock_items
            ]
        }
    
    # Estadísticas de ventas (últimos 30 días)
    from datetime import datetime, timedelta
    from app.models import Order, OrderItem
    
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    sales_stats = db.session.query(
        db.func.count(OrderItem.id).label('order_count'),
        db.func.sum(OrderItem.quantity).label('quantity_sold'),
        db.func.sum(OrderItem.subtotal).label('revenue')
    ).join(
        Order
    ).filter(
        OrderItem.product_id == product.id,
        Order.created_at >= thirty_days_ago,
        Order.status == 'delivered'
    ).first()
    
    product_data['sales_stats'] = {
        'last_30_days': {
            'order_count': sales_stats.order_count or 0,
            'quantity_sold': float(sales_stats.quantity_sold or 0),
            'revenue': float(sales_stats.revenue or 0)
        }
    }
    
    return jsonify({
        'success': True,
        'data': product_data
    })

@bp.route('/products', methods=['POST'])
@token_required
def create_product():
    """
    Crea un nuevo producto
    
    Body:
        {
            "name": "Product Name",
            "description": "Description",
            "price": 99.99,
            "category": "Category",
            "sku": "SKU123",
            "barcode": "1234567890",
            "track_stock": true,
            "is_active": true,
            "initial_stock": {
                "warehouse_id": 1,
                "quantity": 100,
                "min_stock": 10,
                "reorder_point": 20
            }
        }
    
    Returns:
        Producto creado
    """
    user = request.current_api_user
    data = request.get_json()
    
    # Validaciones
    if not data.get('name'):
        return jsonify({
            'success': False,
            'message': 'Product name is required'
        }), 400
    
    if not data.get('price'):
        return jsonify({
            'success': False,
            'message': 'Product price is required'
        }), 400
    
    # Verificar SKU único
    if data.get('sku'):
        existing = Product.query.filter_by(
            user_id=user.id,
            sku=data['sku']
        ).first()
        if existing:
            return jsonify({
                'success': False,
                'message': 'SKU already exists'
            }), 400
    
    # Crear producto
    product = Product(
        user_id=user.id,
        name=data['name'],
        description=data.get('description', ''),
        price=Decimal(str(data['price'])),
        category=data.get('category'),
        sku=data.get('sku'),
        barcode=data.get('barcode'),
        track_stock=data.get('track_stock', False),
        is_active=data.get('is_active', True)
    )
    
    db.session.add(product)
    db.session.flush()
    
    # Crear stock inicial si se proporciona
    if product.track_stock and data.get('initial_stock'):
        stock_data = data['initial_stock']
        
        # Verificar almacén
        warehouse = Warehouse.query.filter_by(
            id=stock_data.get('warehouse_id', 1),
            user_id=user.id
        ).first()
        
        if not warehouse:
            # Usar almacén por defecto
            warehouse = Warehouse.query.filter_by(
                user_id=user.id,
                is_default=True
            ).first()
        
        if warehouse:
            stock_item = StockItem(
                product_id=product.id,
                warehouse_id=warehouse.id,
                quantity=Decimal(str(stock_data.get('quantity', 0))),
                min_stock=Decimal(str(stock_data.get('min_stock', 0))),
                reorder_point=Decimal(str(stock_data.get('reorder_point', 0))) if stock_data.get('reorder_point') else None
            )
            db.session.add(stock_item)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Product created successfully',
        'data': product.to_dict()
    }), 201

@bp.route('/products/<int:product_id>', methods=['PUT'])
@token_required
def update_product(product_id):
    """
    Actualiza un producto existente
    
    Args:
        product_id: ID del producto
    
    Body:
        Campos a actualizar
    
    Returns:
        Producto actualizado
    """
    user = request.current_api_user
    data = request.get_json()
    
    product = Product.query.filter_by(
        id=product_id,
        user_id=user.id
    ).first()
    
    if not product:
        return jsonify({
            'success': False,
            'message': 'Product not found'
        }), 404
    
    # Actualizar campos permitidos
    updateable_fields = [
        'name', 'description', 'price', 'category',
        'sku', 'barcode', 'track_stock', 'is_active'
    ]
    
    for field in updateable_fields:
        if field in data:
            if field == 'price':
                setattr(product, field, Decimal(str(data[field])))
            else:
                setattr(product, field, data[field])
    
    # Verificar SKU único si se está actualizando
    if 'sku' in data and data['sku'] != product.sku:
        existing = Product.query.filter_by(
            user_id=user.id,
            sku=data['sku']
        ).filter(Product.id != product_id).first()
        
        if existing:
            return jsonify({
                'success': False,
                'message': 'SKU already exists'
            }), 400
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Product updated successfully',
        'data': product.to_dict()
    })

@bp.route('/products/<int:product_id>', methods=['DELETE'])
@token_required
def delete_product(product_id):
    """
    Elimina un producto (soft delete)
    
    Args:
        product_id: ID del producto
    
    Returns:
        Confirmación de eliminación
    """
    user = request.current_api_user
    
    product = Product.query.filter_by(
        id=product_id,
        user_id=user.id
    ).first()
    
    if not product:
        return jsonify({
            'success': False,
            'message': 'Product not found'
        }), 404
    
    # Verificar si tiene pedidos asociados
    from app.models import OrderItem
    
    has_orders = OrderItem.query.filter_by(product_id=product_id).first()
    
    if has_orders:
        # Soft delete - solo desactivar
        product.is_active = False
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Product deactivated (has associated orders)'
        })
    else:
        # Hard delete si no tiene pedidos
        db.session.delete(product)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Product deleted successfully'
        })

@bp.route('/products/bulk', methods=['POST'])
@token_required
def bulk_update_products():
    """
    Actualización masiva de productos
    
    Body:
        {
            "product_ids": [1, 2, 3],
            "updates": {
                "category": "New Category",
                "is_active": false
            }
        }
    
    Returns:
        Número de productos actualizados
    """
    user = request.current_api_user
    data = request.get_json()
    
    product_ids = data.get('product_ids', [])
    updates = data.get('updates', {})
    
    if not product_ids or not updates:
        return jsonify({
            'success': False,
            'message': 'product_ids and updates are required'
        }), 400
    
    # Campos permitidos para actualización masiva
    allowed_fields = ['category', 'is_active']
    
    # Filtrar solo campos permitidos
    filtered_updates = {
        k: v for k, v in updates.items() 
        if k in allowed_fields
    }
    
    if not filtered_updates:
        return jsonify({
            'success': False,
            'message': 'No valid fields to update'
        }), 400
    
    # Actualizar productos
    updated = Product.query.filter(
        Product.id.in_(product_ids),
        Product.user_id == user.id
    ).update(filtered_updates, synchronize_session=False)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'{updated} products updated successfully',
        'updated_count': updated
    })

@bp.route('/products/categories', methods=['GET'])
@token_required
def get_categories():
    """
    Obtiene lista de categorías únicas
    
    Returns:
        Lista de categorías disponibles
    """
    user = request.current_api_user
    
    categories = db.session.query(Product.category).filter(
        Product.user_id == user.id,
        Product.category.isnot(None)
    ).distinct().all()
    
    category_list = [cat[0] for cat in categories if cat[0]]
    
    return jsonify({
        'success': True,
        'data': sorted(category_list)
    })

# Namespace para documentación
api_products = {
    'name': 'Products',
    'description': 'Product management endpoints',
    'endpoints': [
        {
            'path': '/products',
            'method': 'GET',
            'description': 'List products with pagination and filters',
            'auth_required': True
        },
        {
            'path': '/products/{product_id}',
            'method': 'GET',
            'description': 'Get product details',
            'auth_required': True
        },
        {
            'path': '/products',
            'method': 'POST',
            'description': 'Create new product',
            'auth_required': True
        },
        {
            'path': '/products/{product_id}',
            'method': 'PUT',
            'description': 'Update product',
            'auth_required': True
        },
        {
            'path': '/products/{product_id}',
            'method': 'DELETE',
            'description': 'Delete product',
            'auth_required': True
        },
        {
            'path': '/products/bulk',
            'method': 'POST',
            'description': 'Bulk update products',
            'auth_required': True
        },
        {
            'path': '/products/categories',
            'method': 'GET',
            'description': 'Get unique categories',
            'auth_required': True
        }
    ]
}
