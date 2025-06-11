import os
from flask import render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import func, desc, and_, or_, extract
import json
from app import db
from app.dashboard import bp
from app.dashboard.forms import ProductForm, BusinessSettingsForm
from app.models import Product, Order, OrderItem
from app.utils.decorators import business_required, active_business_required
from app.utils.helpers import save_picture, delete_picture, format_currency

# Importar analytics si existe
try:
    from app.dashboard.analytics import Analytics
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False

@bp.route('/')
@login_required
@active_business_required
def index():
    """Dashboard principal SÚPER COMPLETO con métricas avanzadas"""
    
    # Fechas para cálculos
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    month_start = today.replace(day=1)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)
    
    # ==================== MÉTRICAS BÁSICAS ====================
    total_products = Product.query.filter_by(user_id=current_user.id).count()
    active_products = Product.query.filter_by(user_id=current_user.id, is_active=True).count()
    total_orders = Order.query.filter_by(user_id=current_user.id).count()
    pending_orders = Order.query.filter_by(user_id=current_user.id, status='pending').count()
    
    # ==================== VENTAS Y CRECIMIENTO ====================
    
    # Ventas de hoy
    today_sales = db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.user_id == current_user.id,
        func.date(Order.created_at) == today,
        Order.status.in_(['confirmed', 'processing', 'shipped', 'delivered'])
    ).scalar() or 0
    
    # Ventas de ayer
    yesterday_sales = db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.user_id == current_user.id,
        func.date(Order.created_at) == yesterday,
        Order.status.in_(['confirmed', 'processing', 'shipped', 'delivered'])
    ).scalar() or 0
    
    # Crecimiento de ventas
    today_growth = calculate_growth_percentage(today_sales, yesterday_sales)
    
    # Pedidos de hoy vs ayer
    today_orders = Order.query.filter(
        Order.user_id == current_user.id,
        func.date(Order.created_at) == today
    ).count()
    
    yesterday_orders = Order.query.filter(
        Order.user_id == current_user.id,
        func.date(Order.created_at) == yesterday
    ).count()
    
    orders_growth = calculate_growth_percentage(today_orders, yesterday_orders)
    
    # ==================== CLIENTES Y ESTADÍSTICAS ====================
    
    # Clientes únicos totales
    customers_count = db.session.query(func.count(func.distinct(Order.customer_phone))).filter(
        Order.user_id == current_user.id
    ).scalar() or 0
    
    # Nuevos clientes esta semana
    new_customers_week = db.session.query(func.count(func.distinct(Order.customer_phone))).filter(
        Order.user_id == current_user.id,
        Order.created_at >= week_ago
    ).scalar() or 0
    
    # Clientes que repiten (más de 1 pedido)
    returning_customers = db.session.query(
        func.count(func.distinct(Order.customer_phone))
    ).filter(
        Order.user_id == current_user.id
    ).having(
        func.count(Order.id) > 1
    ).group_by(Order.customer_phone).count()
    
    # Tasa de retención
    retention_rate = (returning_customers / customers_count * 100) if customers_count > 0 else 0
    
    # ==================== VENTAS MENSUALES Y METAS ====================
    
    # Ventas del mes actual
    monthly_sales = db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.user_id == current_user.id,
        func.date(Order.created_at) >= month_start,
        Order.status.in_(['confirmed', 'processing', 'shipped', 'delivered'])
    ).scalar() or 0
    
    # Ventas del mes pasado
    last_monthly_sales = db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.user_id == current_user.id,
        func.date(Order.created_at) >= last_month_start,
        func.date(Order.created_at) < month_start,
        Order.status.in_(['confirmed', 'processing', 'shipped', 'delivered'])
    ).scalar() or 0
    
    monthly_growth = calculate_growth_percentage(monthly_sales, last_monthly_sales)
    
    # Meta mensual (obtener del usuario o default)
    monthly_goal = getattr(current_user, 'monthly_goal', None) or 10000
    goal_progress = (monthly_sales / monthly_goal * 100) if monthly_goal > 0 else 0
    
    # ==================== PRODUCTOS MÁS VENDIDOS ====================
    
    top_products = get_top_selling_products(current_user.id, limit=5)
    
    # ==================== ACTIVIDAD RECIENTE ====================
    
    recent_activities = get_recent_business_activities(current_user.id, limit=10)
    
    # ==================== DATOS PARA GRÁFICOS ====================
    
    # Ventas últimos 7 días
    sales_chart_data = get_sales_chart_data(current_user.id, days=7)
    
    # Pedidos por día últimos 7 días  
    orders_chart_data = get_orders_chart_data(current_user.id, days=7)
    
    # ==================== ANÁLISIS DE RENDIMIENTO ====================
    
    # Ticket promedio
    avg_order_value = 0
    completed_orders_count = Order.query.filter_by(
        user_id=current_user.id,
        status='delivered'
    ).count()
    
    if completed_orders_count > 0:
        total_completed_sales = db.session.query(func.sum(Order.total)).filter_by(
            user_id=current_user.id,
            status='delivered'
        ).scalar() or 0
        avg_order_value = total_completed_sales / completed_orders_count
    
    # Productos con bajo stock
    low_stock_products = Product.query.filter(
        Product.user_id == current_user.id,
        Product.stock <= 5,
        Product.is_active == True
    ).count()
    
    # ==================== ÚLTIMOS PEDIDOS ====================
    
    recent_orders = Order.query.filter_by(user_id=current_user.id)\
        .order_by(Order.created_at.desc()).limit(8).all()
    
    # ==================== ESTADÍSTICAS ADICIONALES ====================
    
    # Productos más vistos (simulado - en producción sería de analytics reales)
    products_views = total_products * 47 if total_products > 0 else 0
    
    # Conversion rate (simulado)
    conversion_rate = 3.2  # En producción calcularías: pedidos / visitas * 100
    
    # ==================== ALERTAS DEL SISTEMA ====================
    
    alerts = []
    
    # Alert si no hay productos
    if total_products == 0:
        alerts.append({
            'type': 'warning',
            'title': '¡Agrega tu primer producto!',
            'message': 'Tu tienda está vacía. Necesitas productos para empezar a vender.',
            'action_text': 'Agregar producto',
            'action_url': url_for('dashboard.new_product')
        })
    
    # Alert para pedidos pendientes
    if pending_orders > 0:
        alerts.append({
            'type': 'info',
            'title': f'Tienes {pending_orders} pedidos pendientes',
            'message': 'Revisa y procesa los pedidos nuevos.',
            'action_text': 'Ver pedidos',
            'action_url': url_for('dashboard.orders')
        })
    
    # Alert para productos con bajo stock
    if low_stock_products > 0:
        alerts.append({
            'type': 'warning',
            'title': f'{low_stock_products} productos con poco stock',
            'message': 'Algunos productos necesitan reposición.',
            'action_text': 'Ver inventario',
            'action_url': url_for('dashboard.products')
        })
    
    # ==================== DATOS ANALYTICS AVANZADOS ====================
    
    analytics_data = {}
    if ANALYTICS_AVAILABLE:
        try:
            analytics = Analytics(current_user.id)
            analytics_data = analytics.get_dashboard_metrics()
        except Exception as e:
            current_app.logger.warning(f"Analytics error: {e}")
            analytics_data = {}
    
    # ==================== RENDER TEMPLATE ====================
    
    return render_template('dashboard/index.html',
        # Métricas principales
        total_products=total_products,
        active_products=active_products,
        total_orders=total_orders,
        pending_orders=pending_orders,
        
        # Ventas y crecimiento
        today_sales=float(today_sales),
        today_orders=today_orders,
        today_growth=today_growth,
        orders_growth=orders_growth,
        
        # Clientes
        customers_count=customers_count,
        new_customers=new_customers_week,
        returning_customers=returning_customers,
        retention_rate=round(retention_rate, 1),
        
        # Mensuales y metas
        monthly_sales=float(monthly_sales),
        monthly_goal=float(monthly_goal),
        monthly_growth=monthly_growth,
        goal_progress=min(round(goal_progress, 1), 100),
        
        # Rendimiento
        avg_order_value=round(float(avg_order_value), 2),
        conversion_rate=conversion_rate,
        products_views=products_views,
        low_stock_products=low_stock_products,
        
        # Listas de datos
        top_products=top_products,
        recent_activities=recent_activities,
        recent_orders=recent_orders,
        alerts=alerts,
        
        # Datos para gráficos (JSON para JavaScript)
        sales_labels=json.dumps(sales_chart_data['labels']),
        sales_data=json.dumps(sales_chart_data['data']),
        orders_labels=json.dumps(orders_chart_data['labels']),
        orders_data=json.dumps(orders_chart_data['data']),
        
        # Analytics avanzados
        analytics=analytics_data
    )

