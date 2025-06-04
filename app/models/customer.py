"""
Sistema CRM básico para gestión de clientes
"""

from datetime import datetime, timedelta
from app.extensions import db
from sqlalchemy import func, and_
import re


class Customer(db.Model):
    """Modelo de Cliente para CRM"""
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Información básica
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), index=True)
    phone = db.Column(db.String(20), nullable=False, index=True)
    secondary_phone = db.Column(db.String(20))
    
    # Información adicional
    address = db.Column(db.Text)
    city = db.Column(db.String(50))
    state = db.Column(db.String(50))
    postal_code = db.Column(db.String(20))
    
    # Información fiscal
    tax_id = db.Column(db.String(50))  # CI/RUC/NIT
    company_name = db.Column(db.String(100))
    
    # Fechas importantes
    birthdate = db.Column(db.Date)
    anniversary_date = db.Column(db.Date)  # Para recordatorios
    
    # Segmentación
    customer_type = db.Column(db.String(20), default='individual')  # individual, company
    segment = db.Column(db.String(50))  # VIP, regular, new, inactive
    tags = db.Column(db.JSON, default=list)  # Etiquetas personalizadas
    
    # Preferencias
    preferred_contact_method = db.Column(db.String(20), default='phone')  # phone, email, whatsapp
    marketing_consent = db.Column(db.Boolean, default=True)
    
    # Estadísticas (se actualizan automáticamente)
    total_orders = db.Column(db.Integer, default=0)
    total_spent = db.Column(db.Numeric(12, 2), default=0)
    average_order_value = db.Column(db.Numeric(10, 2), default=0)
    last_order_date = db.Column(db.DateTime)
    
    # Scoring
    lifetime_value = db.Column(db.Numeric(12, 2), default=0)  # CLV
    loyalty_score = db.Column(db.Integer, default=0)  # 0-100
    
    # Estado
    status = db.Column(db.String(20), default='active')  # active, inactive, blocked
    
    # Notas
    notes = db.Column(db.Text)
    internal_notes = db.Column(db.Text)  # Notas privadas del negocio
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    business = db.relationship('User', backref='customers')
    orders = db.relationship('Order', backref='customer', lazy='dynamic')
    interactions = db.relationship('CustomerInteraction', backref='customer', lazy='dynamic', cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super(Customer, self).__init__(**kwargs)
        # Normalizar teléfono
        if self.phone:
            self.phone = self.normalize_phone(self.phone)
    
    @staticmethod
    def normalize_phone(phone):
        """Normaliza el formato del teléfono"""
        # Remover caracteres no numéricos
        phone = re.sub(r'\D', '', phone)
        # Agregar código de país si no lo tiene (asumiendo Cuba +53)
        if len(phone) == 8 and not phone.startswith('53'):
            phone = '53' + phone
        return phone
    
    def update_statistics(self):
        """Actualiza las estadísticas del cliente basado en sus pedidos"""
        from app.models import Order
        
        # Obtener pedidos completados
        completed_orders = self.orders.filter(
            Order.status.in_(['delivered', 'completed'])
        ).all()
        
        self.total_orders = len(completed_orders)
        self.total_spent = sum(order.total for order in completed_orders)
        
        if self.total_orders > 0:
            self.average_order_value = self.total_spent / self.total_orders
            self.last_order_date = max(order.created_at for order in completed_orders)
        
        # Calcular lifetime value (simplificado)
        self.calculate_lifetime_value()
        
        # Calcular loyalty score
        self.calculate_loyalty_score()
        
        # Actualizar segmento
        self.update_segment()
    
    def calculate_lifetime_value(self):
        """Calcula el valor de vida del cliente (CLV)"""
        # Fórmula simplificada: AOV × Frecuencia × Duración esperada
        if self.total_orders == 0:
            self.lifetime_value = 0
            return
        
        # Calcular frecuencia de compra (pedidos por mes)
        months_active = max(1, (datetime.utcnow() - self.created_at).days / 30)
        frequency = self.total_orders / months_active
        
        # Estimar duración (meses) - simplificado
        expected_lifetime_months = 24  # 2 años por defecto
        
        self.lifetime_value = self.average_order_value * frequency * expected_lifetime_months
    
    def calculate_loyalty_score(self):
        """Calcula un score de lealtad del 0-100"""
        score = 0
        
        # Frecuencia de compra (30 puntos)
        if self.total_orders >= 10:
            score += 30
        elif self.total_orders >= 5:
            score += 20
        elif self.total_orders >= 2:
            score += 10
        
        # Recencia (30 puntos)
        if self.last_order_date:
            days_since_last_order = (datetime.utcnow() - self.last_order_date).days
            if days_since_last_order <= 30:
                score += 30
            elif days_since_last_order <= 60:
                score += 20
            elif days_since_last_order <= 90:
                score += 10
        
        # Valor monetario (40 puntos)
        if self.total_spent >= 1000:
            score += 40
        elif self.total_spent >= 500:
            score += 30
        elif self.total_spent >= 200:
            score += 20
        elif self.total_spent >= 50:
            score += 10
        
        self.loyalty_score = min(100, score)
    
    def update_segment(self):
        """Actualiza el segmento del cliente automáticamente"""
        # Segmentación basada en RFM simplificado
        if self.loyalty_score >= 80:
            self.segment = 'VIP'
        elif self.loyalty_score >= 50:
            self.segment = 'regular'
        elif self.total_orders == 0:
            self.segment = 'prospect'
        elif self.last_order_date and (datetime.utcnow() - self.last_order_date).days > 180:
            self.segment = 'inactive'
        else:
            self.segment = 'new'
    
    @property
    def is_birthday_soon(self):
        """Verifica si el cumpleaños es en los próximos 7 días"""
        if not self.birthdate:
            return False
        
        today = datetime.utcnow().date()
        birthday_this_year = self.birthdate.replace(year=today.year)
        
        # Si ya pasó este año, verificar el próximo
        if birthday_this_year < today:
            birthday_this_year = birthday_this_year.replace(year=today.year + 1)
        
        days_until = (birthday_this_year - today).days
        return 0 <= days_until <= 7
    
    @property
    def days_since_last_order(self):
        """Días desde el último pedido"""
        if not self.last_order_date:
            return None
        return (datetime.utcnow() - self.last_order_date).days
    
    def add_tag(self, tag):
        """Agrega una etiqueta al cliente"""
        if not self.tags:
            self.tags = []
        if tag not in self.tags:
            self.tags = self.tags + [tag]  # SQLAlchemy detecta cambios en JSON
    
    def remove_tag(self, tag):
        """Remueve una etiqueta del cliente"""
        if self.tags and tag in self.tags:
            self.tags = [t for t in self.tags if t != tag]


class CustomerInteraction(db.Model):
    """Registro de interacciones con clientes"""
    __tablename__ = 'customer_interactions'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Tipo de interacción
    interaction_type = db.Column(db.String(50), nullable=False)  # call, email, visit, note, complaint
    channel = db.Column(db.String(50))  # phone, email, whatsapp, in_person
    
    # Contenido
    subject = db.Column(db.String(200))
    description = db.Column(db.Text, nullable=False)
    
    # Estado y seguimiento
    status = db.Column(db.String(20), default='completed')  # completed, pending, scheduled
    follow_up_required = db.Column(db.Boolean, default=False)
    follow_up_date = db.Column(db.DateTime)
    
    # Resultado
    outcome = db.Column(db.String(50))  # satisfied, unsatisfied, no_answer, scheduled
    
    # Timestamps
    interaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100))  # Nombre del usuario que registró
    
    # Relaciones
    business = db.relationship('User', backref='customer_interactions')


