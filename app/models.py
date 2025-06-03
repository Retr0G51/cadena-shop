from datetime import datetime
from flask_login import UserMixin
from slugify import slugify
from app.extensions import db, bcrypt

class User(UserMixin, db.Model):
    """
    Modelo de Usuario (Dueño del negocio)
    Cada usuario representa un negocio con su propia tienda online
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    business_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Información del negocio
    description = db.Column(db.Text)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    logo = db.Column(db.String(200))  # Path to logo image
    
    # Configuración
    is_active = db.Column(db.Boolean, default=True)
    accept_orders = db.Column(db.Boolean, default=True)
    currency = db.Column(db.String(3), default='CUP')
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    products = db.relationship('Product', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='business', lazy='dynamic', cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if not self.slug:
            self.slug = self.generate_unique_slug()
    
    def set_password(self, password):
        """Hashea y guarda la contraseña"""
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        """Verifica si la contraseña es correcta"""
        return bcrypt.check_password_hash(self.password_hash, password)
    
    def generate_unique_slug(self):
        """Genera un slug único basado en el nombre del negocio"""
        base_slug = slugify(self.business_name)
        slug = base_slug
        counter = 1
        
        while User.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        return slug
    
    def __repr__(self):
        return f'<User {self.business_name}>'


class Product(db.Model):
    """
    Modelo de Producto
    Cada producto pertenece a un usuario/negocio
    """
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Decimal(10, 2), nullable=False)
    stock = db.Column(db.Integer, default=0)
    image = db.Column(db.String(200))  # Path to product image
    
    # Estado del producto
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    
    # Categoría (opcional para futura expansión)
    category = db.Column(db.String(50))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign key
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relaciones
    order_items = db.relationship('OrderItem', backref='product', lazy='dynamic')
    
    @property
    def in_stock(self):
        """Verifica si el producto está en stock"""
        return self.stock > 0
    
    def __repr__(self):
        return f'<Product {self.name}>'


class Order(db.Model):
    """
    Modelo de Pedido
    Representa un pedido realizado por un cliente
    """
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    
    # Información del cliente
    customer_name = db.Column(db.String(100), nullable=False)
    customer_email = db.Column(db.String(120))
    customer_phone = db.Column(db.String(20), nullable=False)
    delivery_address = db.Column(db.Text)
    notes = db.Column(db.Text)
    
    # Estado del pedido
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, preparing, ready, delivered, cancelled
    payment_method = db.Column(db.String(20), default='cash')  # cash, transfer, card
    payment_status = db.Column(db.String(20), default='pending')  # pending, paid, refunded
    
    # Totales
    subtotal = db.Column(db.Decimal(10, 2), default=0)
    delivery_fee = db.Column(db.Decimal(10, 2), default=0)
    total = db.Column(db.Decimal(10, 2), default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    delivered_at = db.Column(db.DateTime)
    
    # Foreign key
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relaciones
    items = db.relationship('OrderItem', backref='order', lazy='dynamic', cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super(Order, self).__init__(**kwargs)
        if not self.order_number:
            self.order_number = self.generate_order_number()
    
    def generate_order_number(self):
        """Genera un número de orden único"""
        from random import randint
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M')
        random_suffix = randint(100, 999)
        return f"ORD-{timestamp}-{random_suffix}"
    
    def calculate_totals(self):
        """Calcula los totales del pedido"""
        self.subtotal = sum(item.subtotal for item in self.items)
        self.total = self.subtotal + self.delivery_fee
    
    def get_status_badge_class(self):
        """Retorna la clase CSS para el badge del estado"""
        status_classes = {
            'pending': 'bg-yellow-100 text-yellow-800',
            'confirmed': 'bg-blue-100 text-blue-800',
            'preparing': 'bg-purple-100 text-purple-800',
            'ready': 'bg-indigo-100 text-indigo-800',
            'delivered': 'bg-green-100 text-green-800',
            'cancelled': 'bg-red-100 text-red-800'
        }
        return status_classes.get(self.status, 'bg-gray-100 text-gray-800')
    
    def get_status_display(self):
        """Retorna el texto en español del estado"""
        status_display = {
            'pending': 'Pendiente',
            'confirmed': 'Confirmado',
            'preparing': 'Preparando',
            'ready': 'Listo',
            'delivered': 'Entregado',
            'cancelled': 'Cancelado'
        }
        return status_display.get(self.status, 'Desconocido')
    
    def __repr__(self):
        return f'<Order {self.order_number}>'


class OrderItem(db.Model):
    """
    Modelo de Item de Pedido
    Representa un producto dentro de un pedido
    """
    __tablename__ = 'order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Decimal(10, 2), nullable=False)
    subtotal = db.Column(db.Decimal(10, 2), nullable=False)
    notes = db.Column(db.String(200))
    
    # Foreign keys
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    
    def __init__(self, **kwargs):
        super(OrderItem, self).__init__(**kwargs)
        if self.product_id and self.quantity:
            product = Product.query.get(self.product_id)
            if product:
                self.unit_price = product.price
                self.subtotal = product.price * self.quantity
    
    def calculate_subtotal(self):
        """Calcula el subtotal del item"""
        self.subtotal = self.unit_price * self.quantity
    
    def __repr__(self):
        return f'<OrderItem {self.quantity}x Product:{self.product_id}>'
