"""
Modelo CRM para PedidosSaaS
Gestión avanzada de clientes, segmentación y marketing
"""
from datetime import datetime, timedelta
from decimal import Decimal
from app.extensions import db
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB

class Customer(db.Model):
    """Cliente del negocio con información extendida"""
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Información básica
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), index=True)
    phone = db.Column(db.String(20), nullable=False)
    alternative_phone = db.Column(db.String(20))
    
    # Información fiscal
    tax_id = db.Column(db.String(20))  # NIF/CIF/RUT
    company_name = db.Column(db.String(100))
    
    # Direcciones
    address = db.Column(db.Text)
    city = db.Column(db.String(50))
    state = db.Column(db.String(50))
    postal_code = db.Column(db.String(10))
    country = db.Column(db.String(2), default='CU')  # ISO code
    
    # Segmentación
    customer_type = db.Column(db.String(20), default='individual')  # individual, company
    segment = db.Column(db.String(50))  # vip, regular, new, etc.
    tags = db.Column(JSONB)  # Etiquetas flexibles
    
    # Preferencias
    preferred_payment_method = db.Column(db.String(20))
    preferred_contact_method = db.Column(db.String(20), default='phone')  # phone, email, whatsapp
    language = db.Column(db.String(5), default='es')
    
    # Marketing
    accepts_marketing = db.Column(db.Boolean, default=True)
    marketing_consent_date = db.Column(db.DateTime)
    unsubscribed_at = db.Column(db.DateTime)
    
    # Métricas
    total_orders = db.Column(db.Integer, default=0)
    total_spent = db.Column(db.Numeric(10, 2), default=0)
    average_order_value = db.Column(db.Numeric(10, 2), default=0)
    last_order_date = db.Column(db.DateTime)
    
    # Scoring
    loyalty_points = db.Column(db.Integer, default=0)
    credit_limit = db.Column(db.Numeric(10, 2), default=0)
    current_balance = db.Column(db.Numeric(10, 2), default=0)  # Deuda actual
    
    # Notas
    notes = db.Column(db.Text)
    internal_notes = db.Column(db.Text)  # No visible para el cliente
    
    # Estado
    is_active = db.Column(db.Boolean, default=True)
    is_blacklisted = db.Column(db.Boolean, default=False)
    blacklist_reason = db.Column(db.String(200))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    
orders = db.relationship(
    'Order', 
    foreign_keys='Order.customer_id',
    backref='customer', 
    lazy='dynamic'
)
    groups = db.relationship('CustomerGroup', secondary='customer_group_members', backref='customers')
    interactions = db.relationship('CustomerInteraction', backref='customer', lazy='dynamic', cascade='all, delete-orphan')
    
    # Índice único por negocio
    __table_args__ = (
        db.UniqueConstraint('user_id', 'email', name='_user_email_uc'),
        db.UniqueConstraint('user_id', 'phone', name='_user_phone_uc'),
    )
    
    def update_metrics(self):
        """Actualiza las métricas del cliente"""
        orders = self.orders.filter_by(status='delivered')
        self.total_orders = orders.count()
        self.total_spent = orders.with_entities(func.sum(Order.total)).scalar() or 0
        
        if self.total_orders > 0:
            self.average_order_value = self.total_spent / self.total_orders
        
        last_order = orders.order_by(Order.created_at.desc()).first()
        if last_order:
            self.last_order_date = last_order.created_at
    
    @property
    def lifetime_value(self):
        """Valor de vida del cliente"""
        return self.total_spent
    
    @property
    def days_since_last_order(self):
        """Días desde el último pedido"""
        if self.last_order_date:
            return (datetime.utcnow() - self.last_order_date).days
        return None
    
    @property
    def is_at_risk(self):
        """Cliente en riesgo de pérdida (>60 días sin comprar)"""
        days = self.days_since_last_order
        return days and days > 60
    
    @property
    def is_vip(self):
        """Cliente VIP basado en gasto o segmento"""
        return self.segment == 'vip' or self.total_spent > 1000
    
    def add_tag(self, tag):
        """Agrega una etiqueta al cliente"""
        if not self.tags:
            self.tags = []
        if tag not in self.tags:
            self.tags.append(tag)
    
    def remove_tag(self, tag):
        """Elimina una etiqueta del cliente"""
        if self.tags and tag in self.tags:
            self.tags.remove(tag)
    
    def __repr__(self):
        return f'<Customer {self.name}>'


class CustomerGroup(db.Model):
    """Grupos de clientes para segmentación"""
    __tablename__ = 'customer_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # Tipo de grupo
    group_type = db.Column(db.String(20), default='manual')  # manual, automatic
    
    # Criterios para grupos automáticos (JSON)
    criteria = db.Column(JSONB)
    
    # Beneficios del grupo
    discount_rate = db.Column(db.Numeric(5, 2), default=0)
    priority_support = db.Column(db.Boolean, default=False)
    
    # Estado
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def update_members(self):
        """Actualiza miembros si es un grupo automático"""
        if self.group_type != 'automatic' or not self.criteria:
            return
        
        # Lógica para actualizar miembros basado en criterios
        # Por ejemplo: clientes VIP, nuevos clientes, etc.
        pass
    
    def __repr__(self):
        return f'<CustomerGroup {self.name}>'


