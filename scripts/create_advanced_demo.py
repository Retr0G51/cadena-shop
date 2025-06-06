#!/usr/bin/env python
"""
Script para crear datos de demostración avanzados
Incluye facturas, inventario, clientes CRM y más
"""
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
import random
import json

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Product, Order, OrderItem
from app.models.invoice import Invoice, InvoiceSeries, InvoiceItem, RecurringInvoice
from app.models.inventory import Warehouse, StockItem, InventoryMovement, PurchaseOrder, PurchaseOrderItem
from app.models.customer import Customer, CustomerGroup, CustomerInteraction, MarketingCampaign, LoyaltyProgram
from werkzeug.security import generate_password_hash

# Datos de ejemplo
CUSTOMER_NAMES = [
    "Juan Pérez", "María García", "Carlos López", "Ana Martínez", "Luis Rodríguez",
    "Laura Hernández", "José González", "Carmen Sánchez", "Francisco Díaz", "Isabel Ruiz",
    "Manuel Torres", "Rosa Jiménez", "Antonio Moreno", "Teresa Álvarez", "Pedro Romero",
    "Dolores Gil", "Javier Serrano", "Lucía Blanco", "Miguel Castro", "Elena Ortiz"
]

BUSINESS_NAMES = [
    "Restaurante El Sabor", "Cafetería Central", "Panadería La Esquina",
    "Comida Rápida Express", "Pizzería Bella Italia"
]

INTERACTION_SUBJECTS = [
    "Consulta sobre pedido", "Felicitación por servicio", "Sugerencia de mejora",
    "Problema con entrega", "Solicitud de factura", "Cambio de dirección"
]

CAMPAIGN_NAMES = [
    "Descuento de Temporada", "Bienvenida Nuevos Clientes", "Fidelización VIP",
    "Reactivación de Clientes", "Lanzamiento Nuevo Producto"
]

def create_demo_user():
    """Crea usuario de demostración"""
    demo_user = User.query.filter_by(email='demo@pedidossaas.com').first()
    
    if not demo_user:
        demo_user = User(
            email='demo@pedidossaas.com',
            password_hash=generate_password_hash('demo123'),
            business_name='Demo Restaurant Premium',
            phone='+34600123456',
            address='Calle Principal 123, Madrid',
            is_active=True,
            plan='premium',
            trial_ends=datetime.utcnow() + timedelta(days=365)
        )
        db.session.add(demo_user)
        db.session.commit()
        print("✓ Usuario demo creado")
    else:
        print("✓ Usuario demo ya existe")
    
    return demo_user

def create_warehouses(user):
    """Crea almacenes de ejemplo"""
    warehouses = []
    
    warehouse_data = [
        {"name": "Almacén Principal", "code": "MAIN", "is_default": True},
        {"name": "Almacén Secundario", "code": "SEC", "is_default": False},
        {"name": "Almacén Refrigerado", "code": "COLD", "is_default": False}
    ]
    
    for data in warehouse_data:
        warehouse = Warehouse.query.filter_by(
            user_id=user.id,
            code=data['code']
        ).first()
        
        if not warehouse:
            warehouse = Warehouse(
                user_id=user.id,
                name=data['name'],
                code=data['code'],
                address=f"{data['name']}, {user.address}",
                is_default=data['is_default']
            )
            db.session.add(warehouse)
            warehouses.append(warehouse)
    
    db.session.commit()
    print(f"✓ {len(warehouses)} almacenes creados")
    return warehouses

