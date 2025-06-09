"""
Modelos de la aplicación PedidosSaaS
Centraliza todos los modelos para facilitar imports
"""

# Importar modelos principales desde el archivo base
from app.models import User, Product, Order, OrderItem

# Importar modelos adicionales
from app.models.invoice import (
    Invoice, InvoiceSeries, InvoiceItem, InvoicePayment, RecurringInvoice
)

from app.models.inventory import (
    Warehouse, StockItem, InventoryMovement, StockAlert, 
    PurchaseOrder, PurchaseOrderItem
)

from app.models.customer import (
    Customer, CustomerGroup, CustomerInteraction,
    MarketingCampaign, CampaignRecipient, 
    LoyaltyProgram, LoyaltyTransaction
)

# Exportar todos los modelos
__all__ = [
    # Base
    'User', 'Product', 'Order', 'OrderItem',
    
    # Invoice
    'Invoice', 'InvoiceSeries', 'InvoiceItem', 'InvoicePayment', 'RecurringInvoice',
    
    # Inventory
    'Warehouse', 'StockItem', 'InventoryMovement', 'StockAlert',
    'PurchaseOrder', 'PurchaseOrderItem',
    
    # Customer
    'Customer', 'CustomerGroup', 'CustomerInteraction',
    'MarketingCampaign', 'CampaignRecipient',
    'LoyaltyProgram', 'LoyaltyTransaction'
]

# Registrar eventos y validaciones
from sqlalchemy import event
from sqlalchemy.orm import validates

# Eventos para actualizar timestamps automáticamente
def update_timestamp(mapper, connection, target):
    """Actualiza el campo updated_at antes de guardar"""
    if hasattr(target, 'updated_at'):
        from datetime import datetime
        target.updated_at = datetime.utcnow()

# Registrar evento para todos los modelos con updated_at
for model in [User, Product, Order, Customer, Invoice]:
    if hasattr(model, 'updated_at'):
        event.listen(model, 'before_update', update_timestamp)

# Validaciones globales
@event.listens_for(Product.price, 'set', propagate=True)
def validate_price(target, value, oldvalue, initiator):
    """Valida que el precio sea positivo"""
    if value is not None and value < 0:
        raise ValueError("El precio no puede ser negativo")
    return value

@event.listens_for(Order, 'before_insert')
def generate_order_number(mapper, connection, target):
    """Genera número de orden antes de insertar"""
    if not target.order_number:
        from datetime import datetime
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        target.order_number = f"ORD-{timestamp}"

# Funciones de utilidad para modelos
def get_model_by_name(model_name):
    """Obtiene una clase de modelo por su nombre"""
    return globals().get(model_name)

def get_all_models():
    """Obtiene todas las clases de modelo"""
    from app.extensions import db
    return [
        model for model in globals().values()
        if hasattr(model, '__tablename__') and 
        hasattr(model, '__table__') and
        isinstance(model.__table__, db.Table)
    ]
