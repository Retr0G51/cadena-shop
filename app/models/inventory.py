"""
Modelo de Inventario para PedidosSaaS
Control avanzado de stock, movimientos, alertas y trazabilidad
"""
from datetime import datetime
from decimal import Decimal
from app.extensions import db
from sqlalchemy.orm import validates

class Warehouse(db.Model):
    """Almacenes o ubicaciones de inventario"""
    __tablename__ = 'warehouses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True)
    address = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    stock_items = db.relationship('StockItem', backref='warehouse', lazy='dynamic')
    movements = db.relationship(
    'InventoryMovement',
    foreign_keys='InventoryMovement.warehouse_id',
    backref='warehouse',
    lazy='dynamic'
)
    
    def __repr__(self):
        return f'<Warehouse {self.name}>'


class StockItem(db.Model):
    """Stock por producto y almacén"""
    __tablename__ = 'stock_items'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    
    # Cantidades
    quantity = db.Column(db.Numeric(10, 2), default=0)
    reserved_quantity = db.Column(db.Numeric(10, 2), default=0)  # Reservado para pedidos
    
    # Control de stock
    min_stock = db.Column(db.Numeric(10, 2), default=0)
    max_stock = db.Column(db.Numeric(10, 2))
    reorder_point = db.Column(db.Numeric(10, 2))  # Punto de reorden
    
    # Costos
    average_cost = db.Column(db.Numeric(10, 2), default=0)
    last_cost = db.Column(db.Numeric(10, 2), default=0)
    
    # Timestamps
    last_movement_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Índice único
    __table_args__ = (
        db.UniqueConstraint('product_id', 'warehouse_id', name='_product_warehouse_uc'),
    )
    
    @property
    def available_quantity(self):
        """Cantidad disponible (no reservada)"""
        return self.quantity - self.reserved_quantity
    
    @property
    def needs_reorder(self):
        """Verifica si necesita reorden"""
        if self.reorder_point:
            return self.available_quantity <= self.reorder_point
        return self.available_quantity <= self.min_stock
    
    def reserve(self, quantity):
        """Reserva cantidad para un pedido"""
        if quantity > self.available_quantity:
            raise ValueError("Cantidad insuficiente para reservar")
        self.reserved_quantity += quantity
    
    def release_reservation(self, quantity):
        """Libera cantidad reservada"""
        self.reserved_quantity = max(0, self.reserved_quantity - quantity)
    
    def __repr__(self):
        return f'<StockItem Product:{self.product_id} Warehouse:{self.warehouse_id} Qty:{self.quantity}>'


class InventoryMovement(db.Model):
    """Movimientos de inventario"""
    __tablename__ = 'inventory_movements'
    
    id = db.Column(db.Integer, primary_key=True)
    movement_type = db.Column(db.String(20), nullable=False)  # in, out, transfer, adjustment
    reference_type = db.Column(db.String(20))  # order, purchase, manual, return
    reference_id = db.Column(db.Integer)  # ID del pedido, compra, etc.
    
    # Producto y cantidad
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    unit_cost = db.Column(db.Numeric(10, 2))
    
    # Ubicaciones
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    destination_warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'))  # Para transferencias
    
    # Stock antes y después
    stock_before = db.Column(db.Numeric(10, 2))
    stock_after = db.Column(db.Numeric(10, 2))
    
    # Información adicional
    reason = db.Column(db.String(200))
    notes = db.Column(db.Text)
    batch_number = db.Column(db.String(50))  # Número de lote
    expiry_date = db.Column(db.Date)  # Fecha de vencimiento
    
    # Usuario y timestamps
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    product = db.relationship('Product', backref='movements')
    
    @validates('quantity')
    def validate_quantity(self, key, quantity):
        """Valida que la cantidad sea positiva"""
        if quantity <= 0:
            raise ValueError("La cantidad debe ser positiva")
        return quantity
    
    def apply_movement(self):
        """Aplica el movimiento al stock"""
        stock_item = StockItem.query.filter_by(
            product_id=self.product_id,
            warehouse_id=self.warehouse_id
        ).first()
        
        if not stock_item:
            stock_item = StockItem(
                product_id=self.product_id,
                warehouse_id=self.warehouse_id
            )
            db.session.add(stock_item)
        
        # Guardar stock anterior
        self.stock_before = stock_item.quantity
        
        # Aplicar movimiento
        if self.movement_type == 'in':
            stock_item.quantity += self.quantity
            # Actualizar costo promedio
            if self.unit_cost:
                total_value = (stock_item.quantity * stock_item.average_cost) + (self.quantity * self.unit_cost)
                stock_item.average_cost = total_value / (stock_item.quantity + self.quantity)
                stock_item.last_cost = self.unit_cost
        
        elif self.movement_type == 'out':
            if stock_item.available_quantity < self.quantity:
                raise ValueError("Stock insuficiente")
            stock_item.quantity -= self.quantity
        
        elif self.movement_type == 'adjustment':
            # Ajuste directo
            stock_item.quantity = self.quantity
        
        elif self.movement_type == 'transfer':
            # Transferencia entre almacenes
            if stock_item.available_quantity < self.quantity:
                raise ValueError("Stock insuficiente para transferir")
            
            stock_item.quantity -= self.quantity
            
            # Crear stock en destino
            dest_stock = StockItem.query.filter_by(
                product_id=self.product_id,
                warehouse_id=self.destination_warehouse_id
            ).first()
            
            if not dest_stock:
                dest_stock = StockItem(
                    product_id=self.product_id,
                    warehouse_id=self.destination_warehouse_id
                )
                db.session.add(dest_stock)
            
            dest_stock.quantity += self.quantity
        
        # Guardar stock posterior
        self.stock_after = stock_item.quantity
        stock_item.last_movement_date = datetime.utcnow()
    
    def __repr__(self):
        return f'<InventoryMovement {self.movement_type} Product:{self.product_id} Qty:{self.quantity}>'