def create_products_with_stock(user, warehouses):
    """Crea productos con stock inicial"""
    categories = ['Bebidas', 'Comidas', 'Postres', 'Aperitivos', 'Especiales']
    products = []
    
    product_data = [
        # Bebidas
        {"name": "Coca Cola 355ml", "category": "Bebidas", "price": 25.00, "stock": 100},
        {"name": "Agua Mineral 500ml", "category": "Bebidas", "price": 15.00, "stock": 150},
        {"name": "Jugo Natural", "category": "Bebidas", "price": 35.00, "stock": 50},
        {"name": "Café Americano", "category": "Bebidas", "price": 30.00, "stock": 200},
        {"name": "Té Verde", "category": "Bebidas", "price": 25.00, "stock": 80},
        
        # Comidas
        {"name": "Hamburguesa Clásica", "category": "Comidas", "price": 85.00, "stock": 60},
        {"name": "Pizza Margarita", "category": "Comidas", "price": 120.00, "stock": 40},
        {"name": "Ensalada César", "category": "Comidas", "price": 75.00, "stock": 30},
        {"name": "Sandwich Club", "category": "Comidas", "price": 65.00, "stock": 50},
        {"name": "Pasta Alfredo", "category": "Comidas", "price": 95.00, "stock": 35},
        
        # Postres
        {"name": "Tarta de Chocolate", "category": "Postres", "price": 45.00, "stock": 25},
        {"name": "Helado Vainilla", "category": "Postres", "price": 35.00, "stock": 40},
        {"name": "Flan Casero", "category": "Postres", "price": 30.00, "stock": 30},
        {"name": "Brownie con Helado", "category": "Postres", "price": 55.00, "stock": 20},
        {"name": "Cheesecake", "category": "Postres", "price": 60.00, "stock": 15},
        
        # Aperitivos
        {"name": "Nachos con Queso", "category": "Aperitivos", "price": 45.00, "stock": 50},
        {"name": "Alitas BBQ", "category": "Aperitivos", "price": 65.00, "stock": 40},
        {"name": "Papas Fritas", "category": "Aperitivos", "price": 35.00, "stock": 60},
        {"name": "Aros de Cebolla", "category": "Aperitivos", "price": 40.00, "stock": 45},
        {"name": "Quesadilla", "category": "Aperitivos", "price": 55.00, "stock": 35}
    ]
    
    for data in product_data:
        product = Product.query.filter_by(
            user_id=user.id,
            name=data['name']
        ).first()
        
        if not product:
            product = Product(
                user_id=user.id,
                name=data['name'],
                description=f"{data['name']} - {data['category']}",
                price=Decimal(str(data['price'])),
                category=data['category'],
                is_active=True,
                track_stock=True
            )
            db.session.add(product)
            db.session.flush()
            
            # Crear stock inicial en almacén principal
            main_warehouse = next(w for w in warehouses if w.is_default)
            stock_item = StockItem(
                product_id=product.id,
                warehouse_id=main_warehouse.id,
                quantity=Decimal(str(data['stock'])),
                min_stock=Decimal('10'),
                reorder_point=Decimal('20'),
                average_cost=Decimal(str(data['price'] * 0.6))  # 60% del precio de venta
            )
            db.session.add(stock_item)
            
            # Movimiento inicial
            movement = InventoryMovement(
                user_id=user.id,
                product_id=product.id,
                warehouse_id=main_warehouse.id,
                movement_type='in',
                reference_type='manual',
                quantity=Decimal(str(data['stock'])),
                unit_cost=stock_item.average_cost,
                reason='Stock inicial',
                created_by=user.id
            )
            db.session.add(movement)
            
            products.append(product)
    
    db.session.commit()
    print(f"✓ {len(products)} productos con stock creados")
    return Product.query.filter_by(user_id=user.id).all()

def create_customers(user):
    """Crea clientes con información completa"""
    customers = []
    
    for i, name in enumerate(CUSTOMER_NAMES):
        phone = f"+346{str(i).zfill(8)}"
        
        customer = Customer.query.filter_by(
            user_id=user.id,
            phone=phone
        ).first()
        
        if not customer:
            customer = Customer(
                user_id=user.id,
                name=name,
                email=f"{name.lower().replace(' ', '.')}@email.com",
                phone=phone,
                address=f"Calle {i+1}, Número {(i+1)*10}, Madrid",
                city="Madrid",
                postal_code=f"280{str(i).zfill(2)}",
                customer_type='individual' if i % 5 != 0 else 'company',
                segment='new',
                accepts_marketing=i % 3 != 0,
                notes=f"Cliente desde {datetime.utcnow().strftime('%Y')}"
            )
            
            if customer.customer_type == 'company':
                customer.company_name = f"Empresa de {name}"
                customer.tax_id = f"B{str(i).zfill(8)}"
            
            db.session.add(customer)
            customers.append(customer)
    
    db.session.commit()
    print(f"✓ {len(customers)} clientes creados")
    return customers

def create_customer_groups(user):
    """Crea grupos de clientes"""
    groups = []
    
    group_data = [
        {
            "name": "VIP",
            "description": "Clientes con más de 1000€ en compras",
            "discount_rate": Decimal('10'),
            "priority_support": True
        },
        {
            "name": "Nuevos Clientes",
            "description": "Clientes registrados en los últimos 30 días",
            "discount_rate": Decimal('5'),
            "priority_support": False
        },
        {
            "name": "Clientes Frecuentes",
            "description": "Más de 5 pedidos al mes",
            "discount_rate": Decimal('7'),
            "priority_support": True
        }
    ]
    
    for data in group_data:
        group = CustomerGroup.query.filter_by(
            user_id=user.id,
            name=data['name']
        ).first()
        
        if not group:
            group = CustomerGroup(
                user_id=user.id,
                name=data['name'],
                description=data['description'],
                discount_rate=data['discount_rate'],
                priority_support=data['priority_support']
            )
            db.session.add(group)
            groups.append(group)
    
    db.session.commit()
    print(f"✓ {len(groups)} grupos de clientes creados")
    return groups