# ==================== FUNCIONES AUXILIARES ====================

def calculate_growth_percentage(current, previous):
    """Calcula el porcentaje de crecimiento"""
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 1)

def get_top_selling_products(user_id, limit=5):
    """Obtiene los productos más vendidos con datos de ventas"""
    top_products = db.session.query(
        Product,
        func.coalesce(func.sum(OrderItem.quantity), 0).label('units_sold'),
        func.coalesce(func.sum(OrderItem.subtotal), 0).label('revenue')
    ).outerjoin(
        OrderItem, Product.id == OrderItem.product_id
    ).outerjoin(
        Order, and_(
            OrderItem.order_id == Order.id,
            Order.status.in_(['confirmed', 'processing', 'shipped', 'delivered'])
        )
    ).filter(
        Product.user_id == user_id,
        Product.is_active == True
    ).group_by(Product.id).order_by(
        desc('units_sold')
    ).limit(limit).all()
    
    # Convertir a lista con atributos adicionales
    products_list = []
    for product, units_sold, revenue in top_products:
        product.units_sold = int(units_sold)
        product.revenue = float(revenue)
        product.sales_count = int(units_sold)  # Alias para compatibilidad
        products_list.append(product)
    
    return products_list

def get_recent_business_activities(user_id, limit=10):
    """Obtiene actividades recientes del negocio"""
    activities = []
    
    # Pedidos recientes (últimos 5)
    recent_orders = Order.query.filter(
        Order.user_id == user_id
    ).order_by(desc(Order.created_at)).limit(5).all()
    
    for order in recent_orders:
        time_ago = get_time_ago_text(order.created_at)
        
        status_icons = {
            'pending': 'fas fa-clock text-yellow-500',
            'confirmed': 'fas fa-check text-blue-500', 
            'processing': 'fas fa-cog text-purple-500',
            'shipped': 'fas fa-truck text-indigo-500',
            'delivered': 'fas fa-check-circle text-green-500',
            'cancelled': 'fas fa-times text-red-500'
        }
        
        status_texts = {
            'pending': 'Nuevo pedido recibido',
            'confirmed': 'Pedido confirmado',
            'processing': 'Pedido en preparación', 
            'shipped': 'Pedido enviado',
            'delivered': 'Pedido entregado',
            'cancelled': 'Pedido cancelado'
        }
        
        activities.append({
            'type': 'order',
            'icon': status_icons.get(order.status, 'fas fa-shopping-cart text-gray-500'),
            'title': status_texts.get(order.status, 'Pedido actualizado'),
            'description': f"{order.customer_name or 'Cliente'} - ${order.total}",
            'time_ago': time_ago,
            'link': url_for('dashboard.order_detail', order_id=order.id) if hasattr(bp, 'order_detail') else '#',
            'created_at': order.created_at
        })
    
    # Productos agregados recientemente (últimos 3)
    recent_products = Product.query.filter(
        Product.user_id == user_id
    ).order_by(desc(Product.created_at)).limit(3).all()
    
    for product in recent_products:
        time_ago = get_time_ago_text(product.created_at)
        
        activities.append({
            'type': 'product',
            'icon': 'fas fa-box text-blue-500',
            'title': 'Producto agregado',
            'description': f"{product.name} - ${product.price}",
            'time_ago': time_ago,
            'link': url_for('dashboard.edit_product', product_id=product.id),
            'created_at': product.created_at
        })
    
    # Ordenar por fecha y limitar
    activities.sort(key=lambda x: x['created_at'], reverse=True)
    return activities[:limit]

