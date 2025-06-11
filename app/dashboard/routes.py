import os
from flask import render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import func, desc, and_, or_
import json
from app import db
from app.dashboard import bp
from app.dashboard.forms import ProductForm, BusinessSettingsForm
from app.models import Product, Order, OrderItem
from app.utils.decorators import business_required, active_business_required
from app.utils.helpers import save_picture, delete_picture, format_currency

@bp.route('/')
@login_required
@active_business_required
def index():
    """Dashboard principal con métricas y analytics completos"""
    
    # Fechas para cálculos
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    month_start = today.replace(day=1)
    
    # Estadísticas básicas del negocio
    total_products = Product.query.filter_by(user_id=current_user.id).count()
    active_products = Product.query.filter_by(user_id=current_user.id, is_active=True).count()
    total_orders = Order.query.filter_by(user_id=current_user.id).count()
    pending_orders = Order.query.filter_by(user_id=current_user.id, status='pending').count()
    
    # Métricas de ventas de hoy
    today_sales = db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.user_id == current_user.id,
        func.date(Order.created_at) == today,
        Order.status.in_(['confirmed', 'processing', 'shipped', 'delivered'])
    ).scalar() or 0
    
    # Ventas de ayer para comparación
    yesterday_sales = db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.user_id == current_user.id,
        func.date(Order.created_at) == yesterday,
        Order.status.in_(['confirmed', 'processing', 'shipped', 'delivered'])
    ).scalar() or 0
    
    # Cálculo de crecimiento
    today_growth = 0
    if yesterday_sales > 0:
        today_growth = ((today_sales - yesterday_sales) / yesterday_sales) * 100
    elif today_sales > 0:
        today_growth = 100
    
    # Pedidos de hoy
    today_orders = Order.query.filter(
        Order.user_id == current_user.id,
        func.date(Order.created_at) == today
    ).count()
    
    # Clientes únicos (basado en teléfonos únicos)
    customers_count = db.session.query(func.count(func.distinct(Order.customer_phone))).filter(
        Order.user_id == current_user.id
    ).scalar() or 0
    
    # Nuevos clientes esta semana
    new_customers = db.session.query(func.count(func.distinct(Order.customer_phone))).filter(
        Order.user_id == current_user.id,
        Order.created_at >= week_ago
    ).scalar() or 0
    
    # Ventas del mes actual
    monthly_sales = db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.user_id == current_user.id,
        func.date(Order.created_at) >= month_start,
        Order.status.in_(['confirmed', 'processing', 'shipped', 'delivered'])
    ).scalar() or 0
    
    # Productos más vendidos
    top_products = db.session.query(
        Product,
        func.coalesce(func.sum(OrderItem.quantity), 0).label('sales_count')
    ).outerjoin(
        OrderItem, Product.id == OrderItem.product_id
    ).outerjoin(
        Order, and_(
            OrderItem.order_id == Order.id,
            Order.status.in_(['confirmed', 'processing', 'shipped', 'delivered'])
        )
    ).filter(
        Product.user_id == current_user.id,
        Product.is_active == True
    ).group_by(Product.id).order_by(
        desc('sales_count')
    ).limit(5).all()
    
    # Convertir productos con sales_count
    products_list = []
    for product, sales_count in top_products:
        product.sales_count = sales_count
        products_list.append(product)
    
    # Actividad reciente
    recent_activities = get_recent_activities(current_user.id, limit=8)
    
    # Datos para gráficos de ventas (últimos 7 días)
    sales_data = get_sales_chart_data(current_user.id, days=7)
    
    # Últimos pedidos
    recent_orders = Order.query.filter_by(user_id=current_user.id)\
        .order_by(Order.created_at.desc()).limit(5).all()
    
    return render_template('dashboard/index.html',
        # Métricas principales
        total_products=total_products,
        active_products=active_products,
        total_orders=total_orders,
        pending_orders=pending_orders,
        today_sales=float(today_sales),
        today_orders=today_orders,
        customers_count=customers_count,
        today_growth=round(today_growth, 1),
        new_customers=new_customers,
        products_views=total_products * 25,  # Simulado
        
        # Meta mensual
        monthly_sales=float(monthly_sales),
        monthly_goal=getattr(current_user, 'monthly_goal', 10000) or 10000,
        
        # Listas y datos
        top_products=products_list,
        recent_activities=recent_activities,
        recent_orders=recent_orders,
        
        # Datos para gráficos (JSON)
        sales_labels=json.dumps(sales_data['labels']),
        sales_data=json.dumps(sales_data['data'])
    )

