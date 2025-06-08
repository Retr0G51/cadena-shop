"""
API de pedidos para PedidosSaaS
Gestión completa de pedidos vía API
"""
from flask import jsonify, request
from decimal import Decimal
from datetime import datetime, timedelta
from app.api import bp
from app.api.auth import token_required
from app.models import Order, OrderItem, Product
from app.models.customer import Customer
from app.models.inventory import StockItem, InventoryMovement
from app.extensions import db

@bp.route('/orders', methods=['GET'])
@token_required
def get_orders():
    """
    Obtiene lista de pedidos con paginación y filtros
    
    Query params:
        - page: Número de página
        - per_page: Items por página
        - status: Filtrar por estado
        - date_from: Fecha inicial (YYYY-MM-DD)
        - date_to: Fecha final (YYYY-MM-DD)
        - customer_phone: Filtrar por teléfono
    
    Returns:
        Lista paginada de pedidos
    """
    user = request.current_api_user
    
    # Query base
    query = Order.query.filter_by(user_id=user.id)
    
    # Filtros
    if request.args.get('status'):
        query = query.filter_by(status=request.args.get('status'))
    
    if request.args.get('customer_phone'):
        query = query.filter_by(customer_phone=request.args.get('customer_phone'))
    
    if request.args.get('date_from'):
        date_from = datetime.strptime(request.args.get('date_from'), '%Y-%m-%d')
        query = query.filter(Order.created_at >= date_from)
    
    if request.args.get('date_to'):
        date_to = datetime.strptime(request.args.get('date_to'), '%Y-%m-%d')
        date_to = date_to.replace(hour=23, minute=59, second=59)
        query = query.filter(Order.created_at <= date_to)
    
    # Ordenar por fecha descendente
    query = query.order_by(Order.created_at.desc())
    
    # Paginación
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Serializar
    orders = []
    for order in paginated.items:
        order_data = order.to_dict()
        order_data['items'] = [item.to_dict() for item in order.items]
        orders.append(order_data)
    
    return jsonify({
        'success': True,
        'data': orders,
        'pagination': {
            'page': paginated.page,
            'per_page': paginated.per_page,
            'total': paginated.total,
            'pages': paginated.pages,
            'has_prev': paginated.has_prev,
            'has_next': paginated.has_next
        }
    })

@bp.route('/orders/<int:order_id>', methods=['GET'])
@token_required
def get_order(order_id):
    """
    Obtiene detalles de un pedido específico
    
    Args:
        order_id: ID del pedido
    
    Returns:
        Información completa del pedido
    """
    user = request.current_api_user
    
    order = Order.query.filter_by(
        id=order_id,
        user_id=user.id
    ).first()
    
    if not order:
        return jsonify({
            'success': False,
            'message': 'Order not found'
        }), 404
    
    order_data = order.to_dict()
    order_data['items'] = [item.to_dict() for item in order.items]
    
    # Incluir información del cliente si existe
    if order.customer_id:
        customer = Customer.query.get(order.customer_id)
        if customer:
            order_data['customer'] = {
                'id': customer.id,
                'name': customer.name,
                'email': customer.email,
                'phone': customer.phone,
                'segment': customer.segment
            }
    
    return jsonify({
        'success': True,
        'data': order_data
    })