class CustomerGroup(db.Model):
    """Grupos de clientes para segmentación y campañas"""
    __tablename__ = 'customer_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Información del grupo
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # Criterios de segmentación (JSON)
    criteria = db.Column(db.JSON)  # Ej: {"min_orders": 5, "segment": "VIP"}
    
    # Tipo
    group_type = db.Column(db.String(20), default='manual')  # manual, automatic
    
    # Estado
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    business = db.relationship('User', backref='customer_groups')
    members = db.relationship('CustomerGroupMember', backref='group', lazy='dynamic', cascade='all, delete-orphan')
    
    @property
    def member_count(self):
        """Cantidad de miembros en el grupo"""
        return self.members.count()
    
    def update_automatic_members(self):
        """Actualiza miembros automáticamente basado en criterios"""
        if self.group_type != 'automatic' or not self.criteria:
            return
        
        # Construir query basado en criterios
        query = Customer.query.filter_by(user_id=self.user_id)
        
        if 'min_orders' in self.criteria:
            query = query.filter(Customer.total_orders >= self.criteria['min_orders'])
        
        if 'segment' in self.criteria:
            query = query.filter(Customer.segment == self.criteria['segment'])
        
        if 'min_spent' in self.criteria:
            query = query.filter(Customer.total_spent >= self.criteria['min_spent'])
        
        if 'tags' in self.criteria:
            # Filtrar por tags (requiere JSON operations)
            for tag in self.criteria['tags']:
                query = query.filter(Customer.tags.contains([tag]))
        
        # Obtener clientes que cumplen criterios
        matching_customers = query.all()
        
        # Actualizar membresías
        current_member_ids = set(m.customer_id for m in self.members)
        new_member_ids = set(c.id for c in matching_customers)
        
        # Agregar nuevos miembros
        for customer_id in new_member_ids - current_member_ids:
            member = CustomerGroupMember(
                group_id=self.id,
                customer_id=customer_id
            )
            db.session.add(member)
        
        # Remover miembros que ya no cumplen
        for customer_id in current_member_ids - new_member_ids:
            member = self.members.filter_by(customer_id=customer_id).first()
            if member:
                db.session.delete(member)


