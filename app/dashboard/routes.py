import os
from flask import render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app import db
from app.dashboard import bp
from app.dashboard.forms import ProductForm, BusinessSettingsForm
from app.models import Product, Order
from app.utils.decorators import business_required, active_business_required
from app.utils.helpers import save_picture, delete_picture

@bp.route('/')
@login_required
@active_business_required
def index():
    """Dashboard principal"""
    # Estadísticas del negocio
    total_products = Product.query.filter_by(user_id=current_user.id).count()
    active_products = Product.query.filter_by(user_id=current_user.id, is_active=True).count()
    total_orders = Order.query.filter_by(user_id=current_user.id).count()
    pending_orders = Order.query.filter_by(user_id=current_user.id, status='pending').count()
    
    # Últimos pedidos
    recent_orders = Order.query.filter_by(user_id=current_user.id)\
        .order_by(Order.created_at.desc()).limit(5).all()
    
    return render_template('dashboard/index.html',
        total_products=total_products,
        active_products=active_products,
        total_orders=total_orders,
        pending_orders=pending_orders,
        recent_orders=recent_orders
    )

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
    
    flash('Producto eliminado exitosamente.', 'success')
    return jsonify({'success': True})

@bp.route('/orders')
@login_required
@active_business_required
def orders():
    """Lista de pedidos del negocio"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    
    query = Order.query.filter_by(user_id=current_user.id)
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    orders = query.order_by(Order.created_at.desc())\
        .paginate(page=page, per_page=20, error_out=False)
    
    return render_template('dashboard/orders.html', orders=orders, status_filter=status_filter)

@bp.route('/orders/<int:order_id>')
@login_required
@active_business_required
def order_detail(order_id):
    """Detalle de un pedido"""
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
    valid_statuses = ['pending', 'confirmed', 'preparing', 'ready', 'delivered', 'cancelled']
    
    if new_status not in valid_statuses:
        return jsonify({'success': False, 'message': 'Estado inválido'}), 400
    
    order.status = new_status
    if new_status == 'delivered':
        from datetime import datetime
        order.delivered_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': f'Estado actualizado a {order.get_status_display()}'
    })

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
@active_business_required
def settings():
    """Configuración del negocio"""
    form = BusinessSettingsForm()
    
    if form.validate_on_submit():
        current_user.business_name = form.business_name.data
        current_user.description = form.description.data
        current_user.phone = form.phone.data
        current_user.address = form.address.data
        current_user.accept_orders = form.accept_orders.data == '1'
        current_user.currency = form.currency.data
        
        # Actualizar logo si se subió uno nuevo
        if form.logo.data:
            if current_user.logo:
                delete_picture(current_user.logo, 'logos')
            
            picture_file = save_picture(form.logo.data, 'logos')
            current_user.logo = picture_file
        
        # Regenerar slug si cambió el nombre
        if current_user.business_name != form.business_name.data:
            current_user.slug = current_user.generate_unique_slug()
        
        db.session.commit()
        flash('¡Configuración actualizada exitosamente!', 'success')
        return redirect(url_for('dashboard.settings'))
    
    elif request.method == 'GET':
        form.business_name.data = current_user.business_name
        form.description.data = current_user.description
        form.phone.data = current_user.phone
        form.address.data = current_user.address
        form.accept_orders.data = '1' if current_user.accept_orders else '0'
        form.currency.data = current_user.currency
    
    return render_template('dashboard/settings.html', form=form)