def get_recent_activities(user_id, limit=8):
    """Obtiene la actividad reciente del negocio"""
    activities = []
    
    # Pedidos recientes
    recent_orders = Order.query.filter(
        Order.user_id == user_id
    ).order_by(desc(Order.created_at)).limit(5).all()
    
    for order in recent_orders:
        time_diff = datetime.now() - order.created_at
        
        if time_diff.days > 0:
            time_ago = f"hace {time_diff.days} día{'s' if time_diff.days > 1 else ''}"
        elif time_diff.seconds > 3600:
            hours = time_diff.seconds // 3600
            time_ago = f"hace {hours} hora{'s' if hours > 1 else ''}"
        elif time_diff.seconds > 60:
            minutes = time_diff.seconds // 60
            time_ago = f"hace {minutes} minuto{'s' if minutes > 1 else ''}"
        else:
            time_ago = "hace un momento"
        
        status_text = {
            'pending': 'Nuevo pedido recibido',
            'confirmed': 'Pedido confirmado',
            'processing': 'Pedido en preparación',
            'shipped': 'Pedido enviado',
            'delivered': 'Pedido entregado',
            'cancelled': 'Pedido cancelado'
        }.get(order.status, 'Pedido actualizado')
        
        activities.append({
            'type': 'order',
            'title': status_text,
            'description': f"{order.customer_name} - ${order.total}",
            'time_ago': time_ago,
            'link': f"/dashboard/orders/{order.id}"
        })
    
    # Productos agregados recientemente
    recent_products = Product.query.filter(
        Product.user_id == user_id
    ).order_by(desc(Product.created_at)).limit(3).all()
    
    for product in recent_products:
        time_diff = datetime.now() - product.created_at
        
        if time_diff.days > 0:
            time_ago = f"hace {time_diff.days} día{'s' if time_diff.days > 1 else ''}"
        else:
            time_ago = "hoy"
        
        activities.append({
            'type': 'product',
            'title': 'Producto agregado',
            'description': f"{product.name} - ${product.price}",
            'time_ago': time_ago,
            'link': f"/dashboard/products/{product.id}/edit"
        })
    
    # Ordenar por "relevancia" (pedidos primero, luego productos)
    activities.sort(key=lambda x: (x['type'] == 'product', x['time_ago']))
    return activities[:limit]

def get_sales_chart_data(user_id, days=7):
    """Obtiene datos para el gráfico de ventas"""
    labels = []
    data = []
    
    for i in range(days):
        date = datetime.now().date() - timedelta(days=days-1-i)
        
        # Formato de fecha para etiqueta
        if days <= 7:
            labels.append(date.strftime('%a %d'))  # "Lun 15"
        else:
            labels.append(date.strftime('%d/%m'))  # "15/06"
        
        # Ventas del día
        day_sales = db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(
            Order.user_id == user_id,
            func.date(Order.created_at) == date,
            Order.status.in_(['confirmed', 'processing', 'shipped', 'delivered'])
        ).scalar() or 0
        
        data.append(float(day_sales))
    
    return {
        'labels': labels,
        'data': data
    }

@bp.route('/chart-data')
@login_required
def chart_data():
    """API endpoint para datos de gráficos dinámicos"""
    period = request.args.get('period', '7d')
    
    if period == '7d':
        days = 7
    elif period == '30d':
        days = 30
    else:
        days = 7
    
    data = get_sales_chart_data(current_user.id, days)
    
    return jsonify({
        'labels': data['labels'],
        'data': data['data']
    })

