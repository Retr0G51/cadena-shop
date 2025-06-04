"""
Sistema avanzado de gestión de inventario con seguimiento y alertas
"""

from datetime import datetime
from app.extensions import db
from sqlalchemy import event
from enum import Enum


class StockMovementType(Enum):
    """Tipos de movimientos de inventario"""
    PURCHASE = 'purchase'  # Compra/entrada
    SALE = 'sale'  # Venta
    ADJUSTMENT = 'adjustment'  # Ajuste manual
    RETURN = 'return'  # Devolución
    DAMAGE = 'damage'  # Daño/pérdida
    TRANSFER = 'transfer'  # Transferencia entre almacenes
    PRODUCTION = 'production'  # Producción (para productos elaborados)


class StockMovement(db.Model):
    """Registro de todos los movimientos de inventario"""
    __tablename__ = 'stock_movements'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Tipo y cantidad
    movement_type = db.Column(db.Enum(StockMovementType), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)  # Positivo = entrada, Negativo = salida
    
    # Stock antes y después
    stock_before = db.Column(db.Integer, nullable=False)
    stock_after = db.Column(db.Integer, nullable=False)
    
    # Costo (para calcular valor del inventario)
    unit_cost = db.Column(db.Numeric(10, 2))
    total_cost = db.Column(db.Numeric(10, 2))
    
    # Referencias
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey('order_items.id'), nullable=True)
    
    # Información adicional
    reference = db.Column(db.String(100))  # Número de factura, orden de compra, etc.
    notes = db.Column(db.Text)
    
    # Usuario que realizó el movimiento
    performed_by = db.Column(db.String(100))  # Nombre del usuario
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    product = db.relationship('Product', backref='stock_movements')
    business = db.relationship('User', backref='stock_movements')
    order = db.relationship('Order', backref='stock_movements')
    order_item = db.relationship('OrderItem', backref='stock_movements')
    
    @staticmethod
    def create_movement(product, movement_type, quantity, reference=None, notes=None, 
                       order=None, order_item=None, unit_cost=None):
        """Crea un movimiento de inventario y actualiza el stock del producto"""
        # Validar cantidad según tipo de movimiento
        if movement_type in [StockMovementType.SALE, StockMovementType.DAMAGE]:
            if quantity > 0:
                quantity = -quantity  # Asegurar que sea negativo para salidas
        
        # Crear movimiento
        movement = StockMovement(
            product_id=product.id,
            user_id=product.user_id,
            movement_type=movement_type,
            quantity=quantity,
            stock_before=product.stock,
            stock_after=product.stock + quantity,
            reference=reference,
            notes=notes,
            unit_cost=unit_cost or product.cost_price or 0,
            total_cost=(unit_cost or product.cost_price or 0) * abs(quantity),
            order_id=order.id if order else None,
            order_item_id=order_item.id if order_item else None,
            performed_by=current_user.business_name if hasattr(current_user, 'business_name') else 'Sistema'
        )
        
        # Actualizar stock del producto
        product.stock += quantity
        
        # Verificar alertas de stock bajo
        if product.stock <= product.min_stock:
            StockAlert.create_or_update_alert(product)
        
        db.session.add(movement)
        db.session.add(product)
        
        return movement


class StockAlert(db.Model):
    """Alertas de inventario bajo"""
    __tablename__ = 'stock_alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Estado de la alerta
    status = db.Column(db.String(20), default='active')  # active, resolved, ignored
    severity = db.Column(db.String(20), default='warning')  # info, warning, critical
    
    # Información de stock
    current_stock = db.Column(db.Integer)
    min_stock = db.Column(db.Integer)
    
    # Fechas
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    last_notified_at = db.Column(db.DateTime)
    
    # Relaciones
    product = db.relationship('Product', backref='stock_alerts')
    business = db.relationship('User', backref='stock_alerts')
    
    @staticmethod
    def create_or_update_alert(product):
        """Crea o actualiza una alerta de stock bajo"""
        # Buscar alerta activa existente
        alert = StockAlert.query.filter_by(
            product_id=product.id,
            status='active'
        ).first()
        
        if alert:
            # Actualizar alerta existente
            alert.current_stock = product.stock
            alert.min_stock = product.min_stock
            
            # Actualizar severidad
            if product.stock == 0:
                alert.severity = 'critical'
            elif product.stock <= product.min_stock * 0.5:
                alert.severity = 'warning'
            else:
                alert.severity = 'info'
        else:
            # Crear nueva alerta
            alert = StockAlert(
                product_id=product.id,
                user_id=product.user_id,
                current_stock=product.stock,
                min_stock=product.min_stock,
                severity='critical' if product.stock == 0 else 'warning'
            )
            db.session.add(alert)
        
        return alert


