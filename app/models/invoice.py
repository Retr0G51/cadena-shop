"""
Modelos para el sistema de facturación electrónica
"""

from datetime import datetime, timedelta
from app.extensions import db
from sqlalchemy import event


class Invoice(db.Model):
    """Modelo de Factura Electrónica"""
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    
    # Relación con pedido (opcional, puede ser factura manual)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Información del cliente
    client_name = db.Column(db.String(100), nullable=False)
    client_email = db.Column(db.String(120))
    client_phone = db.Column(db.String(20))
    client_address = db.Column(db.Text)
    client_tax_id = db.Column(db.String(50))  # RUC/NIT/CI
    
    # Fechas
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime)
    
    # Estado
    status = db.Column(db.String(20), default='draft')  # draft, sent, paid, overdue, cancelled
    payment_status = db.Column(db.String(20), default='pending')  # pending, partial, paid
    
    # Montos
    subtotal = db.Column(db.Numeric(10, 2), default=0)
    tax_rate = db.Column(db.Numeric(5, 2), default=0)  # Porcentaje
    tax_amount = db.Column(db.Numeric(10, 2), default=0)
    discount_rate = db.Column(db.Numeric(5, 2), default=0)  # Porcentaje
    discount_amount = db.Column(db.Numeric(10, 2), default=0)
    total = db.Column(db.Numeric(10, 2), default=0)
    
    # Pagos
    paid_amount = db.Column(db.Numeric(10, 2), default=0)
    
    # Notas
    notes = db.Column(db.Text)
    internal_notes = db.Column(db.Text)  # Notas privadas
    
    # Configuración
    currency = db.Column(db.String(3), default='CUP')
    payment_terms = db.Column(db.Integer, default=30)  # Días para pagar
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sent_at = db.Column(db.DateTime)
    paid_at = db.Column(db.DateTime)
    
    # Relaciones
    order = db.relationship('Order', backref='invoice', uselist=False)
    business = db.relationship('User', backref='invoices')
    items = db.relationship('InvoiceItem', backref='invoice', lazy='dynamic', cascade='all, delete-orphan')
    payments = db.relationship('InvoicePayment', backref='invoice', lazy='dynamic', cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super(Invoice, self).__init__(**kwargs)
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        if not self.due_date:
            self.due_date = datetime.utcnow() + timedelta(days=self.payment_terms or 30)
    
    def generate_invoice_number(self):
        """Genera número de factura único"""
        from app.models import User
        
        # Obtener el último número de factura del usuario
        last_invoice = Invoice.query.filter_by(
            user_id=self.user_id
        ).order_by(Invoice.id.desc()).first()
        
        if last_invoice:
            # Extraer número y incrementar
            last_num = int(last_invoice.invoice_number.split('-')[-1])
            new_num = last_num + 1
        else:
            new_num = 1
        
        # Formato: INV-YYYY-00001
        year = datetime.utcnow().year
        return f"INV-{year}-{new_num:05d}"
    
    def calculate_totals(self):
        """Calcula los totales de la factura"""
        # Calcular subtotal desde items
        self.subtotal = sum(item.total for item in self.items)
        
        # Calcular descuento
        if self.discount_rate:
            self.discount_amount = self.subtotal * (self.discount_rate / 100)
        
        # Calcular impuestos
        taxable_amount = self.subtotal - self.discount_amount
        if self.tax_rate:
            self.tax_amount = taxable_amount * (self.tax_rate / 100)
        
        # Total
        self.total = taxable_amount + self.tax_amount
        
        # Actualizar estado de pago
        self.update_payment_status()
    
    def update_payment_status(self):
        """Actualiza el estado de pago basado en los pagos recibidos"""
        total_paid = sum(payment.amount for payment in self.payments if payment.status == 'completed')
        self.paid_amount = total_paid
        
        if self.paid_amount >= self.total:
            self.payment_status = 'paid'
            self.status = 'paid'
            if not self.paid_at:
                self.paid_at = datetime.utcnow()
        elif self.paid_amount > 0:
            self.payment_status = 'partial'
        else:
            self.payment_status = 'pending'
            # Verificar si está vencida
            if self.due_date and datetime.utcnow() > self.due_date:
                self.status = 'overdue'
    
    def get_status_badge_class(self):
        """Retorna la clase CSS para el badge del estado"""
        status_classes = {
            'draft': 'bg-gray-100 text-gray-800',
            'sent': 'bg-blue-100 text-blue-800',
            'paid': 'bg-green-100 text-green-800',
            'overdue': 'bg-red-100 text-red-800',
            'cancelled': 'bg-gray-100 text-gray-800'
        }
        return status_classes.get(self.status, 'bg-gray-100 text-gray-800')
    
    def get_payment_status_display(self):
        """Retorna el texto del estado de pago"""
        status_display = {
            'pending': 'Pendiente',
            'partial': 'Pago Parcial',
            'paid': 'Pagado'
        }
        return status_display.get(self.payment_status, 'Desconocido')
    
    @property
    def balance_due(self):
        """Retorna el saldo pendiente"""
        return max(0, self.total - self.paid_amount)
    
    @property
    def is_overdue(self):
        """Verifica si la factura está vencida"""
        return self.due_date and datetime.utcnow() > self.due_date and self.payment_status != 'paid'
    
    @property
    def days_overdue(self):
        """Días de vencimiento"""
        if self.is_overdue:
            return (datetime.utcnow() - self.due_date).days
        return 0


class InvoiceItem(db.Model):
    """Items de la factura"""
    __tablename__ = 'invoice_items'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    
    # Descripción del item
    description = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Opcional: relación con producto
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    
    # Totales
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    discount_rate = db.Column(db.Numeric(5, 2), default=0)
    discount_amount = db.Column(db.Numeric(10, 2), default=0)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Relaciones
    product = db.relationship('Product', backref='invoice_items')
    
    def calculate_totals(self):
        """Calcula los totales del item"""
        self.subtotal = self.quantity * self.unit_price
        
        if self.discount_rate:
            self.discount_amount = self.subtotal * (self.discount_rate / 100)
        
        self.total = self.subtotal - self.discount_amount


class InvoicePayment(db.Model):
    """Pagos registrados para una factura"""
    __tablename__ = 'invoice_payments'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    
    # Información del pago
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(50))  # cash, transfer, card, other
    reference = db.Column(db.String(100))  # Número de referencia/transacción
    
    # Estado
    status = db.Column(db.String(20), default='completed')  # pending, completed, failed
    
    # Notas
    notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# Event listeners para actualizar totales automáticamente
@event.listens_for(InvoiceItem, 'before_insert')
@event.listens_for(InvoiceItem, 'before_update')
def calculate_item_totals(mapper, connection, target):
    """Calcula totales del item antes de guardar"""
    target.calculate_totals()


@event.listens_for(InvoicePayment, 'after_insert')
@event.listens_for(InvoicePayment, 'after_update')
@event.listens_for(InvoicePayment, 'after_delete')
def update_invoice_payment_status(mapper, connection, target):
    """Actualiza estado de pago de la factura cuando cambian los pagos"""
    invoice = Invoice.query.get(target.invoice_id)
    if invoice:
        invoice.update_payment_status()
        db.session.add(invoice)
