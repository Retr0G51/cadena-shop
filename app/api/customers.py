"""
API de clientes para PedidosSaaS
Gestión completa de clientes y CRM vía API
"""
from flask import jsonify, request
from datetime import datetime, timedelta
from decimal import Decimal
from app.api import bp
from app.api.auth import token_required
from app.models import Order
from app.models.customer import Customer, CustomerGroup, CustomerInteraction, MarketingCampaign
from app.extensions import db

@bp.route('/customers', methods=['GET'])
@token_required
def get_customers():
    """
    Obtiene lista de clientes con paginación y filtros
    
    Query params:
        - page: Número de página
        - per_page: Items por página
        - search: Búsqueda por nombre, email o teléfono
        - segment: Filtrar por segmento (vip, premium, regular, new)
        - tags: Filtrar por tags (separados por coma)
        - active: Solo clientes activos (true/false)
    
    Returns:
        Lista paginada de clientes
    """
    user = request.current_api_user
    
    # Query base
    query = Customer.query.filter_by(user_id=user.id)
    
    # Filtros
    if request.args.get('search'):
        search = f"%{request.args.get('search')}%"
        query = query.filter(
            db.or_(
                Customer.name.ilike(search),
                Customer.email.ilike(search),
                Customer.phone.ilike(search),
                Customer.company_name.ilike(search)
            )
        )
    
    if request.args.get('segment'):
        query = query.filter_by(segment=request.args.get('segment'))
    
    if request.args.get('tags'):
        tags = request.args.get('tags').split(',')
        for tag in tags:
            query = query.filter(Customer.tags.contains([tag.strip()]))
    
    if request.args.get('active') is not None:
        is_active = request.args.get('active').lower() == 'true'
        query = query.filter_by(is_active=is_active)
    
    # Ordenamiento
    sort_field = request.args.get('sort', 'created_at')
    sort_order = request.args.get('order', 'desc')
    
    if sort_field in ['name', 'created_at', 'total_spent', 'last_order_date']:
        if sort_order == 'asc':
            query = query.order_by(getattr(Customer, sort_field).asc())
        else:
            query = query.order_by(getattr(Customer, sort_field).desc())
    
    # Paginación
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Serializar
    customers = []
    for customer in paginated.items:
        customer_data = customer.to_dict()
        
        # Agregar estadísticas adicionales
        customer_data['stats'] = {
            'lifetime_value': float(customer.lifetime_value),
            'days_since_last_order': customer.days_since_last_order,
            'is_at_risk': customer.is_at_risk,
            'is_vip': customer.is_vip
        }
        
        customers.append(customer_data)
    
    return jsonify({
        'success': True,
        'data': customers,
        'pagination': {
            'page': paginated.page,
            'per_page': paginated.per_page,
            'total': paginated.total,
            'pages': paginated.pages,
            'has_prev': paginated.has_prev,
            'has_next': paginated.has_next
        }
    })

@bp.route('/customers/<int:customer_id>', methods=['GET'])
@token_required
def get_customer(customer_id):
    """
    Obtiene detalles de un cliente específico
    
    Args:
        customer_id: ID del cliente
    
    Returns:
        Información completa del cliente
    """
    user = request.current_api_user
    
    customer = Customer.query.filter_by(
        id=customer_id,
        user_id=user.id
    ).first()
    
    if not customer:
        return jsonify({
            'success': False,
            'message': 'Customer not found'
        }), 404
    
    # Actualizar métricas
    customer.update_metrics()
    db.session.commit()
    
    customer_data = customer.to_dict()
    
    # Agregar información adicional
    customer_data['stats'] = {
        'lifetime_value': float(customer.lifetime_value),
        'days_since_last_order': customer.days_since_last_order,
        'is_at_risk': customer.is_at_risk,
        'is_vip': customer.is_vip
    }
    
    # Grupos
    customer_data['groups'] = [
        {
            'id': group.id,
            'name': group.name,
            'discount_rate': float(group.discount_rate)
        }
        for group in customer.groups
    ]
    
    # Últimos pedidos
    recent_orders = Order.query.filter_by(
        user_id=user.id,
        customer_phone=customer.phone
    ).order_by(Order.created_at.desc()).limit(5).all()
    
    customer_data['recent_orders'] = [
        {
            'id': order.id,
            'order_number': order.order_number,
            'total': float(order.total),
            'status': order.status,
            'created_at': order.created_at.isoformat()
        }
        for order in recent_orders
    ]
    
    # Últimas interacciones
    recent_interactions = customer.interactions.order_by(
        CustomerInteraction.created_at.desc()
    ).limit(5).all()
    
    customer_data['recent_interactions'] = [
        {
            'id': interaction.id,
            'type': interaction.interaction_type,
            'subject': interaction.subject,
            'created_at': interaction.created_at.isoformat()
        }
        for interaction in recent_interactions
    ]
    
    return jsonify({
        'success': True,
        'data': customer_data
    })