def create_orders_and_invoices(user, products, customers, warehouses):
    """Crea pedidos e facturas históricas"""
    orders = []
    invoices = []
    
    # Crear serie de facturación
    series = InvoiceSeries.query.filter_by(user_id=user.id).first()
    if not series:
        series = InvoiceSeries(
            user_id=user.id,
            prefix='FAC',
            current_number=0
        )
        db.session.add(series)
        db.session.flush()
    
    # Crear pedidos para los últimos 90 días
    for day in range(90):
        date = datetime.utcnow() - timedelta(days=day)
        num_orders = random.randint(5, 15)
        
        for _ in range(num_orders):
            customer = random.choice(customers)
            
            # Crear pedido
            order = Order(
                user_id=user.id,
                customer_name=customer.name,
                customer_phone=customer.phone,
                delivery_address=customer.address,
                status=random.choice(['delivered', 'delivered', 'delivered', 'pending', 'cancelled']),
                payment_method=random.choice(['cash', 'card', 'transfer']),
                notes=f"Pedido del {date.strftime('%d/%m/%Y')}",
                created_at=date,
                updated_at=date
            )
            
            # Agregar items
            num_items = random.randint(1, 5)
            selected_products = random.sample(products, num_items)
            
            for product in selected_products:
                quantity = random.randint(1, 3)
                item = OrderItem(
                    product_id=product.id,
                    quantity=quantity,
                    unit_price=product.price,
                    subtotal=product.price * quantity
                )
                order.items.append(item)
                
                # Actualizar stock si el pedido está completado
                if order.status == 'delivered':
                    main_warehouse = next(w for w in warehouses if w.is_default)
                    movement = InventoryMovement(
                        user_id=user.id,
                        product_id=product.id,
                        warehouse_id=main_warehouse.id,
                        movement_type='out',
                        reference_type='order',
                        reference_id=order.id,
                        quantity=quantity,
                        reason='Venta',
                        created_by=user.id,
                        created_at=date
                    )
                    db.session.add(movement)
            
            order.calculate_total()
            db.session.add(order)
            orders.append(order)
            
            # Crear factura para algunos pedidos completados
            if order.status == 'delivered' and random.random() > 0.3:
                invoice = Invoice(
                    user_id=user.id,
                    series_id=series.id,
                    invoice_number=series.get_next_number(),
                    order_id=order.id,
                    customer_name=customer.name,
                    customer_tax_id=customer.tax_id,
                    customer_address=customer.address,
                    customer_email=customer.email,
                    customer_phone=customer.phone,
                    tax_rate=Decimal('18'),
                    status='paid' if random.random() > 0.2 else 'issued',
                    payment_method=order.payment_method,
                    issued_at=date,
                    due_date=date + timedelta(days=30),
                    created_at=date
                )
                
                # Copiar items del pedido
                for order_item in order.items:
                    invoice_item = InvoiceItem(
                        description=order_item.product.name,
                        quantity=order_item.quantity,
                        unit_price=order_item.unit_price,
                        product_id=order_item.product_id
                    )
                    invoice_item.calculate_subtotal()
                    invoice.items.append(invoice_item)
                
                invoice.calculate_totals()
                
                if invoice.status == 'paid':
                    invoice.payment_date = date + timedelta(days=random.randint(1, 15))
                
                db.session.add(invoice)
                invoices.append(invoice)
            
            # Actualizar métricas del cliente
            customer.total_orders += 1
            if order.status == 'delivered':
                customer.total_spent += order.total
                customer.last_order_date = date
    
    db.session.commit()
    print(f"✓ {len(orders)} pedidos y {len(invoices)} facturas creados")
    return orders, invoices

