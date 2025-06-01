import os
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.dashboard import dashboard_bp
from app.dashboard.forms import ProductForm, OrderStatusForm
from app.models import Product, Order
from app.extensions import db

def allowed_file(filename):
    """Verifica si el archivo es permitido"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@dashboard_bp.route('/')
@login_required
def index():
    """Panel principal del dashboard"""
    # Estadísticas básicas
    total_products = Product.query.filter_by(user_id=current_user.id).count()
    active_products = Product.query.filter_by(user_id=current_user.id, is_active=True).count()
    total_orders = Order.query.filter_by(user_id=current_user.id).count()
    pending_orders = Order.query.filter_by(user_id=current_user.id, status='pending').count()
    
    # Últimos pedidos
    recent_orders = Order.query.filter_by(user_id=current_user.id)\
                              .order_by(Order.created_at.desc())\
                              .limit(5).all()
    
    return render_template('dashboard/index.html',
                         total_products=total_products,
                         active_products=active_products,
                         total_orders=total_orders,
                         pending_orders=pending_orders,
                         recent_orders=recent_orders)

@dashboard_bp.route('/products')
@login_required
def products():
    """Lista de productos del negocio"""
    page = request.args.get('page', 1, type=int)
    products = Product.query.filter_by(user_id=current_user.id)\
                           .order_by(Product.created_at.desc())\
                           .paginate(page=page, per_page=current_app.config['PRODUCTS_PER_PAGE'])
    
    return render_template('dashboard/products.html', products=products)

@dashboard_bp.route('/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    """Agregar nuevo producto"""
    form = ProductForm()
    
    if form.validate_on_submit():
        product = Product(
            name=form.name.data,
            description=form.description.data,
            price=form.price.data,
            stock=form.stock.data,
            user_id=current_user.id
        )
        
        # Manejar imagen si se sube
        if form.image.data:
            file = form.image.data
            if file and allowed_file(file.filename):
                # Crear nombre único para el archivo
                filename = secure_filename(file.filename)
                timestamp = str(int(datetime.utcnow().timestamp()))
                filename = f"{current_user.id}_{timestamp}_{filename}"
                
                # Guardar archivo
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                
                # Guardar ruta en el modelo
                product.image = f"uploads/{filename}"
        
        try:
            db.session.add(product)
            db.session.commit()
            flash('Producto agregado exitosamente.', 'success')
            return redirect(url_for('dashboard.products'))
        except Exception as e:
            db.session.rollback()
            flash('Error al agregar el producto.', 'danger')
    
    return render_template('dashboard/product_form.html', form=form, title='Agregar Producto')

@dashboard_bp.route('/products/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_product(id):
    """Editar producto existente"""
    product = Product.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    form = ProductForm(obj=product)
    
    if form.validate_on_submit():
        product.name = form.name.data
        product.description = form.description.data
        product.price = form.price.data
        product.stock = form.stock.data
        
        # Manejar nueva imagen si se sube
        if form.image.data:
            file = form.image.data
            if file and allowed_file(file.filename):
                # Eliminar imagen anterior si existe
                if product.image:
                    old_path = os.path.join(current_app.root_path, 'static', product.image)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                # Guardar nueva imagen
                filename = secure_filename(file.filename)
                timestamp = str(int(datetime.utcnow().timestamp()))
                filename = f"{current_user.id}_{timestamp}_{filename}"
                
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                
                product.image = f"uploads/{filename}"
        
        try:
            db.session.commit()
            flash('Producto actualizado exitosamente.', 'success')
            return redirect(url_for('dashboard.products'))
        except Exception as e:
            db.session.rollback()
            flash('Error al actualizar el producto.', 'danger')
    
    return render_template('dashboard/product_form.html', form=form, title='Editar Producto', product=product)

@dashboard_bp.route('/products/toggle/<int:id>')
@login_required
def toggle_product(id):
    """Activar/desactivar producto"""
    product = Product.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    
    product.is_active = not product.is_active
    db.session.commit()
    
    status = 'activado' if product.is_active else 'desactivado'
    flash(f'Producto {status} exitosamente.', 'success')
    
    return redirect(url_for('dashboard.products'))

@dashboard_bp.route('/orders')
@login_required
def orders():
    """Lista de pedidos del negocio"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    
    query = Order.query.filter_by(user_id=current_user.id)
    
    if status:
        query = query.filter_by(status=status)
    
    orders = query.order_by(Order.created_at.desc())\
                  .paginate(page=page, per_page=current_app.config['ORDERS_PER_PAGE'])
    
    return render_template('dashboard/orders.html', orders=orders, current_status=status)

@dashboard_bp.route('/orders/<int:id>')
@login_required
def order_detail(id):
    """Detalle de un pedido"""
    order = Order.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    form = OrderStatusForm(status=order.status)
    
    return render_template('dashboard/order_detail.html', order=order, form=form)

@dashboard_bp.route('/orders/<int:id>/status', methods=['POST'])
@login_required
def update_order_status(id):
    """Actualizar estado de un pedido"""
    order = Order.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    form = OrderStatusForm()
    
    if form.validate_on_submit():
        order.status = form.status.data
        db.session.commit()
        flash('Estado del pedido actualizado.', 'success')
    
    return redirect(url_for('dashboard.order_detail', id=id))

# Importar datetime al inicio del archivo
from datetime import datetime