@bp.route('/customers', methods=['POST'])
@token_required
def create_customer():
    """
    Crea un nuevo cliente
    
    Body:
        {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "+1234567890",
            "address": "123 Main St",
            "city": "New York",
            "postal_code": "10001",
            "customer_type": "individual",
            "company_name": "ACME Inc",
            "tax_id": "123456789",
            "accepts_marketing": true,
            "tags": ["vip", "wholesale"],
            "notes": "Important customer"
        }
    
    Returns:
        Cliente creado
    """
    user = request.current_api_user
    data = request.get_json()
    
    # Validaciones
    if not data.get('name'):
        return jsonify({
            'success': False,
            'message': 'Customer name is required'
        }), 400
    
    if not data.get('phone'):
        return jsonify({
            'success': False,
            'message': 'Customer phone is required'
        }), 400
    
    # Verificar si el cliente ya existe
    existing = Customer.query.filter_by(
        user_id=user.id,
        phone=data['phone']
    ).first()
    
    if existing:
        return jsonify({
            'success': False,
            'message': 'Customer with this phone already exists'
        }), 400
    
    # Crear cliente
    customer = Customer(
        user_id=user.id,
        name=data['name'],
        email=data.get('email'),
        phone=data['phone'],
        alternative_phone=data.get('alternative_phone'),
        address=data.get('address'),
        city=data.get('city'),
        state=data.get('state'),
        postal_code=data.get('postal_code'),
        country=data.get('country', 'MX'),
        customer_type=data.get('customer_type', 'individual'),
        company_name=data.get('company_name'),
        tax_id=data.get('tax_id'),
        accepts_marketing=data.get('accepts_marketing', True),
        tags=data.get('tags', []),
        notes=data.get('notes'),
        preferred_payment_method=data.get('preferred_payment_method'),
        preferred_contact_method=data.get('preferred_contact_method', 'phone'),
        language=data.get('language', 'es')
    )
    
    # Establecer segmento inicial
    customer.segment = 'new'
    
    # Si se proporciona crédito inicial
    if data.get('credit_limit'):
        customer.credit_limit = Decimal(str(data['credit_limit']))
    
    db.session.add(customer)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Customer created successfully',
        'data': customer.to_dict()
    }), 201

@bp.route('/customers/<int:customer_id>', methods=['PUT'])
@token_required
def update_customer(customer_id):
    """
    Actualiza un cliente existente
    
    Args:
        customer_id: ID del cliente
    
    Body:
        Campos a actualizar
    
    Returns:
        Cliente actualizado
    """
    user = request.current_api_user
    data = request.get_json()
    
    customer = Customer.query.filter_by(
        id=customer_id,
        user_id=user.id
    ).first()
    
    if not customer:
        return jsonify({
            'success': False,
            'message': 'Customer not found'
        }), 404
    
    # Campos actualizables
    updateable_fields = [
        'name', 'email', 'alternative_phone', 'address', 'city', 'state',
        'postal_code', 'country', 'customer_type', 'company_name', 'tax_id',
        'accepts_marketing', 'tags', 'notes', 'internal_notes',
        'preferred_payment_method', 'preferred_contact_method', 'language',
        'credit_limit', 'is_active', 'is_blacklisted', 'blacklist_reason'
    ]
    
    for field in updateable_fields:
        if field in data:
            if field == 'credit_limit' and data[field] is not None:
                setattr(customer, field, Decimal(str(data[field])))
            else:
                setattr(customer, field, data[field])
    
    # Verificar teléfono único si se está actualizando
    if 'phone' in data and data['phone'] != customer.phone:
        existing = Customer.query.filter_by(
            user_id=user.id,
            phone=data['phone']
        ).filter(Customer.id != customer_id).first()
        
        if existing:
            return jsonify({
                'success': False,
                'message': 'Phone number already in use'
            }), 400
        
        customer.phone = data['phone']
    
    # Si se actualiza marketing consent
    if 'accepts_marketing' in data:
        if data['accepts_marketing'] and not customer.accepts_marketing:
            customer.marketing_consent_date = datetime.utcnow()
        elif not data['accepts_marketing'] and customer.accepts_marketing:
            customer.unsubscribed_at = datetime.utcnow()
    
    customer.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Customer updated successfully',
        'data': customer.to_dict()
    })