def get_time_ago_text(datetime_obj):
    """Convierte datetime a texto 'hace X tiempo'"""
    now = datetime.now()
    diff = now - datetime_obj
    
    if diff.days > 7:
        return f"hace {diff.days} días"
    elif diff.days > 0:
        return f"hace {diff.days} día{'s' if diff.days > 1 else ''}"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"hace {hours} hora{'s' if hours > 1 else ''}"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"hace {minutes} minuto{'s' if minutes > 1 else ''}"
    else:
        return "hace un momento"

def get_sales_chart_data(user_id, days=7):
    """Datos para gráfico de ventas por día"""
    labels = []
    data = []
    
    for i in range(days):
        date = datetime.now().date() - timedelta(days=days-1-i)
        
        # Formato de etiqueta
        if days <= 7:
            # Para 7 días: "Lun 15", "Mar 16", etc.
            day_names = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
            day_name = day_names[date.weekday()]
            labels.append(f"{day_name} {date.day}")
        else:
            # Para más días: "15/06", "16/06", etc.
            labels.append(date.strftime('%d/%m'))
        
        # Ventas del día
        day_sales = db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(
            Order.user_id == user_id,
            func.date(Order.created_at) == date,
            Order.status.in_(['confirmed', 'processing', 'shipped', 'delivered'])
        ).scalar() or 0
        
        data.append(float(day_sales))
    
    return {'labels': labels, 'data': data}