@bp.route('/live-metrics')
@login_required
def live_metrics():
    """API endpoint para métricas en tiempo real"""
    today = datetime.now().date()
    
    # Ventas de hoy
    today_sales = db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.user_id == current_user.id,
        func.date(Order.created_at) == today,
        Order.status.in_(['confirmed', 'processing', 'shipped', 'delivered'])
    ).scalar()
    
    # Pedidos de hoy
    today_orders = db.session.query(func.count(Order.id)).filter(
        Order.user_id == current_user.id,
        func.date(Order.created_at) == today
    ).scalar()
    
    return jsonify({
        'today_sales': float(today_sales or 0),
        'today_orders': today_orders or 0,
        'timestamp': datetime.now().isoformat()
    })

# Resto de las rutas existentes (products, orders, etc.)

@bp.route('/products')
@login_required
@active_business_required
def products():
    """Lista de productos del negocio"""
    page = request.args.get('page', 1, type=int)
    products = Product.query.filter_by(user_id=current_user.id)\
        .order_by(Product.created_at.desc())\
        .paginate(page=page, per_page=12, error_out=False)
    
    return render_template('dashboard/products.html', products=products)

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
        
        # Guardar imagen si se subió
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
    
    # Verificar que el producto pertenece al usuario actual
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
        
        # Actualizar imagen si se subió una nueva
        if form.image.data:
            # Eliminar imagen anterior
            if product.image:
                delete_picture(product.image, 'products')
            
            picture_file = save_picture(form.image.data, 'products')
            product.image = picture_file
        
        db.session.commit()
        flash('¡Producto actualizado exitosamente!', 'success')
        return redirect(url_for('dashboard.products'))
    
    # Prellenar el formulario
    elif request.method == 'GET':
        form.name.data = product.name
        form.description.data = product.description
        form.price.data = product.price
        form.stock.data = product.stock
        form.category.data = product.category
        form.is_active.data = '1' if product.is_active else '0'
        form.is_featured.data = '1' if product.is_featured else '0'
    
    return render_template('dashboard/product_form.html', 
        form=form, 
        title='Editar Producto', 
        product=product)

@bp.route('/products/<int:product_id>/delete', methods=['POST'])
@login_required
@active_business_required
def delete_product(product_id):
    """Eliminar producto"""
    product = Product.query.get_or_404(product_id)
    
    if product.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'No autorizado'}), 403
    
    # Eliminar imagen si existe
    if product.image:
        delete_picture(product.image, 'products')
    
    db.session.delete(product)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Producto eliminado exitosamente'})

@bp.route('/orders')
@login_required
@active_business_required
def orders():
    """Lista de pedidos"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    
    query = Order.query.filter_by(user_id=current_user.id)
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    orders = query.order_by(Order.created_at.desc())\
        .paginate(page=page, per_page=20, error_out=False)
    
    return render_template('dashboard/orders.html', 
                         orders=orders, 
                         status_filter=status_filter)

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

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
@active_business_required
def settings():
    """Configuración del negocio"""
    form = BusinessSettingsForm()
    
    if form.validate_on_submit():
        current_user.business_name = form.business_name.data
        current_user.email = form.email.data
        current_user.phone = form.phone.data
        current_user.address = form.address.data
        
        # Actualizar campos adicionales si existen
        if hasattr(current_user, 'business_description'):
            current_user.business_description = form.business_description.data if hasattr(form, 'business_description') else None
        if hasattr(current_user, 'monthly_goal'):
            monthly_goal = request.form.get('monthly_goal')
            if monthly_goal:
                current_user.monthly_goal = float(monthly_goal)
        
        db.session.commit()
        flash('Configuración actualizada exitosamente.', 'success')
        return redirect(url_for('dashboard.settings'))
    
    # Prellenar formulario
    elif request.method == 'GET':
        form.business_name.data = current_user.business_name
        form.email.data = current_user.email
        form.phone.data = current_user.phone
        form.address.data = current_user.address
    
    return render_template('dashboard/settings.html', form=form)