@bp.route('/orders', methods=['POST'])
@token_required
def create_order():
    """
    Crea un nuevo pedido
    
    Body:
        {
            "customer_name": "John Doe",
            "customer_phone": "+521234567890",
            "customer_email": "john@example.com",
            "delivery_address": "123 Main St",
            "delivery_method": "delivery",
            "payment_method": "cash",
            "notes": "Ring doorbell",
            "items": [
                {
                    "product_id": 1,
                    "quantity": 2,
                    "unit_price": 99.99,
                    "notes": "No onions"
                }
            ]
        }
    
    Returns:
        Pedido creado
    """
    user = request.current_api_user
    data = request.get_json()
    
    # Validaciones básicas
    if not data.get('customer_name'):
        return jsonify({
            'success': False,
            'message': 'Customer name is required'
        }), 400
    
    if not data.get('customer_phone'):
        return jsonify({
            'success': False,
            'message': 'Customer phone is required'
        }), 400
    
    if not data.get('items') or len(data['items']) == 0:
        return jsonify({
            'success': False,
            'message': 'At least one item is required'
        }), 400
    
    # Buscar o crear cliente
    customer = None
    if data.get('customer_phone'):
        customer = Customer.query.filter_by(
            user_id=user.id,
            phone=data['customer_phone']
        ).first()
        
        if not customer:
            customer = Customer(
                user_id=user.id,
                name=data['customer_name'],
                phone=data['customer_phone'],
                email=data.get('customer_email'),
                address=data.get('delivery_address')
            )
            db.session.add(customer)
            db.session.flush()
    
    # Crear pedido
    order = Order(
        user_id=user.id,
        customer_id=customer.id if customer else None,
        customer_name=data['customer_name'],
        customer_phone=data['customer_phone'],
        delivery_address=data.get('delivery_address', ''),
        delivery_method=data.get('delivery_method', 'pickup'),
        payment_method=data.get('payment_method', 'cash'),
        notes=data.get('notes', ''),
        status='pending'
    )
    
    db.session.add(order)
    db.session.flush()
    
    # Agregar items
    total = Decimal('0')
    for item_data in data['items']:
        # Verificar producto
        product = Product.query.filter_by(
            id=item_data['product_id'],
            user_id=user.id
        ).first()
        
        if not product:
            db.session.rollback()
            return jsonify({
                'success': False,
                'message': f'Product {item_data["product_id"]} not found'
            }), 400
        
        # Usar precio del producto o el proporcionado
        unit_price = Decimal(str(item_data.get('unit_price', product.price)))
        quantity = Decimal(str(item_data['quantity']))
        
        # Verificar stock si es necesario
        if product.track_stock:
            # Obtener stock del almacén principal
            from app.models.inventory import Warehouse
            warehouse = Warehouse.query.filter_by(
                user_id=user.id,
                is_default=True
            ).first()
            
            if warehouse:
                stock_item = StockItem.query.filter_by(
                    product_id=product.id,
                    warehouse_id=warehouse.id
                ).first()
                
                if not stock_item or stock_item.available_quantity < quantity:
                    db.session.rollback()
                    return jsonify({
                        'success': False,
                        'message': f'Insufficient stock for product {product.name}'
                    }), 400
                
                # Reservar stock
                stock_item.reserve(quantity)
        
        # Crear item del pedido
        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=quantity,
            unit_price=unit_price,
            subtotal=quantity * unit_price,
            notes=item_data.get('notes', '')
        )
        
        db.session.add(order_item)
        total += order_item.subtotal
    
    # Actualizar total del pedido
    order.total = total
    
    # Generar número de orden
    if not order.order_number:
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        order.order_number = f"ORD-{timestamp}-{order.id}"
    
    db.session.commit()
    
    # Preparar respuesta
    order_data = order.to_dict()
    order_data['items'] = [item.to_dict() for item in order.items]
    
    return jsonify({
        'success': True,
        'message': 'Order created successfully',
        'data': order_data
    }), 201