class InventoryValuation(db.Model):
    """Valoración del inventario en un momento dado"""
    __tablename__ = 'inventory_valuations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Fecha de la valoración
    valuation_date = db.Column(db.Date, nullable=False)
    
    # Totales
    total_items = db.Column(db.Integer, default=0)  # Cantidad total de items
    total_products = db.Column(db.Integer, default=0)  # Cantidad de productos diferentes
    total_value = db.Column(db.Numeric(12, 2), default=0)  # Valor total del inventario
    
    # Desglose por categorías (JSON)
    category_breakdown = db.Column(db.JSON)
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    business = db.relationship('User', backref='inventory_valuations')
    
    @staticmethod
    def calculate_current_valuation(user_id):
        """Calcula la valoración actual del inventario"""
        from app.models import Product
        
        # Obtener todos los productos activos con stock
        products = Product.query.filter(
            Product.user_id == user_id,
            Product.is_active == True,
            Product.stock > 0
        ).all()
        
        total_items = 0
        total_value = 0
        category_breakdown = {}
        
        for product in products:
            total_items += product.stock
            
            # Usar precio de costo si está disponible, sino usar precio de venta * 0.7
            cost = product.cost_price if hasattr(product, 'cost_price') and product.cost_price else product.price * 0.7
            product_value = product.stock * cost
            total_value += product_value
            
            # Agrupar por categoría
            category = product.category or 'Sin categoría'
            if category not in category_breakdown:
                category_breakdown[category] = {
                    'items': 0,
                    'value': 0,
                    'products': 0
                }
            
            category_breakdown[category]['items'] += product.stock
            category_breakdown[category]['value'] += float(product_value)
            category_breakdown[category]['products'] += 1
        
        return {
            'total_items': total_items,
            'total_products': len(products),
            'total_value': float(total_value),
            'category_breakdown': category_breakdown
        }


# Agregar campos adicionales al modelo Product existente
def extend_product_model():
    """Extiende el modelo Product con campos de inventario avanzado"""
    from app.models import Product
    
    # Agregar nuevos campos si no existen
    if not hasattr(Product, 'min_stock'):
        Product.min_stock = db.Column(db.Integer, default=10)
    
    if not hasattr(Product, 'max_stock'):
        Product.max_stock = db.Column(db.Integer, default=1000)
    
    if not hasattr(Product, 'reorder_point'):
        Product.reorder_point = db.Column(db.Integer, default=20)
    
    if not hasattr(Product, 'reorder_quantity'):
        Product.reorder_quantity = db.Column(db.Integer, default=50)
    
    if not hasattr(Product, 'cost_price'):
        Product.cost_price = db.Column(db.Numeric(10, 2))
    
    if not hasattr(Product, 'supplier'):
        Product.supplier = db.Column(db.String(100))
    
    if not hasattr(Product, 'supplier_code'):
        Product.supplier_code = db.Column(db.String(50))
    
    if not hasattr(Product, 'location'):
        Product.location = db.Column(db.String(50))  # Ubicación en almacén
    
    if not hasattr(Product, 'expiry_date'):
        Product.expiry_date = db.Column(db.Date)  # Para productos perecederos
    
    if not hasattr(Product, 'last_restock_date'):
        Product.last_restock_date = db.Column(db.DateTime)
    
    if not hasattr(Product, 'track_inventory'):
        Product.track_inventory = db.Column(db.Boolean, default=True)
    
    # Métodos adicionales
    @property
    def stock_status(Product):
        """Retorna el estado del stock"""
        if not Product.track_inventory:
            return 'no_tracking'
        if Product.stock == 0:
            return 'out_of_stock'
        elif Product.stock <= Product.min_stock:
            return 'low_stock'
        elif Product.stock >= Product.max_stock:
            return 'overstock'
        else:
            return 'normal'
    
    @property
    def stock_percentage(Product):
        """Retorna el porcentaje de stock respecto al máximo"""
        if Product.max_stock == 0:
            return 0
        return min(100, (Product.stock / Product.max_stock) * 100)
    
    @property
    def days_until_stockout(Product):
        """Estima días hasta agotarse basado en ventas recientes"""
        # Calcular velocidad de venta de los últimos 30 días
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        from app.models import OrderItem, Order
        
        sold_quantity = db.session.query(
            func.sum(OrderItem.quantity)
        ).join(Order).filter(
            OrderItem.product_id == Product.id,
            Order.created_at >= thirty_days_ago,
            Order.status != 'cancelled'
        ).scalar() or 0
        
        if sold_quantity == 0:
            return float('inf')  # No hay ventas recientes
        
        daily_rate = sold_quantity / 30
        if daily_rate == 0:
            return float('inf')
        
        return int(Product.stock / daily_rate)
    
    # Agregar métodos al modelo
    Product.stock_status = stock_status
    Product.stock_percentage = stock_percentage
    Product.days_until_stockout = days_until_stockout


