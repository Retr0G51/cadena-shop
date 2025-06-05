"""
Sistema de Analytics para PedidosSaaS
Análisis de ventas, productos, clientes y tendencias
"""
from datetime import datetime, timedelta
from decimal import Decimal
from flask import jsonify
from sqlalchemy import func, and_, or_, extract
from app.extensions import db
from app.models import Order, OrderItem, Product, User
from app.models.customer import Customer, CustomerGroup
from app.models.invoice import Invoice
from app.models.inventory import StockItem, InventoryMovement

class Analytics:
    """Clase principal para análisis de datos"""
    
    def __init__(self, user_id):
        self.user_id = user_id
    
    def get_dashboard_metrics(self, date_from=None, date_to=None):
        """Obtiene métricas principales del dashboard"""
        if not date_from:
            date_from = datetime.utcnow() - timedelta(days=30)
        if not date_to:
            date_to = datetime.utcnow()
        
        # Filtro base
        date_filter = and_(
            Order.created_at >= date_from,
            Order.created_at <= date_to,
            Order.user_id == self.user_id
        )
        
        # Ventas totales
        total_sales = db.session.query(
            func.sum(Order.total)
        ).filter(date_filter, Order.status == 'delivered').scalar() or 0
        
        # Número de pedidos
        total_orders = db.session.query(
            func.count(Order.id)
        ).filter(date_filter).scalar() or 0
        
        # Pedidos completados
        completed_orders = db.session.query(
            func.count(Order.id)
        ).filter(date_filter, Order.status == 'delivered').scalar() or 0
        
        # Ticket promedio
        avg_order_value = 0
        if completed_orders > 0:
            avg_order_value = total_sales / completed_orders
        
        # Productos vendidos
        products_sold = db.session.query(
            func.sum(OrderItem.quantity)
        ).join(Order).filter(
            date_filter,
            Order.status == 'delivered'
        ).scalar() or 0
        
        # Clientes únicos
        unique_customers = db.session.query(
            func.count(func.distinct(Order.customer_phone))
        ).filter(date_filter).scalar() or 0
        
        # Comparación con período anterior
        prev_date_from = date_from - (date_to - date_from)
        prev_date_to = date_from
        
        prev_sales = db.session.query(
            func.sum(Order.total)
        ).filter(
            and_(
                Order.created_at >= prev_date_from,
                Order.created_at < prev_date_to,
                Order.user_id == self.user_id,
                Order.status == 'delivered'
            )
        ).scalar() or 0
        
        # Calcular cambio porcentual
        sales_change = 0
        if prev_sales > 0:
            sales_change = ((total_sales - prev_sales) / prev_sales) * 100
        
        return {
            'total_sales': float(total_sales),
            'total_orders': total_orders,
            'completed_orders': completed_orders,
            'completion_rate': (completed_orders / total_orders * 100) if total_orders > 0 else 0,
            'avg_order_value': float(avg_order_value),
            'products_sold': int(products_sold),
            'unique_customers': unique_customers,
            'sales_change': float(sales_change),
            'date_range': {
                'from': date_from.isoformat(),
                'to': date_to.isoformat()
            }
        }
    
    def get_sales_trend(self, period='daily', days=30):
        """Obtiene tendencia de ventas"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Determinar agrupación
        if period == 'daily':
            date_trunc = func.date_trunc('day', Order.created_at)
        elif period == 'weekly':
            date_trunc = func.date_trunc('week', Order.created_at)
        elif period == 'monthly':
            date_trunc = func.date_trunc('month', Order.created_at)
        else:
            date_trunc = func.date_trunc('day', Order.created_at)
        
        # Query
        sales_data = db.session.query(
            date_trunc.label('period'),
            func.count(Order.id).label('orders'),
            func.sum(Order.total).label('revenue'),
            func.avg(Order.total).label('avg_order')
        ).filter(
            Order.user_id == self.user_id,
            Order.created_at >= start_date,
            Order.created_at <= end_date,
            Order.status == 'delivered'
        ).group_by('period').order_by('period').all()
        
        return [{
            'date': row.period.isoformat(),
            'orders': row.orders,
            'revenue': float(row.revenue or 0),
            'avg_order': float(row.avg_order or 0)
        } for row in sales_data]
    
    def get_top_products(self, limit=10, days=30):
        """Obtiene productos más vendidos"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        top_products = db.session.query(
            Product.id,
            Product.name,
            Product.price,
            func.sum(OrderItem.quantity).label('quantity_sold'),
            func.sum(OrderItem.subtotal).label('revenue'),
            func.count(func.distinct(Order.id)).label('order_count')
        ).join(
            OrderItem, Product.id == OrderItem.product_id
        ).join(
            Order, Order.id == OrderItem.order_id
        ).filter(
            Product.user_id == self.user_id,
            Order.created_at >= start_date,
            Order.created_at <= end_date,
            Order.status == 'delivered'
        ).group_by(
            Product.id, Product.name, Product.price
        ).order_by(
            func.sum(OrderItem.quantity).desc()
        ).limit(limit).all()
        
        return [{
            'id': row.id,
            'name': row.name,
            'price': float(row.price),
            'quantity_sold': int(row.quantity_sold),
            'revenue': float(row.revenue),
            'order_count': row.order_count
        } for row in top_products]
    
    def get_customer_analytics(self):
        """Análisis de clientes"""
        # Clientes totales
        total_customers = Customer.query.filter_by(
            user_id=self.user_id
        ).count()
        
        # Nuevos clientes (últimos 30 días)
        new_customers = Customer.query.filter(
            Customer.user_id == self.user_id,
            Customer.created_at >= datetime.utcnow() - timedelta(days=30)
        ).count()
        
        # Clientes recurrentes
        recurring_customers = db.session.query(
            func.count(func.distinct(Order.customer_phone))
        ).filter(
            Order.user_id == self.user_id
        ).group_by(
            Order.customer_phone
        ).having(
            func.count(Order.id) > 1
        ).count()
        
        # Segmentación por valor
        customer_segments = db.session.query(
            func.case(
                (Customer.total_spent >= 1000, 'VIP'),
                (Customer.total_spent >= 500, 'Premium'),
                (Customer.total_spent >= 100, 'Regular'),
                else_='Nuevo'
            ).label('segment'),
            func.count(Customer.id).label('count'),
            func.avg(Customer.total_spent).label('avg_spent')
        ).filter(
            Customer.user_id == self.user_id
        ).group_by('segment').all()
        
        # Tasa de retención
        retention_rate = 0
        if total_customers > 0:
            retention_rate = (recurring_customers / total_customers) * 100
        
        return {
            'total_customers': total_customers,
            'new_customers': new_customers,
            'recurring_customers': recurring_customers,
            'retention_rate': retention_rate,
            'segments': [{
                'name': seg.segment,
                'count': seg.count,
                'avg_spent': float(seg.avg_spent or 0)
            } for seg in customer_segments]
        }
    
    def get_sales_by_hour(self, days=7):
        """Ventas por hora del día"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        hourly_sales = db.session.query(
            extract('hour', Order.created_at).label('hour'),
            func.count(Order.id).label('orders'),
            func.sum(Order.total).label('revenue')
        ).filter(
            Order.user_id == self.user_id,
            Order.created_at >= start_date,
            Order.created_at <= end_date,
            Order.status == 'delivered'
        ).group_by('hour').order_by('hour').all()
        
        # Crear array completo de 24 horas
        hourly_data = {hour: {'orders': 0, 'revenue': 0} for hour in range(24)}
        
        for row in hourly_sales:
            hourly_data[int(row.hour)] = {
                'orders': row.orders,
                'revenue': float(row.revenue or 0)
            }
        
        return [
            {
                'hour': hour,
                'orders': data['orders'],
                'revenue': data['revenue']
            }
            for hour, data in sorted(hourly_data.items())
        ]
    
    def get_category_performance(self):
        """Rendimiento por categoría"""
        category_stats = db.session.query(
            Product.category,
            func.count(func.distinct(Product.id)).label('product_count'),
            func.sum(OrderItem.quantity).label('units_sold'),
            func.sum(OrderItem.subtotal).label('revenue')
        ).join(
            OrderItem, Product.id == OrderItem.product_id
        ).join(
            Order, Order.id == OrderItem.order_id
        ).filter(
            Product.user_id == self.user_id,
            Order.status == 'delivered'
        ).group_by(Product.category).all()
        
        return [{
            'category': row.category or 'Sin categoría',
            'product_count': row.product_count,
            'units_sold': int(row.units_sold or 0),
            'revenue': float(row.revenue or 0)
        } for row in category_stats]
    
    def get_inventory_metrics(self):
        """Métricas de inventario"""
        # Valor total del inventario
        inventory_value = db.session.query(
            func.sum(StockItem.quantity * StockItem.average_cost)
        ).join(
            Product, Product.id == StockItem.product_id
        ).filter(
            Product.user_id == self.user_id
        ).scalar() or 0
        
        # Productos con bajo stock
        low_stock_products = StockItem.query.join(
            Product
        ).filter(
            Product.user_id == self.user_id,
            StockItem.quantity <= StockItem.min_stock
        ).count()
        
        # Rotación de inventario (últimos 30 días)
        cogs = db.session.query(
            func.sum(OrderItem.quantity * StockItem.average_cost)
        ).join(
            Product, Product.id == OrderItem.product_id
        ).join(
            StockItem, StockItem.product_id == Product.id
        ).join(
            Order, Order.id == OrderItem.order_id
        ).filter(
            Product.user_id == self.user_id,
            Order.created_at >= datetime.utcnow() - timedelta(days=30),
            Order.status == 'delivered'
        ).scalar() or 0
        
        # Calcular rotación
        inventory_turnover = 0
        if inventory_value > 0:
            inventory_turnover = (cogs * 12) / inventory_value  # Anualizado
        
        return {
            'inventory_value': float(inventory_value),
            'low_stock_products': low_stock_products,
            'inventory_turnover': float(inventory_turnover),
            'avg_days_to_sell': 365 / inventory_turnover if inventory_turnover > 0 else 0
        }
    
    def get_financial_summary(self, month=None, year=None):
        """Resumen financiero mensual"""
        if not month:
            month = datetime.utcnow().month
        if not year:
            year = datetime.utcnow().year
        
        # Ingresos del mes
        monthly_revenue = db.session.query(
            func.sum(Invoice.total)
        ).filter(
            Invoice.user_id == self.user_id,
            extract('month', Invoice.issued_at) == month,
            extract('year', Invoice.issued_at) == year,
            Invoice.status == 'paid'
        ).scalar() or 0
        
        # Cuentas por cobrar
        accounts_receivable = db.session.query(
            func.sum(Invoice.total - func.coalesce(
                db.session.query(func.sum(InvoicePayment.amount))
                .filter(InvoicePayment.invoice_id == Invoice.id)
                .scalar_subquery(), 0
            ))
        ).filter(
            Invoice.user_id == self.user_id,
            Invoice.status.in_(['issued', 'partial'])
        ).scalar() or 0
        
        # Facturas vencidas
        overdue_invoices = Invoice.query.filter(
            Invoice.user_id == self.user_id,
            Invoice.status != 'paid',
            Invoice.due_date < datetime.utcnow()
        ).count()
        
        # Margen bruto
        revenue = db.session.query(
            func.sum(OrderItem.subtotal)
        ).join(
            Order, Order.id == OrderItem.order_id
        ).filter(
            Order.user_id == self.user_id,
            extract('month', Order.created_at) == month,
            extract('year', Order.created_at) == year,
            Order.status == 'delivered'
        ).scalar() or 0
        
        cost = db.session.query(
            func.sum(OrderItem.quantity * StockItem.average_cost)
        ).join(
            Product, Product.id == OrderItem.product_id
        ).join(
            StockItem, StockItem.product_id == Product.id
        ).join(
            Order, Order.id == OrderItem.order_id
        ).filter(
            Order.user_id == self.user_id,
            extract('month', Order.created_at) == month,
            extract('year', Order.created_at) == year,
            Order.status == 'delivered'
        ).scalar() or 0
        
        gross_margin = 0
        if revenue > 0:
            gross_margin = ((revenue - cost) / revenue) * 100
        
        return {
            'month': f"{year}-{month:02d}",
            'revenue': float(monthly_revenue),
            'accounts_receivable': float(accounts_receivable),
            'overdue_invoices': overdue_invoices,
            'gross_margin': float(gross_margin),
            'net_profit': float(revenue - cost)
        }
    
    def get_predictive_analytics(self):
        """Análisis predictivo básico"""
        # Tendencia de ventas (regresión lineal simple)
        sales_history = db.session.query(
            func.date_trunc('day', Order.created_at).label('date'),
            func.sum(Order.total).label('revenue')
        ).filter(
            Order.user_id == self.user_id,
            Order.created_at >= datetime.utcnow() - timedelta(days=90),
            Order.status == 'delivered'
        ).group_by('date').order_by('date').all()
        
        if len(sales_history) < 7:
            return {'forecast': [], 'trend': 'insufficient_data'}
        
        # Calcular tendencia simple
        revenues = [float(row.revenue) for row in sales_history]
        avg_revenue = sum(revenues) / len(revenues)
        
        # Determinar tendencia
        recent_avg = sum(revenues[-7:]) / 7
        older_avg = sum(revenues[:7]) / 7
        
        trend = 'stable'
        if recent_avg > older_avg * 1.1:
            trend = 'growing'
        elif recent_avg < older_avg * 0.9:
            trend = 'declining'
        
        # Proyección simple para próximos 7 días
        growth_rate = (recent_avg - older_avg) / older_avg if older_avg > 0 else 0
        forecast = []
        
        for i in range(1, 8):
            projected_revenue = recent_avg * (1 + growth_rate * i / 30)
            forecast.append({
                'day': i,
                'projected_revenue': projected_revenue
            })
        
        return {
            'trend': trend,
            'avg_daily_revenue': avg_revenue,
            'growth_rate': growth_rate * 100,
            'forecast': forecast
        }
    
    def export_analytics_data(self, report_type='full'):
        """Exporta datos de analytics"""
        data = {
            'generated_at': datetime.utcnow().isoformat(),
            'business_id': self.user_id,
            'report_type': report_type
        }
        
        if report_type in ['full', 'dashboard']:
            data['dashboard_metrics'] = self.get_dashboard_metrics()
        
        if report_type in ['full', 'sales']:
            data['sales_trend'] = self.get_sales_trend()
            data['top_products'] = self.get_top_products()
            data['hourly_sales'] = self.get_sales_by_hour()
        
        if report_type in ['full', 'customers']:
            data['customer_analytics'] = self.get_customer_analytics()
        
        if report_type in ['full', 'inventory']:
            data['inventory_metrics'] = self.get_inventory_metrics()
        
        if report_type in ['full', 'financial']:
            data['financial_summary'] = self.get_financial_summary()
        
        return data
