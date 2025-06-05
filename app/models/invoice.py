"""
Modelo de Facturación para PedidosSaaS
Gestiona facturas, series, numeración y control fiscal
"""
from datetime import datetime
from decimal import Decimal
from app.extensions import db
from app.models import Order

class InvoiceSeries(db.Model):
    """Serie de facturación para control fiscal"""
    __tablename__ = 'invoice_series'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    prefix = db.Column(db.String(10), nullable=False)  # Ej: "FAC", "A", "B"
    current_number = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    invoices = db.relationship('Invoice', backref='series', lazy='dynamic')
    
    def get_next_number(self):
        """Obtiene el siguiente número de factura"""
        self.current_number += 1
        return f"{self.prefix}-{self.current_number:06d}"
    
    def __repr__(self):
        return f'<InvoiceSeries {self.prefix}>'


class Invoice(db.Model):
    """Modelo de Factura"""
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    
    # Información fiscal
    series_id = db.Column(db.Integer, db.ForeignKey('invoice_series.id'))
    fiscal_year = db.Column(db.Integer, default=lambda: datetime.utcnow().year)
    
    # Cliente
    customer_name = db.Column(db.String(100), nullable=False)
    customer_tax_id = db.Column(db.String(20))  # NIF/CIF/RUT
    customer_address = db.Column(db.Text)
    customer_email = db.Column(db.String(120))
    customer_phone = db.Column(db.String(20))
    
    # Totales
    subtotal = db.Column(db.Numeric(10, 2), default=0)
    tax_rate = db.Column(db.Numeric(5, 2), default=0)  # Porcentaje
    tax_amount = db.Column(db.Numeric(10, 2), default=0)
    discount_rate = db.Column(db.Numeric(5, 2), default=0)
    discount_amount = db.Column(db.Numeric(10, 2), default=0)
    total = db.Column(db.Numeric(10, 2), default=0)
    
    # Estado
    status = db.Column(db.String(20), default='draft')  # draft, issued, paid, cancelled
    payment_method = db.Column(db.String(20))
    payment_date = db.Column(db.DateTime)
    due_date = db.Column(db.DateTime)
    
    # Notas
    notes = db.Column(db.Text)
    internal_notes = db.Column(db.Text)  # No visible para el cliente
    
    # Timestamps
    issued_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))  # Opcional, puede venir de un pedido
    
    # Relaciones
    items = db.relationship('InvoiceItem', backref='invoice', lazy='dynamic', cascade='all, delete-orphan')
    payments = db.relationship('InvoicePayment', backref='invoice', lazy='dynamic', cascade='all, delete-orphan')
    
    def calculate_totals(self):
        """Calcula los totales de la factura"""
        # Calcular subtotal
        self.subtotal = sum(item.subtotal for item in self.items)
        
        # Calcular descuento
        if self.discount_rate > 0:
            self.discount_amount = self.subtotal * (self.discount_rate / 100)
        
        # Base imponible
        taxable_base = self.subtotal - self.discount_amount
        
        # Calcular impuestos
        if self.tax_rate > 0:
            self.tax_amount = taxable_base * (self.tax_rate / 100)
        
        # Total
        self.total = taxable_base + self.tax_amount
    
    def mark_as_paid(self, payment_date=None):
        """Marca la factura como pagada"""
        self.status = 'paid'
        self.payment_date = payment_date or datetime.utcnow()
    
    def get_paid_amount(self):
        """Obtiene el monto pagado"""
        return sum(payment.amount for payment in self.payments if payment.is_confirmed)
    
    def get_pending_amount(self):
        """Obtiene el monto pendiente"""
        return self.total - self.get_paid_amount()
    
    @property
    def is_overdue(self):
        """Verifica si la factura está vencida"""
        if self.status == 'paid' or not self.due_date:
            return False
        return datetime.utcnow() > self.due_date
    
    def __repr__(self):
        return f'<Invoice {self.invoice_number}>'


class InvoiceItem(db.Model):
    """Items de una factura"""
    __tablename__ = 'invoice_items'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    
    # Descripción del item
    description = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    discount_rate = db.Column(db.Numeric(5, 2), default=0)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Referencia opcional a producto
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    
    def calculate_subtotal(self):
        """Calcula el subtotal del item"""
        base = self.quantity * self.unit_price
        if self.discount_rate > 0:
            discount = base * (self.discount_rate / 100)
            self.subtotal = base - discount
        else:
            self.subtotal = base


class InvoicePayment(db.Model):
    """Pagos parciales de facturas"""
    __tablename__ = 'invoice_payments'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(20), nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    reference = db.Column(db.String(100))  # Número de transferencia, cheque, etc.
    notes = db.Column(db.Text)
    is_confirmed = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<InvoicePayment {self.amount} for Invoice {self.invoice_id}>'


class RecurringInvoice(db.Model):
    """Facturas recurrentes automáticas"""
    __tablename__ = 'recurring_invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Plantilla
    template_name = db.Column(db.String(100), nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_tax_id = db.Column(db.String(20))
    customer_address = db.Column(db.Text)
    customer_email = db.Column(db.String(120))
    
    # Items recurrentes (stored as JSON)
    items_json = db.Column(db.JSON)
    
    # Configuración de recurrencia
    frequency = db.Column(db.String(20), nullable=False)  # daily, weekly, monthly, yearly
    interval = db.Column(db.Integer, default=1)  # Cada X períodos
    day_of_month = db.Column(db.Integer)  # Para facturas mensuales
    
    # Control
    is_active = db.Column(db.Boolean, default=True)
    next_issue_date = db.Column(db.DateTime, nullable=False)
    last_issued_date = db.Column(db.DateTime)
    
    # Configuración fiscal
    series_id = db.Column(db.Integer, db.ForeignKey('invoice_series.id'))
    tax_rate = db.Column(db.Numeric(5, 2), default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def create_invoice(self):
        """Crea una factura basada en esta plantilla"""
        invoice = Invoice(
            user_id=self.user_id,
            series_id=self.series_id,
            customer_name=self.customer_name,
            customer_tax_id=self.customer_tax_id,
            customer_address=self.customer_address,
            customer_email=self.customer_email,
            tax_rate=self.tax_rate,
            status='draft'
        )
        
        # Crear items desde JSON
        if self.items_json:
            for item_data in self.items_json:
                item = InvoiceItem(
                    description=item_data['description'],
                    quantity=item_data['quantity'],
                    unit_price=item_data['unit_price'],
                    discount_rate=item_data.get('discount_rate', 0)
                )
                item.calculate_subtotal()
                invoice.items.append(item)
        
        return invoice
    
    def calculate_next_date(self):
        """Calcula la próxima fecha de emisión"""
        from dateutil.relativedelta import relativedelta
        
        if self.frequency == 'daily':
            delta = relativedelta(days=self.interval)
        elif self.frequency == 'weekly':
            delta = relativedelta(weeks=self.interval)
        elif self.frequency == 'monthly':
            delta = relativedelta(months=self.interval)
        elif self.frequency == 'yearly':
            delta = relativedelta(years=self.interval)
        else:
            delta = relativedelta(months=1)
        
        self.next_issue_date = self.next_issue_date + delta
    
    def __repr__(self):
        return f'<RecurringInvoice {self.template_name}>'