@bp.route('/customers/<int:customer_id>', methods=['DELETE'])
@token_required
def delete_customer(customer_id):
    """
    Elimina un cliente (soft delete)
    
    Args:
        customer_id: ID del cliente
    
    Returns:
        Confirmación de eliminación
    """
    user = request.current_api_user
    
    customer = Customer.query.filter_by(
        id=customer_id,
        user_id=user.id
    ).first()
    
    if not customer:
        return jsonify({
            'success': False,
            'message': 'Customer not found'
        }), 404
    
    # Verificar si tiene pedidos
    has_orders = Order.query.filter_by(
        user_id=user.id,
        customer_phone=customer.phone
    ).first()
    
    if has_orders:
        # Soft delete
        customer.is_active = False
        customer.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Customer deactivated (has orders)'
        })
    else:
        # Hard delete si no tiene historial
        db.session.delete(customer)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Customer deleted successfully'
        })

@bp.route('/customers/<int:customer_id>/interactions', methods=['GET'])
@token_required
def get_customer_interactions(customer_id):
    """
    Obtiene las interacciones de un cliente
    
    Args:
        customer_id: ID del cliente
    
    Returns:
        Lista de interacciones
    """
    user = request.current_api_user
    
    customer = Customer.query.filter_by(
        id=customer_id,
        user_id=user.id
    ).first()
    
    if not customer:
        return jsonify({
            'success': False,
            'message': 'Customer not found'
        }), 404
    
    interactions = customer.interactions.order_by(
        CustomerInteraction.created_at.desc()
    ).all()
    
    return jsonify({
        'success': True,
        'data': [interaction.to_dict() for interaction in interactions]
    })

@bp.route('/customers/<int:customer_id>/interactions', methods=['POST'])
@token_required
def create_customer_interaction(customer_id):
    """
    Crea una nueva interacción con el cliente
    
    Args:
        customer_id: ID del cliente
    
    Body:
        {
            "interaction_type": "call",
            "channel": "phone",
            "subject": "Follow up",
            "content": "Discussed new products",
            "requires_followup": true,
            "followup_date": "2024-01-15"
        }
    
    Returns:
        Interacción creada
    """
    user = request.current_api_user
    data = request.get_json()
    
    customer = Customer.query.filter_by(
        id=customer_id,
        user_id=user.id
    ).first()
    
    if not customer:
        return jsonify({
            'success': False,
            'message': 'Customer not found'
        }), 404
    
    interaction = CustomerInteraction(
        customer_id=customer.id,
        user_id=user.id,
        created_by=user.id,
        interaction_type=data.get('interaction_type', 'note'),
        channel=data.get('channel'),
        subject=data.get('subject', ''),
        content=data.get('content', ''),
        requires_followup=data.get('requires_followup', False)
    )
    
    if interaction.requires_followup and data.get('followup_date'):
        try:
            interaction.followup_date = datetime.strptime(
                data['followup_date'], '%Y-%m-%d'
            )
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Invalid followup_date format. Use YYYY-MM-DD'
            }), 400
    
    db.session.add(interaction)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Interaction created successfully',
        'data': interaction.to_dict()
    }), 201

@bp.route('/customers/groups', methods=['GET'])
@token_required
def get_customer_groups():
    """
    Obtiene los grupos de clientes
    
    Returns:
        Lista de grupos
    """
    user = request.current_api_user
    
    groups = CustomerGroup.query.filter_by(
        user_id=user.id,
        is_active=True
    ).all()
    
    return jsonify({
        'success': True,
        'data': [
            {
                'id': group.id,
                'name': group.name,
                'description': group.description,
                'type': group.group_type,
                'discount_rate': float(group.discount_rate),
                'member_count': len(group.customers)
            }
            for group in groups
        ]
    })