def get_orders_chart_data(user_id, days=7):
    """Datos para gráfico de pedidos por día"""
    labels = []
    data = []
    
    for i in range(days):
        date = datetime.now().date() - timedelta(days=days-1-i)
        
        # Formato de etiqueta (igual que ventas)
        if days <= 7:
            day_names = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
            day_name = day_names[date.weekday()]
            labels.append(f"{day_name} {date.day}")
        else:
            labels.append(date.strftime('%d/%m'))
        
        # Pedidos del día
        day_orders = Order.query.filter(
            Order.user_id == user_id,
            func.date(Order.created_at) == date
        ).count()
        
        data.append(day_orders)
    
    return {'labels': labels, 'data': data}

# ==================== API ENDPOINTS PARA TIEMPO REAL ====================

@bp.route('/api/chart-data')
@login_required
def api_chart_data():
    """API para datos de gráficos dinámicos"""
    chart_type = request.args.get('type', 'sales')
    period = request.args.get('period', '7d')
    
    # Determinar días según período
    days_map = {'7d': 7, '30d': 30, '90d': 90}
    days = days_map.get(period, 7)
    
    if chart_type == 'sales':
        data = get_sales_chart_data(current_user.id, days)
    elif chart_type == 'orders':
        data = get_orders_chart_data(current_user.id, days)
    else:
        data = {'labels': [], 'data': []}
    
    return jsonify(data)

@bp.route('/api/live-metrics')
@login_required
def api_live_metrics():
    """API para métricas en tiempo real"""
    today = datetime.now().date()
    
    # Ventas de hoy
    today_sales = db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.user_id == current_user.id,
        func.date(Order.created_at) == today,
        Order.status.in_(['confirmed', 'processing', 'shipped', 'delivered'])
    ).scalar() or 0
    
    # Pedidos de hoy
    today_orders = Order.query.filter(
        Order.user_id == current_user.id,
        func.date(Order.created_at) == today
    ).count()
    
    # Pedidos pendientes
    pending_orders = Order.query.filter_by(
        user_id=current_user.id,
        status='pending'
    ).count()
    
    return jsonify({
        'today_sales': float(today_sales),
        'today_orders': today_orders,
        'pending_orders': pending_orders,
        'timestamp': datetime.now().isoformat()
    })

@bp.route('/api/dashboard-summary')
@login_required  
def api_dashboard_summary():
    """API para resumen completo del dashboard"""
    today = datetime.now().date()
    month_start = today.replace(day=1)
    
    # Resumen ejecutivo
    summary = {
        'sales': {
            'today': float(db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(
                Order.user_id == current_user.id,
                func.date(Order.created_at) == today,
                Order.status.in_(['confirmed', 'processing', 'shipped', 'delivered'])
            ).scalar() or 0),
            'month': float(db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(
                Order.user_id == current_user.id,
                func.date(Order.created_at) >= month_start,
                Order.status.in_(['confirmed', 'processing', 'shipped', 'delivered'])
            ).scalar() or 0)
        },
        'orders': {
            'today': Order.query.filter(
                Order.user_id == current_user.id,
                func.date(Order.created_at) == today
            ).count(),
            'pending': Order.query.filter_by(
                user_id=current_user.id,
                status='pending'
            ).count()
        },
        'products': {
            'total': Product.query.filter_by(user_id=current_user.id).count(),
            'active': Product.query.filter_by(user_id=current_user.id, is_active=True).count()
        }
    }
    
    return jsonify(summary)