class InventoryReport:
    """Clase para generar reportes de inventario"""
    
    @staticmethod
    def movement_report(user_id, start_date, end_date, product_id=None):
        """Genera reporte de movimientos de inventario"""
        query = StockMovement.query.filter(
            StockMovement.user_id == user_id,
            StockMovement.created_at.between(start_date, end_date)
        )
        
        if product_id:
            query = query.filter(StockMovement.product_id == product_id)
        
        movements = query.order_by(StockMovement.created_at.desc()).all()
        
        # Calcular resumen
        summary = {
            'total_movements': len(movements),
            'entries': sum(1 for m in movements if m.quantity > 0),
            'exits': sum(1 for m in movements if m.quantity < 0),
            'total_entered': sum(m.quantity for m in movements if m.quantity > 0),
            'total_exited': abs(sum(m.quantity for m in movements if m.quantity < 0)),
            'by_type': {}
        }
        
        # Agrupar por tipo
        for movement_type in StockMovementType:
            type_movements = [m for m in movements if m.movement_type == movement_type]
            if type_movements:
                summary['by_type'][movement_type.value] = {
                    'count': len(type_movements),
                    'quantity': sum(m.quantity for m in type_movements)
                }
        
        return {
            'movements': movements,
            'summary': summary
        }
    
    @staticmethod
    def stock_status_report(user_id):
        """Genera reporte del estado actual del inventario"""
        from app.models import Product
        
        products = Product.query.filter_by(
            user_id=user_id,
            is_active=True,
            track_inventory=True
        ).all()
        
        report = {
            'total_products': len(products),
            'out_of_stock': [],
            'low_stock': [],
            'normal_stock': [],
            'overstock': [],
            'total_value': 0,
            'alerts': []
        }
        
        for product in products:
            status = product.stock_status
            value = product.stock * (product.cost_price or product.price * 0.7)
            report['total_value'] += value
            
            product_info = {
                'id': product.id,
                'name': product.name,
                'stock': product.stock,
                'min_stock': product.min_stock,
                'value': float(value),
                'days_until_stockout': product.days_until_stockout
            }
            
            if status == 'out_of_stock':
                report['out_of_stock'].append(product_info)
                report['alerts'].append({
                    'type': 'critical',
                    'message': f'{product.name} está agotado'
                })
            elif status == 'low_stock':
                report['low_stock'].append(product_info)
                report['alerts'].append({
                    'type': 'warning',
                    'message': f'{product.name} tiene stock bajo ({product.stock} unidades)'
                })
            elif status == 'overstock':
                report['overstock'].append(product_info)
            else:
                report['normal_stock'].append(product_info)
        
        return report