class CustomerGroupMember(db.Model):
    """Membresía de clientes en grupos"""
    __tablename__ = 'customer_group_members'
    
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('customer_groups.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    
    # Fecha de adición
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relación con cliente
    customer = db.relationship('Customer', backref='group_memberships')
    
    # Índice único para evitar duplicados
    __table_args__ = (
        db.UniqueConstraint('group_id', 'customer_id', name='_group_customer_uc'),
    )


class CustomerAnalytics:
    """Clase para análisis y reportes de clientes"""
    
    @staticmethod
    def get_customer_summary(user_id):
        """Obtiene resumen de clientes"""
        total = Customer.query.filter_by(user_id=user_id).count()
        active = Customer.query.filter_by(user_id=user_id, status='active').count()
        
        # Segmentación
        segments = db.session.query(
            Customer.segment,
            func.count(Customer.id)
        ).filter_by(
            user_id=user_id
        ).group_by(Customer.segment).all()
        
        # Clientes nuevos este mes
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
        new_this_month = Customer.query.filter(
            Customer.user_id == user_id,
            Customer.created_at >= start_of_month
        ).count()
        
        return {
            'total': total,
            'active': active,
            'new_this_month': new_this_month,
            'segments': dict(segments),
            'retention_rate': (active / total * 100) if total > 0 else 0
        }
    
    @staticmethod
    def get_top_customers(user_id, limit=10, by='total_spent'):
        """Obtiene los mejores clientes"""
        query = Customer.query.filter_by(user_id=user_id)
        
        if by == 'total_spent':
            query = query.order_by(Customer.total_spent.desc())
        elif by == 'total_orders':
            query = query.order_by(Customer.total_orders.desc())
        elif by == 'loyalty_score':
            query = query.order_by(Customer.loyalty_score.desc())
        
        return query.limit(limit).all()
    
    @staticmethod
    def get_at_risk_customers(user_id, days_inactive=90):
        """Identifica clientes en riesgo de pérdida"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)
        
        return Customer.query.filter(
            Customer.user_id == user_id,
            Customer.last_order_date < cutoff_date,
            Customer.total_orders > 0,
            Customer.status == 'active'
        ).order_by(Customer.total_spent.desc()).all()