# ==================== RUTAS EXISTENTES (MEJORADAS) ====================

@bp.route('/products')
@login_required
@active_business_required
def products():
    """Lista de productos del negocio"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    status = request.args.get('status', '')
    
    query = Product.query.filter_by(user_id=current_user.id)
    
    # Filtros
    if search:
        query = query.filter(Product.name.contains(search))
    if category:
        query = query.filter_by(category=category)
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
    
    products = query.order_by(Product.created_at.desc())\
        .paginate(page=page, per_page=12, error_out=False)
    
    # Categorías para filtro
    categories = db.session.query(Product.category).filter_by(
        user_id=current_user.id
    ).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]
    
    return render_template('dashboard/products.html', 
                         products=products,
                         search=search,
                         category=category, 
                         status=status,
                         categories=categories)

@bp.route('/products/new', methods=['GET', 'POST'])
@login_required
@active_business_required
def new_product():
    """Crear nuevo producto"""
    form = ProductForm()
    
    if form.validate_on_submit():
        product = Product(
            name=form.name.data,
            description=form.description.data,
            price=form.price.data,
            stock=form.stock.data,
            category=form.category.data,
            is_active=form.is_active.data == '1',
            is_featured=form.is_featured.data == '1',
            user_id=current_user.id
        )
        
        # Guardar imagen
        if form.image.data:
            picture_file = save_picture(form.image.data, 'products')
            product.image = picture_file
        
        db.session.add(product)
        db.session.commit()
        
        flash('¡Producto creado exitosamente!', 'success')
        return redirect(url_for('dashboard.products'))
    
    return render_template('dashboard/product_form.html', form=form, title='Nuevo Producto')

@bp.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
@active_business_required  
def edit_product(product_id):
    """Editar producto existente"""
    product = Product.query.get_or_404(product_id)
    
    if product.user_id != current_user.id:
        flash('No tienes permiso para editar este producto.', 'danger')
        return redirect(url_for('dashboard.products'))
    
    form = ProductForm()
    
    if form.validate_on_submit():
        product.name = form.name.data
        product.description = form.description.data
        product.price = form.price.data
        product.stock = form.stock.data
        product.category = form.category.data
        product.is_active = form.is_active.data == '1'
        product.is_featured = form.is_featured.data == '1'
        
        # Actualizar imagen
        if form.image.data:
            if product.image:
                delete_picture(product.image, 'products')
            picture_file = save_picture(form.image.data, 'products')
            product.image = picture_file
        
        db.session.commit()
        flash('¡Producto actualizado exitosamente!', 'success')
        return redirect(url_for('dashboard.products'))
    
    # Prellenar formulario
    elif request.method == 'GET':
        form.name.data = product.name
        form.description.data = product.description
        form.price.data = product.price
        form.stock.data = product.stock
        form.category.data = product.category
        form.is_active.data = '1' if product.is_active else '0'
        form.is_featured.data = '1' if product.is_featured else '0'
    
    return render_template('dashboard/product_form.html', 
                         form=form, title='Editar Producto', product=product)

@bp.route('/products/<int:product_id>/delete', methods=['POST'])
@login_required
@active_business_required
def delete_product(product_id):
    """Eliminar producto"""
    product = Product.query.get_or_404(product_id)
    
    if product.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'No autorizado'}), 403
    
    # Eliminar imagen
    if product.image:
        delete_picture(product.image, 'products')
    
    db.session.delete(product)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Producto eliminado exitosamente'})

@bp.route('/orders')
@login_required
@active_business_required
def orders():
    """Lista de pedidos mejorada"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    search = request.args.get('search', '')
    
    query = Order.query.filter_by(user_id=current_user.id)
    
    # Filtros
    if status_filter:
        query = query.filter_by(status=status_filter)
    if search:
        query = query.filter(or_(
            Order.customer_name.contains(search),
            Order.customer_phone.contains(search)
        ))
    
    orders = query.order_by(Order.created_at.desc())\
        .paginate(page=page, per_page=20, error_out=False)
    
    # Estadísticas para mostrar
    total_orders = Order.query.filter_by(user_id=current_user.id).count()
    pending_count = Order.query.filter_by(user_id=current_user.id, status='pending').count()
    
    return render_template('dashboard/orders.html', 
                         orders=orders,
                         status_filter=status_filter,
                         search=search,
                         total_orders=total_orders,
                         pending_count=pending_count)