class StockAlert(db.Model):
    """Alertas de stock"""
    __tablename__ = 'stock_alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'))
    
    alert_type = db.Column(db.String(20), nullable=False)  # low_stock, overstock, expiring
    threshold_value = db.Column(db.Numeric(10, 2))
    current_value = db.Column(db.Numeric(10, 2))
    
    message = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    is_resolved = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime)
    resolved_at = db.Column(db.DateTime)
    
    # Relaciones
    product = db.relationship('Product', backref='stock_alerts')
    
    def mark_as_read(self):
        """Marca la alerta como leída"""
        self.is_read = True
        self.read_at = datetime.utcnow()
    
    def mark_as_resolved(self):
        """Marca la alerta como resuelta"""
        self.is_resolved = True
        self.resolved_at = datetime.utcnow()
    
    def __repr__(self):
        return f'<StockAlert {self.alert_type} Product:{self.product_id}>'


class PurchaseOrder(db.Model):
    """Órdenes de compra a proveedores"""
    __tablename__ = 'purchase_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    
    # Proveedor
    supplier_name = db.Column(db.String(100), nullable=False)
    supplier_contact = db.Column(db.String(100))
    supplier_phone = db.Column(db.String(20))
    supplier_email = db.Column(db.String(120))
    
    # Estado
    status = db.Column(db.String(20), default='draft')  # draft, sent, partial, completed, cancelled
    
    # Fechas
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    expected_date = db.Column(db.DateTime)
    received_date = db.Column(db.DateTime)
    
    # Totales
    subtotal = db.Column(db.Numeric(10, 2), default=0)
    tax_amount = db.Column(db.Numeric(10, 2), default=0)
    total = db.Column(db.Numeric(10, 2), default=0)
    
    # Notas
    notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    items = db.relationship('PurchaseOrderItem', backref='purchase_order', lazy='dynamic', cascade='all, delete-orphan')
    
    def generate_order_number(self):
        """Genera número de orden de compra"""
        timestamp = datetime.utcnow().strftime('%Y%m%d')
        count = PurchaseOrder.query.filter_by(user_id=self.user_id).count() + 1
        self.order_number = f"PO-{timestamp}-{count:04d}"
    
    def __repr__(self):
        return f'<PurchaseOrder {self.order_number}>'


class PurchaseOrderItem(db.Model):
    """Items de órdenes de compra"""
    __tablename__ = 'purchase_order_items'
    
    id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    
    quantity_ordered = db.Column(db.Numeric(10, 2), nullable=False)
    quantity_received = db.Column(db.Numeric(10, 2), default=0)
    unit_cost = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Relaciones
    product = db.relationship('Product', backref='purchase_items')
    
    @property
    def is_complete(self):
        """Verifica si el item está completo"""
        return self.quantity_received >= self.quantity_ordered
    
    def __repr__(self):
        return f'<PurchaseOrderItem Product:{self.product_id} Qty:{self.quantity_ordered}>'
