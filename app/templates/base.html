import json
from flask import render_template, redirect, url_for, flash, abort
from app.public import public_bp
from app.public.forms import OrderForm
from app.models import User, Product, Order
from app.extensions import db

@public_bp.route('/<slug>')
def store(slug):
    """Vista pública de la tienda de un negocio"""
    # Buscar el negocio por su slug
    business = User.query.filter_by(slug=slug, is_active=True).first_or_404()
    
    # Obtener productos activos del negocio
    products = Product.query.filter_by(user_id=business.id, is_active=True)\
                           .filter(Product.stock > 0)\
                           .order_by(Product.name).all()
    
    return render_template('public/store.html', business=business, products=products)

@public_bp.route('/<slug>/order', methods=['POST'])
def create_order(slug):
    """Crear un pedido en la tienda"""
    # Buscar el negocio
    business = User.query.filter_by(slug=slug, is_active=True).first_or_404()
    
    form = OrderForm()
    
    if form.validate_on_submit():
        # Parsear los datos de productos del campo oculto
        try:
            products_data = json.loads(form.products_data.data)
        except:
            flash('Error al procesar el pedido. Por favor intenta nuevamente.', 'danger')
            return redirect(url_for('public.store', slug=slug))
        
        # Validar que hay productos seleccionados
        if not products_data:
            flash('Debes seleccionar al menos un producto.', 'warning')
            return redirect(url_for('public.store', slug=slug))
        
        # Crear el pedido
        order = Order(
            customer_name=form.customer_name.data,
            customer_email=form.customer_email.data,
            customer_phone=form.customer_phone.data,
            delivery_address=form.delivery_address.data,
            notes=form.notes.data,
            user_id=business.id
        )
        
        # Variable para el total
        total = 0
        
        # Procesar cada producto del pedido
        for item in products_data:
            product_id = item.get('id')
            quantity = item.get('quantity', 1)
            
            # Buscar el producto
            product = Product.query.filter_by(
                id=product_id, 
                user_id=business.id, 
                is_active=True
            ).first()
            
            if product and product.stock >= quantity:
                # Agregar producto al pedido
                order.products.append(product)
                
                # Actualizar stock
                product.stock -= quantity
                
                # Calcular total
                total += float(product.price) * quantity
                
                # Aquí podrías guardar la cantidad y precio en la tabla intermedia
                # Por ahora lo simplificamos
        
        # Asignar total al pedido
        order.total = total
        
        try:
            db.session.add(order)
            db.session.commit()
            
            flash(f'¡Pedido realizado exitosamente! Tu número de orden es: {order.order_number}', 'success')
            return render_template('public/order_success.html', order=order, business=business)
            
        except Exception as e:
            db.session.rollback()
            flash('Error al procesar el pedido. Por favor intenta nuevamente.', 'danger')
            return redirect(url_for('public.store', slug=slug))
    
    # Si hay errores en el formulario
    flash('Por favor corrige los errores en el formulario.', 'warning')
    return redirect(url_for('public.store', slug=slug))