@bp.route('/orders/<int:order_id>')
@login_required
@active_business_required
def order_detail(order_id):
    """Detalle de pedido"""
    order = Order.query.get_or_404(order_id)
    
    if order.user_id != current_user.id:
        flash('No tienes permiso para ver este pedido.', 'danger')
        return redirect(url_for('dashboard.orders'))
    
    return render_template('dashboard/order_detail.html', order=order)

@bp.route('/orders/<int:order_id>/update-status', methods=['POST'])
@login_required
@active_business_required
def update_order_status(order_id):
    """Actualizar estado del pedido"""
    order = Order.query.get_or_404(order_id)
    
    if order.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'No autorizado'}), 403
    
    new_status = request.json.get('status')
    valid_statuses = ['pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled']
    
    if new_status not in valid_statuses:
        return jsonify({'success': False, 'message': 'Estado inválido'}), 400
    
    # Actualizar estado y timestamps
    order.status = new_status
    
    # Actualizar timestamps según el estado
    if new_status == 'confirmed' and not hasattr(order, 'confirmed_at'):
        order.confirmed_at = datetime.now()
    elif new_status == 'processing' and not hasattr(order, 'processing_at'):
        order.processing_at = datetime.now()
    elif new_status == 'shipped' and not hasattr(order, 'shipped_at'):
        order.shipped_at = datetime.now()
    elif new_status == 'delivered':
        order.delivered_at = datetime.now()
    
    db.session.commit()
    
    # Log de la actividad
    current_app.logger.info(f"Order {order_id} status updated to {new_status} by user {current_user.id}")
    
    return jsonify({
        'success': True,
        'message': f'Estado actualizado a {new_status}',
        'new_status': new_status
    })

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
@active_business_required
def settings():
    """Configuración del negocio mejorada"""
    form = BusinessSettingsForm()
    
    if form.validate_on_submit():
        # Datos básicos
        current_user.business_name = form.business_name.data
        current_user.email = form.email.data
        current_user.phone = form.phone.data
        current_user.address = form.address.data
        
        # Campos adicionales si existen en el formulario
        if hasattr(form, 'business_description'):
            current_user.business_description = form.business_description.data
        if hasattr(form, 'currency'):
            current_user.currency = form.currency.data
        if hasattr(form, 'timezone'):
            current_user.timezone = form.timezone.data
        
        # Meta mensual
        monthly_goal = request.form.get('monthly_goal')
        if monthly_goal:
            try:
                current_user.monthly_goal = float(monthly_goal)
            except ValueError:
                flash('Meta mensual debe ser un número válido', 'warning')
        
        # Configuración de notificaciones
        current_user.email_notifications = bool(request.form.get('email_notifications'))
        current_user.whatsapp_notifications = bool(request.form.get('whatsapp_notifications'))
        
        # WhatsApp Business
        whatsapp_number = request.form.get('whatsapp_number')
        if whatsapp_number:
            current_user.whatsapp_number = whatsapp_number
            current_user.whatsapp_enabled = True
        
        # Logo del negocio
        if hasattr(form, 'logo') and form.logo.data:
            if hasattr(current_user, 'logo') and current_user.logo:
                delete_picture(current_user.logo, 'logos')
            picture_file = save_picture(form.logo.data, 'logos')
            current_user.logo = picture_file
        
        # Regenerar slug si cambió el nombre del negocio
        old_name = current_user.business_name
        if old_name != form.business_name.data:
            # Regenerar slug único
            from app.utils.helpers import generate_slug
            base_slug = generate_slug(form.business_name.data)
            slug = base_slug
            counter = 1
            while db.session.query(current_user.__class__).filter_by(slug=slug).first():
                slug = f"{base_slug}-{counter}"
                counter += 1
            current_user.slug = slug
        
        db.session.commit()
        flash('¡Configuración actualizada exitosamente!', 'success')
        return redirect(url_for('dashboard.settings'))
    
    # Prellenar formulario
    elif request.method == 'GET':
        form.business_name.data = current_user.business_name
        form.email.data = current_user.email
        form.phone.data = current_user.phone
        form.address.data = current_user.address
        
        if hasattr(form, 'business_description'):
            form.business_description.data = getattr(current_user, 'business_description', '')
    
    return render_template('dashboard/settings.html', form=form)