def create_purchase_orders(user, products, warehouses):
    """Crea órdenes de compra"""
    purchase_orders = []
    
    suppliers = [
        "Distribuidora Central S.A.",
        "Proveedores Unidos Ltd.",
        "Importadora Global",
        "Suministros Express",
        "Mayorista Nacional"
    ]
    
    for i in range(10):
        po = PurchaseOrder(
            user_id=user.id,
            supplier_name=random.choice(suppliers),
            supplier_contact=f"Contacto {i+1}",
            supplier_phone=f"+346{str(i).zfill(8)}",
            supplier_email=f"compras{i+1}@proveedor.com",
            status=random.choice(['draft', 'sent', 'completed', 'completed']),
            order_date=datetime.utcnow() - timedelta(days=random.randint(1, 60)),
            expected_date=datetime.utcnow() + timedelta(days=random.randint(7, 21))
        )
        po.generate_order_number()
        
        # Agregar items
        num_items = random.randint(3, 8)
        selected_products = random.sample(products, num_items)
        
        for product in selected_products:
            quantity = random.randint(50, 200)
            unit_cost = product.price * Decimal('0.6')  # 60% del precio de venta
            
            item = PurchaseOrderItem(
                product_id=product.id,
                quantity_ordered=quantity,
                unit_cost=unit_cost,
                subtotal=quantity * unit_cost
            )
            
            if po.status == 'completed':
                item.quantity_received = quantity
                po.received_date = po.order_date + timedelta(days=random.randint(3, 10))
            
            po.items.append(item)
        
        # Calcular totales
        po.subtotal = sum(item.subtotal for item in po.items)
        po.tax_amount = po.subtotal * Decimal('0.18')
        po.total = po.subtotal + po.tax_amount
        
        db.session.add(po)
        purchase_orders.append(po)
    
    db.session.commit()
    print(f"✓ {len(purchase_orders)} órdenes de compra creadas")
    return purchase_orders

def create_customer_interactions(user, customers):
    """Crea interacciones con clientes"""
    interactions = []
    
    for customer in random.sample(customers, min(15, len(customers))):
        num_interactions = random.randint(1, 5)
        
        for _ in range(num_interactions):
            interaction = CustomerInteraction(
                customer_id=customer.id,
                user_id=user.id,
                created_by=user.id,
                interaction_type=random.choice(['call', 'email', 'visit', 'note']),
                channel=random.choice(['phone', 'email', 'whatsapp', 'in_person']),
                subject=random.choice(INTERACTION_SUBJECTS),
                content=f"Interacción de ejemplo con {customer.name}",
                created_at=datetime.utcnow() - timedelta(days=random.randint(1, 30))
            )
            db.session.add(interaction)
            interactions.append(interaction)
    
    db.session.commit()
    print(f"✓ {len(interactions)} interacciones creadas")
    return interactions

def create_marketing_campaigns(user, groups):
    """Crea campañas de marketing"""
    campaigns = []
    
    for i, name in enumerate(CAMPAIGN_NAMES[:3]):
        campaign = MarketingCampaign(
            user_id=user.id,
            name=name,
            description=f"Campaña de ejemplo: {name}",
            campaign_type='email',
            subject=f"¡{name} - Oferta Especial!",
            content=f"Contenido de la campaña {name}. Use {{customer_name}} para personalizar.",
            target_group_id=random.choice(groups).id if groups else None,
            discount_percentage=Decimal(str(random.choice([5, 10, 15, 20]))),
            status='completed',
            scheduled_at=datetime.utcnow() - timedelta(days=random.randint(10, 30)),
            sent_at=datetime.utcnow() - timedelta(days=random.randint(5, 25)),
            expires_at=datetime.utcnow() + timedelta(days=random.randint(15, 45)),
            total_recipients=random.randint(50, 200),
            total_sent=random.randint(45, 195),
            total_opened=random.randint(20, 100),
            total_clicked=random.randint(5, 50),
            total_converted=random.randint(1, 20),
            revenue_generated=Decimal(str(random.randint(500, 5000)))
        )
        db.session.add(campaign)
        campaigns.append(campaign)
    
    db.session.commit()
    print(f"✓ {len(campaigns)} campañas de marketing creadas")
    return campaigns

def create_recurring_invoices(user, customers):
    """Crea facturas recurrentes"""
    recurring = []
    
    # Seleccionar algunos clientes para facturas recurrentes
    recurring_customers = random.sample(customers, min(5, len(customers)))
    
    for customer in recurring_customers:
        items_json = [
            {
                'description': 'Servicio mensual de catering',
                'quantity': 1,
                'unit_price': random.randint(500, 2000),
                'discount_rate': 0
            }
        ]
        
        recurring_invoice = RecurringInvoice(
            user_id=user.id,
            template_name=f"Factura mensual - {customer.name}",
            customer_name=customer.name,
            customer_tax_id=customer.tax_id,
            customer_address=customer.address,
            customer_email=customer.email,
            items_json=items_json,
            frequency='monthly',
            interval=1,
            day_of_month=random.randint(1, 28),
            is_active=True,
            next_issue_date=datetime.utcnow() + timedelta(days=random.randint(1, 30)),
            tax_rate=Decimal('18')
        )
        db.session.add(recurring_invoice)
        recurring.append(recurring_invoice)
    
    db.session.commit()
    print(f"✓ {len(recurring)} facturas recurrentes creadas")
    return recurring

