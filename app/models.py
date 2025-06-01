from datetime import datetime
from flask_login import UserMixin
from slugify import slugify
import bcrypt
from app.extensions import db, login_manager

# Tabla asociativa para la relación muchos a muchos entre Order y Product
order_products = db.Table('order_products',
    db.Column('order_id', db.Integer, db.ForeignKey('orders.id'), primary_key=True),
    db.Column('product_id', db.Integer, db.ForeignKey('products.id'), primary_key=True),
    db.Column('quantity', db.Integer, default=1),
    db.Column('price_at_time', db.Decimal(10, 2))  # Precio al momento de la compra
)

class User(UserMixin, db.Model):
    """
    Modelo de Usuario (Dueño del negocio)
    Cada usuario representa un negocio con su propia tienda
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
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Estado
    is_active = db.Column(db.Boolean, default=True)
    
    # Relaciones
    products = db.relationship('Product', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='business', lazy='dynamic', cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        # Generar slug único basado en el nombre del negocio
        if self.business_name and not self.slug:
            self.slug = self._generate_unique_slug()
    
    def _generate_unique_slug(self):
        """Genera un slug único para la URL del negocio"""
        base_slug = slugify(self.business_name)
        slug = base_slug
        counter = 1
        
        # Asegurar que el slug sea único
        while User.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        return slug
    
    def set_password(self, password):
        """Hashea y guarda la contraseña"""
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def check_password(self, password):
        """Verifica si la contraseña es correcta"""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def __repr__(self):
        return f'<User {self.business_name}>'

class Product(db.Model):
    """
    Modelo de Producto
    Cada producto pertenece a un negocio (usuario)
    """
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Decimal(10, 2), nullable=False)
    stock = db.Column(db.Integer, default=0)
    image = db.Column(db.String(200))  # Ruta de la imagen
    
    # Estado
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign Key
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    def __repr__(self):
        return f'<Product {self.name}>'
    
    @property
    def is_available(self):
        """Verifica si el producto está disponible para vender"""
        return self.is_active and self.stock > 0

class Order(db.Model):
    """
    Modelo de Pedido
    Los pedidos son realizados por clientes en las tiendas
    """
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    
    # Información del cliente
    customer_name = db.Column(db.String(100), nullable=False)
    customer_email = db.Column(db.String(120))
    customer_phone = db.Column(db.String(20), nullable=False)
    delivery_address = db.Column(db.Text)
    notes = db.Column(db.Text)
    
    # Estado del pedido
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, preparing, ready, delivered, cancelled
    
    # Totales
    total = db.Column(db.Decimal(10, 2), default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign Key
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relación muchos a muchos con productos
    products = db.relationship('Product', secondary=order_products, backref='orders')
    
    def __init__(self, **kwargs):
        super(Order, self).__init__(**kwargs)
        if not self.order_number:
            self.order_number = self._generate_order_number()
    
    def _generate_order_number(self):
        """Genera un número de orden único"""
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        return f"ORD-{timestamp}"
    
    def calculate_total(self):
        """Calcula el total del pedido basado en los productos"""
        total = 0
        # Aquí implementarías la lógica para calcular el total
        # basándote en los productos y cantidades
        self.total = total
        return total
    
    def __repr__(self):
        return f'<Order {self.order_number}>'
    
    @property
    def status_display(self):
        """Retorna el estado en español"""
        status_map = {
            'pending': 'Pendiente',
            'confirmed': 'Confirmado',
            'preparing': 'En preparación',
            'ready': 'Listo',
            'delivered': 'Entregado',
            'cancelled': 'Cancelado'
        }
        return status_map.get(self.status, self.status)

# Callback para cargar usuario
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