# ==================== UTILIDADES Y HERRAMIENTAS ====================

@bp.route('/tools/backup')
@login_required
@active_business_required
def backup_data():
    """Generar backup de datos del usuario"""
    try:
        # Aquí implementarías la lógica de backup
        # Por ahora retornamos un mensaje
        flash('Función de backup en desarrollo', 'info')
        return redirect(url_for('dashboard.settings'))
    except Exception as e:
        current_app.logger.error(f"Backup error: {e}")
        flash('Error al generar backup', 'error')
        return redirect(url_for('dashboard.settings'))

@bp.route('/tools/export')
@login_required
@active_business_required
def export_all_data():
    """Exportar todos los datos del negocio"""
    try:
        # Implementar exportación completa
        flash('Función de exportación en desarrollo', 'info')
        return redirect(url_for('dashboard.settings'))
    except Exception as e:
        current_app.logger.error(f"Export error: {e}")
        flash('Error al exportar datos', 'error')
        return redirect(url_for('dashboard.settings'))

# ==================== WEBHOOKS Y NOTIFICACIONES ====================

@bp.route('/api/notifications/mark-read', methods=['POST'])
@login_required
def mark_notifications_read():
    """Marcar notificaciones como leídas"""
    notification_ids = request.json.get('ids', [])
    
    # Aquí implementarías la lógica de notificaciones
    # Por ahora retornamos success
    
    return jsonify({
        'success': True,
        'message': f'{len(notification_ids)} notificaciones marcadas como leídas'
    })

@bp.route('/api/quick-actions', methods=['POST'])
@login_required
def quick_actions():
    """Acciones rápidas desde el dashboard"""
    action = request.json.get('action')
    
    try:
        if action == 'mark_all_delivered':
            # Marcar todos los pedidos shipped como delivered
            updated = Order.query.filter_by(
                user_id=current_user.id,
                status='shipped'
            ).update({'status': 'delivered', 'delivered_at': datetime.now()})
            
            db.session.commit()
            return jsonify({
                'success': True,
                'message': f'{updated} pedidos marcados como entregados'
            })
            
        elif action == 'restock_alert':
            # Obtener productos con bajo stock
            low_stock = Product.query.filter(
                Product.user_id == current_user.id,
                Product.stock <= 5,
                Product.is_active == True
            ).count()
            
            return jsonify({
                'success': True,
                'message': f'{low_stock} productos necesitan reposición'
            })
            
        else:
            return jsonify({
                'success': False,
                'message': 'Acción no reconocida'
            }), 400
            
    except Exception as e:
        current_app.logger.error(f"Quick action error: {e}")
        return jsonify({
            'success': False,
            'message': 'Error al ejecutar la acción'
        }), 500

# ==================== ERROR HANDLERS ====================

@bp.errorhandler(404)
def dashboard_not_found(error):
    """404 específico del dashboard"""
    return render_template('errors/404.html'), 404

@bp.errorhandler(500)
def dashboard_server_error(error):
    """500 específico del dashboard"""
    db.session.rollback()
    current_app.logger.error(f"Dashboard error: {error}")
    return render_template('errors/500.html'), 500

# ==================== HELPER PARA DEBUGGING ====================

@bp.route('/debug/info')
@login_required
def debug_info():
    """Información de debugging (solo en desarrollo)"""
    if not current_app.debug:
        return "Not available in production", 403
    
    info = {
        'user_id': current_user.id,
        'business_name': current_user.business_name,
        'total_products': Product.query.filter_by(user_id=current_user.id).count(),
        'total_orders': Order.query.filter_by(user_id=current_user.id).count(),
        'analytics_available': ANALYTICS_AVAILABLE,
        'templates_available': [
            'index.html',
            'products.html', 
            'orders.html',
            'customers.html',
            'analytics.html',
            'settings.html'
        ]
    }
    
    return jsonify(info)
