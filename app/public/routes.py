from flask import render_template, redirect, url_for, flash, request, jsonify, session
from app import db
from app.public import bp
from app.public.forms import OrderForm
from app.models import User, Product, Order, OrderItem

@bp.route('/<slug>')
def store(slug):
    """Página pública de la tienda"""
    # Buscar el negocio por slug
    business = User.query.filter_by(slug=slug, is_active=True).first_or_404()
    
    # Obtener productos activos
    products = Product.query.filter_by(user_id=business.id, is_active=True)\
        .order_by(Product.is_featured.desc(), Product.created_at.desc()).all()
    
    # Obtener carrito de la sesión
    cart_key = f'cart_{business.id}'
    cart = session.get(cart_key, {})
    
    return render_template('public/store.html', 
        business=business, 
        products=products,
        cart=cart)

@bp.route('/<slug>/add-to-cart', methods=['POST'])
def add_to_cart(slug):
    """Agregar producto al carrito"""
    business = User.query.filter_by(slug=slug, is_active=True).first_or_404()
    
    if not business.accept_orders:
        return jsonify({'success': False, 'message': 'Este negocio no está aceptando pedidos'}), 400
    
    product_id = request.json.get('product_id')
    quantity = request.json.get('quantity', 1)
    
    product = Product.query.get_or_404(product_id)
    
    # Verificar que el producto pertenece al negocio
    if product.user_id != business.id:
        return jsonify({'success': False, 'message': 'Producto no válido'}), 400
    
    # Verificar stock
    if product.stock < quantity:
        return jsonify({'success': False, 'message': 'Stock insuficiente'}), 400
    
    # Obtener o crear carrito en sesión
    cart_key = f'cart_{business.id}'
    cart = session.get(cart_key, {})
    
    # Agregar producto al carrito
    product_key = str(product_id)
    if product_key in cart:
        cart[product_key]['quantity'] += quantity
    else:
        cart[product_key] = {
            'id': product.id,
            'name': product.name,
            'price': float(product.price),
            'quantity': quantity,
            'image': product.image
        }
    
    # Guardar carrito en sesión
    session[cart_key] = cart
    session.modified = True
    
    # Calcular total del carrito
    cart_total = sum(item['price'] * item['quantity'] for item in cart.values())
    cart_count = sum(item['quantity'] for item in cart.values())
    
    return jsonify({
        'success': True,
        'message': f'{product.name} agregado al carrito',
        'cart_count': cart_count,
        'cart_total': cart_total
    })

@bp.route('/<slug>/checkout', methods=['GET', 'POST'])
def checkout(slug):
    """Página de checkout y procesamiento de pedido"""
    business = User.query.filter_by(slug=slug, is_active=True).first_or_404()
    
    if not business.accept_orders:
        flash('Este negocio no está aceptando pedidos en este momento.', 'warning')
        return redirect(url_for('public.store', slug=slug))
    
    # Obtener carrito
    cart_key = f'cart_{business.id}'
    cart = session.get(cart_key, {})
    
    if not cart:
        flash('Tu carrito está vacío.', 'info')
        return redirect(url_for('public.store', slug=slug))
    
    form = OrderForm()
    
    if form.validate_on_submit():
        # Crear pedido
        order = Order(
            customer_name=form.customer_name.data,
            customer_email=form.customer_email.data,
            customer_phone=form.customer_phone.data,
            delivery_address=form.delivery_address.data,
            notes=form.notes.data,
            user_id=business.id
        )
        
        db.session.add(order)
        db.session.flush()  # Para obtener el ID del pedido
        
        # Agregar items al pedido
        total = 0
        for item_data in cart.values():
            product = Product.query.get(item_data['id'])
            if product and product.stock >= item_data['quantity']:
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=item_data['quantity'],
                    unit_price=product.price
                )
                order_item.calculate_subtotal()
                
                # Actualizar stock
                product.stock -= item_data['quantity']
                
                db.session.add(order_item)
                total += order_item.subtotal
        
        # Actualizar totales del pedido
        order.subtotal = total
        order.total = total  # Por ahora sin delivery fee
        
        db.session.commit()
        
        # Limpiar carrito
        session.pop(cart_key, None)
        
        flash(f'¡Tu pedido #{order.order_number} ha sido recibido! El negocio se pondrá en contacto contigo pronto.', 'success')
        return redirect(url_for('public.order_confirmation', slug=slug, order_number=order.order_number))
    
    # Calcular totales para mostrar
    cart_items = []
    subtotal = 0
    
    for item_data in cart.values():
        product = Product.query.get(item_data['id'])
        if product:
            item_total = item_data['price'] * item_data['quantity']
            cart_items.append({
                'product': product,
                'quantity': item_data['quantity'],
                'subtotal': item_total
            })
            subtotal += item_total
    
    return render_template('public/checkout.html',
        business=business,
        form=form,
        cart_items=cart_items,
        subtotal=subtotal,
        total=subtotal  # Por ahora sin delivery fee
    )

@bp.route('/<slug>/order-confirmation/<order_number>')
def order_confirmation(slug, order_number):
    """Página de confirmación del pedido"""
    business = User.query.filter_by(slug=slug).first_or_404()
    order = Order.query.filter_by(order_number=order_number, user_id=business.id).first_or_404()
    
    return render_template('public/order_confirmation.html',
        business=business,
        order=order
    )