@bp.route('/customers/segments', methods=['GET'])
@token_required
def get_customer_segments():
    """
    Obtiene estadísticas de segmentos de clientes
    
    Returns:
        Distribución de clientes por segmento
    """
    user = request.current_api_user
    
    segments = db.session.query(
        Customer.segment,
        db.func.count(Customer.id).label('count'),
        db.func.avg(Customer.total_spent).label('avg_spent'),
        db.func.sum(Customer.total_spent).label('total_spent')
    ).filter(
        Customer.user_id == user.id,
        Customer.is_active == True
    ).group_by(Customer.segment).all()
    
    return jsonify({
        'success': True,
        'data': [
            {
                'segment': segment,
                'count': count,
                'avg_spent': float(avg_spent or 0),
                'total_spent': float(total_spent or 0)
            }
            for segment, count, avg_spent, total_spent in segments
        ]
    })

@bp.route('/customers/export', methods=['GET'])
@token_required
def export_customers():
    """
    Exporta clientes en formato CSV o JSON
    
    Query params:
        - format: csv o json (default: json)
        - segment: Filtrar por segmento
        - active: Solo activos
    
    Returns:
        Archivo de exportación
    """
    user = request.current_api_user
    format_type = request.args.get('format', 'json')
    
    # Query base
    query = Customer.query.filter_by(user_id=user.id)
    
    # Aplicar filtros
    if request.args.get('segment'):
        query = query.filter_by(segment=request.args.get('segment'))
    
    if request.args.get('active') == 'true':
        query = query.filter_by(is_active=True)
    
    customers = query.all()
    
    if format_type == 'csv':
        # Exportar como CSV
        from app.utils.helpers import export_to_csv
        
        data = []
        for customer in customers:
            data.append({
                'ID': customer.id,
                'Nombre': customer.name,
                'Email': customer.email,
                'Teléfono': customer.phone,
                'Empresa': customer.company_name or '',
                'NIF': customer.tax_id or '',
                'Segmento': customer.segment,
                'Total Gastado': float(customer.total_spent),
                'Pedidos': customer.total_orders,
                'Última Compra': customer.last_order_date.strftime('%Y-%m-%d') if customer.last_order_date else '',
                'Marketing': 'Sí' if customer.accepts_marketing else 'No'
            })
        
        csv_file = export_to_csv(data, 'customers.csv')
        
        from flask import send_file
        return send_file(
            csv_file,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'customers_{datetime.utcnow().strftime("%Y%m%d")}.csv'
        )
    
    else:
        # Exportar como JSON
        return jsonify({
            'success': True,
            'data': [customer.to_dict() for customer in customers],
            'count': len(customers),
            'exported_at': datetime.utcnow().isoformat()
        })

# Namespace para documentación
api_customers = {
    'name': 'Customers',
    'description': 'Customer management and CRM endpoints',
    'endpoints': [
        {
            'path': '/customers',
            'method': 'GET',
            'description': 'List customers with filters',
            'auth_required': True
        },
        {
            'path': '/customers/{customer_id}',
            'method': 'GET',
            'description': 'Get customer details',
            'auth_required': True
        },
        {
            'path': '/customers',
            'method': 'POST',
            'description': 'Create new customer',
            'auth_required': True
        },
        {
            'path': '/customers/{customer_id}',
            'method': 'PUT',
            'description': 'Update customer',
            'auth_required': True
        },
        {
            'path': '/customers/{customer_id}',
            'method': 'DELETE',
            'description': 'Delete customer',
            'auth_required': True
        },
        {
            'path': '/customers/{customer_id}/interactions',
            'method': 'GET',
            'description': 'Get customer interactions',
            'auth_required': True
        },
        {
            'path': '/customers/{customer_id}/interactions',
            'method': 'POST',
            'description': 'Create customer interaction',
            'auth_required': True
        },
        {
            'path': '/customers/groups',
            'method': 'GET',
            'description': 'Get customer groups',
            'auth_required': True
        },
        {
            'path': '/customers/segments',
            'method': 'GET',
            'description': 'Get customer segments stats',
            'auth_required': True
        },
        {
            'path': '/customers/export',
            'method': 'GET',
            'description': 'Export customers',
            'auth_required': True
        }
    ]
}