@bp.route('/orders/<int:order_id>', methods=['PUT'])
@token_required
def update_order(order_id):
    """
    Actualiza un pedido existente
    
    Args:
        order_id: ID del pedido
    
    Body:
        Campos a actualizar (status, payment_method, notes, etc.)
    
    Returns:
        Pedido actualizado
    """
    user = request.current_api_user
    data = request.get_json()
    
    order = Order.query.filter_by(
        id=order_id,
        user_id=user.id
    ).first()
    
    if not order:
        return jsonify({
            'success': False,
            'message': 'Order not found'
        }), 404
    
    # Campos actualizables
    updateable_fields = [
        'status', 'payment_method', 'delivery_method',
        'delivery_address', 'notes'
    ]
    
    old_status = order.status
    
    for field in updateable_fields:
        if field in data:
            setattr(order, field, data[field])
    
    # Si el estado cambió, manejar lógica adicional
    if 'status' in data and data['status'] != old_status:
        # Si se confirma el pedido
        if data['status'] == 'confirmed' and old_status == 'pending':
            order.confirmed_at = datetime.utcnow()
        
        # Si se completa el pedido
        elif data['status'] == 'delivered':
            order.delivered_at = datetime.utcnow()
            
            # Liberar stock reservado y crear movimiento
            for item in order.items:
                if item.product.track_stock:
                    from app.models.inventory import Warehouse
                    warehouse = Warehouse.query.filter_by(
                        user_id=user.id,
                        is_default=True
                    ).first()
                    
                    if warehouse:
                        stock_item = StockItem.query.filter_by(
                            product_id=item.product_id,
                            warehouse_id=warehouse.id
                        ).first()
                        
                        if stock_item:
                            # Liberar reserva
                            stock_item.release_reservation(item.quantity)
                            
                            # Crear movimiento de salida
                            movement = InventoryMovement(
                                user_id=user.id,
                                product_id=item.product_id,
                                warehouse_id=warehouse.id,
                                movement_type='out',
                                reference_type='order',
                                reference_id=order.id,
                                quantity=item.quantity,
                                reason=f'Venta - Pedido {order.order_number}'
                            )
                            movement.apply_movement()
                            db.session.add(movement)
            
            # Actualizar métricas del cliente
            if order.customer_id:
                customer = Customer.query.get(order.customer_id)
                if customer:
                    customer.update_metrics()
        
        # Si se cancela el pedido
        elif data['status'] == 'cancelled':
            order.cancelled_at = datetime.utcnow()
            
            # Liberar stock reservado
            for item in order.items:
                if item.product.track_stock:
                    from app.models.inventory import Warehouse
                    warehouse = Warehouse.query.filter_by(
                        user_id=user.id,
                        is_default=True
                    ).first()
                    
                    if warehouse:
                        stock_item = StockItem.query.filter_by(
                            product_id=item.product_id,
                            warehouse_id=warehouse.id
                        ).first()
                        
                        if stock_item:
                            stock_item.release_reservation(item.quantity)
    
    order.updated_at = datetime.utcnow()
    db.session.commit()
    
    # Preparar respuesta
    order_data = order.to_dict()
    order_data['items'] = [item.to_dict() for item in order.items]
    
    return jsonify({
        'success': True,
        'message': 'Order updated successfully',
        'data': order_data
    })

@bp.route('/orders/<int:order_id>', methods=['DELETE'])
@token_required
def cancel_order(order_id):
    """
    Cancela un pedido
    
    Args:
        order_id: ID del pedido
    
    Returns:
        Confirmación de cancelación
    """
    user = request.current_api_user
    
    order = Order.query.filter_by(
        id=order_id,
        user_id=user.id
    ).first()
    
    if not order:
        return jsonify({
            'success': False,
            'message': 'Order not found'
        }), 404
    
    if order.status in ['delivered', 'cancelled']:
        return jsonify({
            'success': False,
            'message': f'Cannot cancel order with status: {order.status}'
        }), 400
    
    # Cambiar estado a cancelado
    order.status = 'cancelled'
    order.cancelled_at = datetime.utcnow()
    
    # Liberar stock reservado
    for item in order.items:
        if item.product.track_stock:
            from app.models.inventory import Warehouse
            warehouse = Warehouse.query.filter_by(
                user_id=user.id,
                is_default=True
            ).first()
            
            if warehouse:
                stock_item = StockItem.query.filter_by(
                    product_id=item.product_id,
                    warehouse_id=warehouse.id
                ).first()
                
                if stock_item:
                    stock_item.release_reservation(item.quantity)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Order cancelled successfully'
    })

