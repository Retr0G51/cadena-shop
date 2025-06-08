"""
Rutas de webhooks para integraciones externas
Soporta Stripe, WhatsApp, y webhooks personalizados
"""
from flask import request, jsonify, current_app
from datetime import datetime
import hmac
import hashlib
import json
from app.webhooks import bp
from app.extensions import db, csrf
from app.models import User, Order, Product
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoicePayment

# Desactivar CSRF para webhooks
csrf.exempt(bp)

@bp.route('/stripe', methods=['POST'])
def stripe_webhook():
    """
    Webhook para eventos de Stripe
    Maneja pagos, suscripciones, etc.
    """
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    
    # Verificar firma
    webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
    
    if not webhook_secret:
        current_app.logger.warning("Stripe webhook secret not configured")
        return jsonify({'error': 'Webhook not configured'}), 500
    
    try:
        import stripe
        stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
        
        # Verificar evento
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        # Payload inválido
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        # Firma inválida
        return jsonify({'error': 'Invalid signature'}), 400
    
    # Manejar evento
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        handle_stripe_payment_success(payment_intent)
    
    elif event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        handle_stripe_invoice_paid(invoice)
    
    elif event['type'] == 'customer.subscription.created':
        subscription = event['data']['object']
        handle_stripe_subscription_created(subscription)
    
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        handle_stripe_subscription_cancelled(subscription)
    
    # Log evento
    current_app.logger.info(f"Stripe webhook received: {event['type']}")
    
    return jsonify({'status': 'success'}), 200

@bp.route('/whatsapp', methods=['POST'])
def whatsapp_webhook():
    """
    Webhook para mensajes de WhatsApp Business API
    """
    # Verificación inicial de WhatsApp
    if request.method == 'GET':
        verify_token = current_app.config.get('WHATSAPP_VERIFY_TOKEN', 'pedidossaas')
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == verify_token:
            return challenge, 200
        else:
            return 'Forbidden', 403
    
    # Procesar mensaje
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data'}), 400
    
    # Procesar mensajes entrantes
    if 'messages' in data.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {}):
        messages = data['entry'][0]['changes'][0]['value']['messages']
        
        for message in messages:
            handle_whatsapp_message(message)
    
    return jsonify({'status': 'received'}), 200

@bp.route('/custom/<webhook_id>', methods=['POST'])
def custom_webhook(webhook_id):
    """
    Webhook personalizado para integraciones específicas
    
    Args:
        webhook_id: ID único del webhook configurado
    """
    # Buscar configuración del webhook
    # Aquí podrías tener una tabla de configuraciones de webhooks
    
    # Por ahora, implementación básica
    data = request.get_json()
    headers = dict(request.headers)
    
    # Log del webhook
    current_app.logger.info(f"Custom webhook received: {webhook_id}")
    current_app.logger.debug(f"Headers: {headers}")
    current_app.logger.debug(f"Body: {data}")
    
    # Verificar firma si está configurada
    signature = request.headers.get('X-Webhook-Signature')
    if signature:
        expected_signature = generate_webhook_signature(
            webhook_id,
            request.get_data(as_text=True)
        )
        
        if not hmac.compare_digest(signature, expected_signature):
            return jsonify({'error': 'Invalid signature'}), 401
    
    # Procesar según el tipo de webhook
    webhook_type = data.get('type') or data.get('event_type')
    
    if webhook_type == 'order.created':
        handle_external_order_created(data)
    elif webhook_type == 'product.update':
        handle_external_product_update(data)
    elif webhook_type == 'inventory.alert':
        handle_external_inventory_alert(data)
    else:
        # Webhook genérico - solo log
        current_app.logger.info(f"Unhandled webhook type: {webhook_type}")
    
    return jsonify({'status': 'received'}), 200

# Handlers específicos

def handle_stripe_payment_success(payment_intent):
    """Maneja un pago exitoso de Stripe"""
    # Buscar el pedido o factura asociada
    metadata = payment_intent.get('metadata', {})
    
    if 'order_id' in metadata:
        order = Order.query.get(metadata['order_id'])
        if order:
            order.payment_status = 'paid'
            order.payment_reference = payment_intent['id']
            db.session.commit()
            
            # Enviar notificación
            notify_payment_received(order)
    
    elif 'invoice_id' in metadata:
        invoice = Invoice.query.get(metadata['invoice_id'])
        if invoice:
            # Registrar pago
            payment = InvoicePayment(
                invoice_id=invoice.id,
                amount=payment_intent['amount'] / 100,  # Stripe usa centavos
                payment_method='stripe',
                reference=payment_intent['id']
            )
            db.session.add(payment)
            
            # Actualizar estado de factura
            if invoice.get_pending_amount() <= payment.amount:
                invoice.mark_as_paid()
            
            db.session.commit()

def handle_stripe_invoice_paid(stripe_invoice):
    """Maneja una factura pagada en Stripe"""
    # Buscar usuario por customer ID
    customer_id = stripe_invoice.get('customer')
    
    # Aquí buscarías el usuario por su stripe_customer_id
    # user = User.query.filter_by(stripe_customer_id=customer_id).first()
    pass