def create_loyalty_program(user):
    """Crea programa de lealtad"""
    program = LoyaltyProgram.query.filter_by(user_id=user.id).first()
    
    if not program:
        program = LoyaltyProgram(
            user_id=user.id,
            name="Programa de Puntos Premium",
            description="Gana 1 punto por cada € gastado. Canjea desde 100 puntos.",
            points_per_currency=1,
            points_to_currency_rate=Decimal('0.01'),
            min_points_to_redeem=100,
            points_expiry_days=365
        )
        db.session.add(program)
        db.session.commit()
        print("✓ Programa de lealtad creado")
    
    return program

def update_customer_segments(customers):
    """Actualiza segmentación de clientes"""
    for customer in customers:
        customer.update_metrics()
        
        # Segmentación basada en gasto
        if customer.total_spent >= 1000:
            customer.segment = 'vip'
            customer.loyalty_points = int(customer.total_spent)
        elif customer.total_spent >= 500:
            customer.segment = 'premium'
            customer.loyalty_points = int(customer.total_spent * 0.8)
        elif customer.total_spent >= 100:
            customer.segment = 'regular'
            customer.loyalty_points = int(customer.total_spent * 0.5)
        else:
            customer.segment = 'new'
            customer.loyalty_points = 50  # Bonus de bienvenida
        
        # Agregar tags
        if customer.is_at_risk:
            customer.add_tag('at_risk')
        if customer.total_orders > 10:
            customer.add_tag('frequent')
        if customer.accepts_marketing:
            customer.add_tag('marketing_enabled')
    
    db.session.commit()
    print("✓ Segmentos de clientes actualizados")

def print_summary(user):
    """Imprime resumen de datos creados"""
    print("\n" + "="*50)
    print("RESUMEN DE DATOS DE DEMOSTRACIÓN")
    print("="*50)
    
    print(f"\nNegocio: {user.business_name}")
    print(f"Email: {user.email}")
    print(f"Contraseña: demo123")
    
    print(f"\nDatos creados:")
    print(f"- Productos: {Product.query.filter_by(user_id=user.id).count()}")
    print(f"- Clientes: {Customer.query.filter_by(user_id=user.id).count()}")
    print(f"- Pedidos: {Order.query.filter_by(user_id=user.id).count()}")
    print(f"- Facturas: {Invoice.query.filter_by(user_id=user.id).count()}")
    print(f"- Almacenes: {Warehouse.query.filter_by(user_id=user.id).count()}")
    print(f"- Órdenes de compra: {PurchaseOrder.query.filter_by(user_id=user.id).count()}")
    
    # Estadísticas
    total_revenue = db.session.query(db.func.sum(Order.total)).filter(
        Order.user_id == user.id,
        Order.status == 'delivered'
    ).scalar() or 0
    
    print(f"\nEstadísticas:")
    print(f"- Ingresos totales: €{total_revenue:,.2f}")
    print(f"- Clientes VIP: {Customer.query.filter_by(user_id=user.id, segment='vip').count()}")
    
    print("\n✓ Datos de demostración creados exitosamente!")
    print("Puedes acceder en: http://localhost:5000")
    print("="*50)

def main():
    """Función principal"""
    app = create_app()
    
    with app.app_context():
        print("Creando datos de demostración avanzados...")
        
        # Crear usuario
        user = create_demo_user()
        
        # Crear estructura base
        warehouses = create_warehouses(user)
        products = create_products_with_stock(user, warehouses)
        customers = create_customers(user)
        groups = create_customer_groups(user)
        
        # Asignar algunos clientes a grupos
        vip_group = next(g for g in groups if g.name == 'VIP')
        for customer in random.sample(customers, 5):
            customer.groups.append(vip_group)
        
        # Crear transacciones
        orders, invoices = create_orders_and_invoices(user, products, customers, warehouses)
        purchase_orders = create_purchase_orders(user, products, warehouses)
        
        # Crear interacciones y marketing
        interactions = create_customer_interactions(user, customers)
        campaigns = create_marketing_campaigns(user, groups)
        recurring = create_recurring_invoices(user, customers)
        
        # Crear programa de lealtad
        loyalty_program = create_loyalty_program(user)
        
        # Actualizar segmentos
        update_customer_segments(customers)
        
        # Mostrar resumen
        print_summary(user)

if __name__ == '__main__':
    main()
