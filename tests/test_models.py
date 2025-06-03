import pytest
from app.models import User, Product, Order, OrderItem

def test_user_creation(app):
    """Test user model creation"""
    with app.app_context():
        user = User(
            business_name='Test Panadería',
            email='test@panaderia.com',
            phone='+53 5555-5555'
        )
        user.set_password('testpass123')
        
        db.session.add(user)
        db.session.commit()
        
        assert user.id is not None
        assert user.slug == 'test-panaderia'
        assert user.check_password('testpass123') is True
        assert user.check_password('wrongpass') is False

def test_unique_slug_generation(app):
    """Test that slugs are unique"""
    with app.app_context():
        # Create first user
        user1 = User(
            business_name='Mi Negocio',
            email='user1@example.com',
            phone='+53 5555-5555'
        )
        user1.set_password('pass1')
        db.session.add(user1)
        db.session.commit()
        
        # Create second user with same business name
        user2 = User(
            business_name='Mi Negocio',
            email='user2@example.com',
            phone='+53 5555-5556'
        )
        user2.set_password('pass2')
        db.session.add(user2)
        db.session.commit()
        
        assert user1.slug == 'mi-negocio'
        assert user2.slug == 'mi-negocio-1'

def test_product_creation(app):
    """Test product model creation"""
    with app.app_context():
        user = User(
            business_name='Test Business',
            email='test@example.com',
            phone='+53 5555-5555'
        )
        user.set_password('testpass')
        db.session.add(user)
        db.session.commit()
        
        product = Product(
            name='Pan Francés',
            description='Pan recién horneado',
            price=5.50,
            stock=100,
            user_id=user.id
        )
        db.session.add(product)
        db.session.commit()
        
        assert product.id is not None
        assert product.owner == user
        assert product.in_stock is True

def test_order_creation(app):
    """Test order model creation"""
    with app.app_context():
        # Create user and product
        user = User(
            business_name='Test Business',
            email='test@example.com',
            phone='+53 5555-5555'
        )
        user.set_password('testpass')
        db.session.add(user)
        
        product = Product(
            name='Test Product',
            price=10.00,
            stock=50,
            user_id=1
        )
        db.session.add(product)
        db.session.commit()
        
        # Create order
        order = Order(
            customer_name='Juan Pérez',
            customer_phone='+53 5555-9999',
            delivery_address='Calle 23 #456',
            user_id=user.id
        )
        db.session.add(order)
        db.session.commit()
        
        # Add order item
        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=2
        )
        db.session.add(order_item)
        db.session.commit()
        
        order.calculate_totals()
        db.session.commit()
        
        assert order.order_number is not None
        assert order.items.count() == 1
        assert order.total == 20.00