def handle_stripe_subscription_created(subscription):
    """Maneja una nueva suscripción en Stripe"""
    customer_id = subscription.get('customer')
    
    # Actualizar plan del usuario
    # user = User.query.filter_by(stripe_customer_id=customer_id).first()
    # if user:
    #     user.plan = determine_plan_from_price(subscription['items']['data'][0]['price']['id'])
    #     user.subscription_id = subscription['id']
    #     user.subscription_status = 'active'
    #     db.session.commit()
    pass

def handle_stripe_subscription_cancelled(subscription):
    """Maneja una suscripción cancelada en Stripe"""
    customer_id = subscription.get('customer')
    
    # Downgrade a plan gratuito
    # user = User.query.filter_by(stripe_customer_id=customer_id).first()
    # if user:
    #     user.plan = 'free'
    #     user.subscription_status = 'cancelled'
    #     db.session.commit()
    pass

def handle_whatsapp_message(message):
    """Procesa un mensaje de WhatsApp"""
    from_number = message['from']
    message_type = message['type']
    
    if message_type == 'text':
        text = message['text']['body'].lower()
        
        # Comandos simples
        if text in ['menu', 'menú']:
            send_whatsapp_menu(from_number)
        elif text.startswith('pedido'):
            # Crear pedido por WhatsApp
            create_order_from_whatsapp(from_number, text)
        elif text == 'estado':
            send_order_status_whatsapp(from_number)
        else:
            # Mensaje de ayuda
            send_whatsapp_help(from_number)
    
    elif message_type == 'button':
        # Respuesta a botón
        button_payload = message['button']['payload']
        handle_whatsapp_button(from_number, button_payload)

def handle_external_order_created(data):
    """Maneja la creación de un pedido desde una fuente externa"""
    # Buscar usuario por API key o ID
    user_id = data.get('user_id')
    user = User.query.get(user_id)
    
    if not user:
        return
    
    # Crear pedido
    order = Order(
        user_id=user.id,
        customer_name=data.get('customer_name'),
        customer_phone=data.get('customer_phone'),
        delivery_address=data.get('delivery_address'),
        total=data.get('total', 0),
        external_id=data.get('external_id'),
        source='webhook'
    )
    
    db.session.add(order)
    db.session.commit()
    
    # Notificar al usuario
    notify_new_order(order)

def handle_external_product_update(data):
    """Maneja actualización de producto desde fuente externa"""
    product_id = data.get('product_id')
    sku = data.get('sku')
    
    # Buscar producto
    if product_id:
        product = Product.query.get(product_id)
    elif sku:
        product = Product.query.filter_by(sku=sku).first()
    else:
        return
    
    if product:
        # Actualizar campos permitidos
        if 'price' in data:
            product.price = data['price']
        if 'stock' in data:
            product.stock = data['stock']
        if 'name' in data:
            product.name = data['name']
        
        db.session.commit()

def handle_external_inventory_alert(data):
    """Maneja alertas de inventario externas"""
    from app.models.inventory import StockAlert
    
    user_id = data.get('user_id')
    product_id = data.get('product_id')
    alert_type = data.get('alert_type', 'low_stock')
    
    # Crear alerta
    alert = StockAlert(
        user_id=user_id,
        product_id=product_id,
        alert_type=alert_type,
        message=data.get('message', 'Alerta de inventario externa')
    )
    
    db.session.add(alert)
    db.session.commit()

# Funciones auxiliares

def generate_webhook_signature(webhook_id, payload):
    """Genera firma para verificar webhooks"""
    secret = current_app.config.get('WEBHOOK_SECRET', 'default-secret')
    message = f"{webhook_id}:{payload}"
    
    return hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def notify_payment_received(order):
    """Notifica que se recibió un pago"""
    # Aquí enviarías notificación por email, SMS, etc.
    current_app.logger.info(f"Payment received for order {order.id}")

def notify_new_order(order):
    """Notifica un nuevo pedido"""
    current_app.logger.info(f"New order created via webhook: {order.id}")

def send_whatsapp_menu(phone_number):
    """Envía el menú por WhatsApp"""
    # Implementar envío usando WhatsApp Business API
    pass

def send_whatsapp_help(phone_number):
    """Envía mensaje de ayuda por WhatsApp"""
    pass

def send_order_status_whatsapp(phone_number):
    """Envía estado del último pedido por WhatsApp"""
    pass

def create_order_from_whatsapp(phone_number, message):
    """Crea un pedido desde WhatsApp"""
    pass

def handle_whatsapp_button(phone_number, payload):
    """Maneja respuesta de botón de WhatsApp"""
    pass

# Endpoint de verificación para configuración

@bp.route('/verify', methods=['POST'])
def verify_webhook():
    """
    Endpoint para verificar que los webhooks funcionan
    Útil para configuración inicial
    """
    data = request.get_json()
    
    return jsonify({
        'status': 'success',
        'message': 'Webhook endpoint is working',
        'timestamp': datetime.utcnow().isoformat(),
        'received_data': data
    }), 200