@bp.route('/orders/stats', methods=['GET'])
@token_required
def get_order_stats():
    """
    Obtiene estadísticas de pedidos
    
    Query params:
        - period: today, week, month, year
        - date_from: Fecha inicial personalizada
        - date_to: Fecha final personalizada
    
    Returns:
        Estadísticas de pedidos
    """
    user = request.current_api_user
    
    # Determinar período
    period = request.args.get('period', 'today')
    now = datetime.utcnow()
    
    if period == 'today':
        date_from = now.replace(hour=0, minute=0, second=0, microsecond=0)
        date_to = now
    elif period == 'week':
        date_from = now - timedelta(days=7)
        date_to = now
    elif period == 'month':
        date_from = now - timedelta(days=30)
        date_to = now
    elif period == 'year':
        date_from = now - timedelta(days=365)
        date_to = now
    else:
        # Período personalizado
        try:
            date_from = datetime.strptime(request.args.get('date_from'), '%Y-%m-%d')
            date_to = datetime.strptime(request.args.get('date_to'), '%Y-%m-%d')
        except:
            date_from = now - timedelta(days=30)
            date_to = now
    
    # Obtener estadísticas
    orders = Order.query.filter(
        Order.user_id == user.id,
        Order.created_at >= date_from,
        Order.created_at <= date_to
    ).all()
    
    # Calcular métricas
    total_orders = len(orders)
    completed_orders = len([o for o in orders if o.status == 'delivered'])
    cancelled_orders = len([o for o in orders if o.status == 'cancelled'])
    pending_orders = len([o for o in orders if o.status == 'pending'])
    
    total_revenue = sum(o.total for o in orders if o.status == 'delivered')
    avg_order_value = total_revenue / completed_orders if completed_orders > 0 else 0
    
    # Productos más vendidos
    from sqlalchemy import func
    top_products = db.session.query(
        Product.id,
        Product.name,
        func.sum(OrderItem.quantity).label('quantity_sold'),
        func.sum(OrderItem.subtotal).label('revenue')
    ).join(
        OrderItem
    ).join(
        Order
    ).filter(
        Order.user_id == user.id,
        Order.created_at >= date_from,
        Order.created_at <= date_to,
        Order.status == 'delivered'
    ).group_by(
        Product.id, Product.name
    ).order_by(
        func.sum(OrderItem.quantity).desc()
    ).limit(5).all()
    
    return jsonify({
        'success': True,
        'data': {
            'period': {
                'from': date_from.isoformat(),
                'to': date_to.isoformat()
            },
            'summary': {
                'total_orders': total_orders,
                'completed_orders': completed_orders,
                'cancelled_orders': cancelled_orders,
                'pending_orders': pending_orders,
                'completion_rate': (completed_orders / total_orders * 100) if total_orders > 0 else 0
            },
            'revenue': {
                'total': float(total_revenue),
                'average_order_value': float(avg_order_value)
            },
            'top_products': [
                {
                    'id': p.id,
                    'name': p.name,
                    'quantity_sold': int(p.quantity_sold),
                    'revenue': float(p.revenue)
                }
                for p in top_products
            ]
        }
    })

# Namespace para documentación
api_orders = {
    'name': 'Orders',
    'description': 'Order management endpoints',
    'endpoints': [
        {
            'path': '/orders',
            'method': 'GET',
            'description': 'List orders with filters',
            'auth_required': True
        },
        {
            'path': '/orders/{order_id}',
            'method': 'GET',
            'description': 'Get order details',
            'auth_required': True
        },
        {
            'path': '/orders',
            'method': 'POST',
            'description': 'Create new order',
            'auth_required': True
        },
        {
            'path': '/orders/{order_id}',
            'method': 'PUT',
            'description': 'Update order',
            'auth_required': True
        },
        {
            'path': '/orders/{order_id}',
            'method': 'DELETE',
            'description': 'Cancel order',
            'auth_required': True
        },
        {
            'path': '/orders/stats',
            'method': 'GET',
            'description': 'Get order statistics',
            'auth_required': True
        }
    ]
}