# Tabla de asociación para grupos
customer_group_members = db.Table('customer_group_members',
    db.Column('customer_id', db.Integer, db.ForeignKey('customers.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('customer_groups.id'), primary_key=True),
    db.Column('joined_at', db.DateTime, default=datetime.utcnow)
)


class CustomerInteraction(db.Model):
    """Registro de interacciones con clientes"""
    __tablename__ = 'customer_interactions'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Tipo de interacción
    interaction_type = db.Column(db.String(20), nullable=False)  # call, email, visit, complaint, note
    channel = db.Column(db.String(20))  # phone, email, whatsapp, in_person
    
    # Contenido
    subject = db.Column(db.String(200))
    content = db.Column(db.Text)
    
    # Seguimiento
    requires_followup = db.Column(db.Boolean, default=False)
    followup_date = db.Column(db.DateTime)
    is_resolved = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    def __repr__(self):
        return f'<CustomerInteraction {self.interaction_type} Customer:{self.customer_id}>'


class MarketingCampaign(db.Model):
    """Campañas de marketing"""
    __tablename__ = 'marketing_campaigns'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    campaign_type = db.Column(db.String(20), nullable=False)  # email, sms, promotion
    
    # Contenido
    subject = db.Column(db.String(200))
    content = db.Column(db.Text)
    template_id = db.Column(db.String(50))  # Para templates externos
    
    # Segmentación
    target_group_id = db.Column(db.Integer, db.ForeignKey('customer_groups.id'))
    target_criteria = db.Column(JSONB)  # Criterios adicionales
    
    # Configuración
    discount_code = db.Column(db.String(20))
    discount_amount = db.Column(db.Numeric(10, 2))
    discount_percentage = db.Column(db.Numeric(5, 2))
    
    # Programación
    status = db.Column(db.String(20), default='draft')  # draft, scheduled, active, completed
    scheduled_at = db.Column(db.DateTime)
    sent_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)
    
    # Métricas
    total_recipients = db.Column(db.Integer, default=0)
    total_sent = db.Column(db.Integer, default=0)
    total_opened = db.Column(db.Integer, default=0)
    total_clicked = db.Column(db.Integer, default=0)
    total_converted = db.Column(db.Integer, default=0)
    revenue_generated = db.Column(db.Numeric(10, 2), default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def open_rate(self):
        """Tasa de apertura"""
        if self.total_sent > 0:
            return (self.total_opened / self.total_sent) * 100
        return 0
    
    @property
    def click_rate(self):
        """Tasa de clics"""
        if self.total_opened > 0:
            return (self.total_clicked / self.total_opened) * 100
        return 0
    
    @property
    def conversion_rate(self):
        """Tasa de conversión"""
        if self.total_sent > 0:
            return (self.total_converted / self.total_sent) * 100
        return 0
    
    @property
    def roi(self):
        """Retorno de inversión"""
        # Simplified ROI calculation
        cost = self.total_sent * 0.01  # Asumiendo costo por mensaje
        if cost > 0:
            return ((self.revenue_generated - cost) / cost) * 100
        return 0
    
    def __repr__(self):
        return f'<MarketingCampaign {self.name}>'


class CampaignRecipient(db.Model):
    """Destinatarios de campañas"""
    __tablename__ = 'campaign_recipients'
    
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('marketing_campaigns.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    
    # Estado
    status = db.Column(db.String(20), default='pending')  # pending, sent, failed
    sent_at = db.Column(db.DateTime)
    opened_at = db.Column(db.DateTime)
    clicked_at = db.Column(db.DateTime)
    converted_at = db.Column(db.DateTime)
    
    # Tracking
    open_count = db.Column(db.Integer, default=0)
    click_count = db.Column(db.Integer, default=0)
    
    # Error tracking
    error_message = db.Column(db.String(200))
    
    # Relaciones
    campaign = db.relationship('MarketingCampaign', backref='recipients')
    
    def mark_as_opened(self):
        """Marca como abierto"""
        if not self.opened_at:
            self.opened_at = datetime.utcnow()
        self.open_count += 1
    
    def mark_as_clicked(self):
        """Marca como clickeado"""
        if not self.clicked_at:
            self.clicked_at = datetime.utcnow()
        self.click_count += 1
    
    def __repr__(self):
        return f'<CampaignRecipient Campaign:{self.campaign_id} Customer:{self.customer_id}>'


class LoyaltyProgram(db.Model):
    """Programa de lealtad"""
    __tablename__ = 'loyalty_programs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # Configuración de puntos
    points_per_currency = db.Column(db.Integer, default=1)  # Puntos por cada unidad monetaria
    points_to_currency_rate = db.Column(db.Numeric(5, 2), default=0.01)  # Valor de cada punto
    
    # Reglas
    min_points_to_redeem = db.Column(db.Integer, default=100)
    points_expiry_days = db.Column(db.Integer)  # Días hasta que expiran los puntos
    
    # Estado
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<LoyaltyProgram {self.name}>'


class LoyaltyTransaction(db.Model):
    """Transacciones de puntos de lealtad"""
    __tablename__ = 'loyalty_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('loyalty_programs.id'), nullable=False)
    
    transaction_type = db.Column(db.String(20), nullable=False)  # earn, redeem, expire, adjust
    points = db.Column(db.Integer, nullable=False)  # Positivo para ganar, negativo para canjear
    balance_after = db.Column(db.Integer, nullable=False)
    
    # Referencia
    reference_type = db.Column(db.String(20))  # order, manual, promotion
    reference_id = db.Column(db.Integer)
    
    description = db.Column(db.String(200))
    expires_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<LoyaltyTransaction {self.transaction_type} {self.points}pts>'
