"""
Rutas y lógica para Analytics Dashboard con optimizaciones para conexiones lentas
"""

from flask import render_template, jsonify, request, send_file, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, and_, extract
from datetime import datetime, timedelta
import json
import io
import csv
from app.dashboard import bp
from app.models import Order, OrderItem, Product, User
from app.utils.decorators import active_business_required
from app.extensions import db
from app.utils.cache import cache_analytics  # Implementaremos cache


@bp.route('/analytics')
@login_required
@active_business_required
def analytics():
    """Vista principal del dashboard analytics"""
    # Datos básicos para la carga inicial (optimizado)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    # KPIs principales - consulta optimizada
    kpis = get_kpis_summary(current_user.id, start_date, end_date)
    
    # Estado de pedidos - usando agregación
    order_status_summary = db.session.query(
        Order.status, 
        func.count(Order.id)
    ).filter(
        Order.user_id == current_user.id,
        Order.created_at >= start_date
    ).group_by(Order.status).all()
    
    order_status_dict = {status: count for status, count in order_status_summary}
    
    # Top 5 productos para vista rápida (no los 10)
    product_performance = db.session.query(
        Product.id,
        Product.name,
        Product.category,
        Product.image,
        Product.stock,
        func.sum(OrderItem.quantity).label('units_sold'),
        func.sum(OrderItem.subtotal).label('revenue')
    ).join(
        OrderItem, Product.id == OrderItem.product_id
    ).join(
        Order, OrderItem.order_id == Order.id
    ).filter(
        Product.user_id == current_user.id,
        Order.created_at >= start_date,
        Order.status != 'cancelled'
    ).group_by(
        Product.id
    ).order_by(
        func.sum(OrderItem.subtotal).desc()
    ).limit(5).all()
    
    return render_template('dashboard/analytics.html',
        **kpis,
        order_status_summary=order_status_dict,
        product_performance=product_performance
    )


@bp.route('/analytics/data')
@login_required
@active_business_required
@cache_analytics(timeout=300)  # Cache por 5 minutos
def analytics_data():
    """API endpoint para datos de analytics (AJAX)"""
    period = request.args.get('period', '30', type=int)
    
    # Validar período
    if period not in [7, 30, 90, 365]:
        period = 30
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=period)
    
    try:
        # Obtener datos con consultas optimizadas
        analytics_data = {
            'sales_trend': get_sales_trend(current_user.id, start_date, end_date, period),
            'top_products': get_top_products(current_user.id, start_date, end_date),
            'categories': get_category_distribution(current_user.id, start_date, end_date),
            'peak_hours': get_peak_hours(current_user.id, start_date, end_date)
        }
        
        kpis = get_kpis_summary(current_user.id, start_date, end_date)
        
        return jsonify({
            'success': True,
            'analytics': analytics_data,
            'kpis': kpis
        })
    except Exception as e:
        current_app.logger.error(f"Error en analytics_data: {str(e)}")
        return jsonify({'success': False, 'message': 'Error al cargar datos'}), 500


def get_kpis_summary(user_id, start_date, end_date):
    """Obtiene KPIs resumidos con comparación de período anterior"""
    # Período actual
    current_stats = db.session.query(
        func.count(Order.id).label('total_orders'),
        func.sum(Order.total).label('total_revenue'),
        func.avg(Order.total).label('avg_ticket'),
        func.count(func.distinct(
            func.date(Order.created_at)
        )).label('active_days')
    ).filter(
        Order.user_id == user_id,
        Order.created_at.between(start_date, end_date),
        Order.status != 'cancelled'
    ).first()
    
    # Período anterior (mismo número de días)
    period_days = (end_date - start_date).days
    prev_end_date = start_date
    prev_start_date = prev_end_date - timedelta(days=period_days)
    
    prev_stats = db.session.query(
        func.count(Order.id).label('total_orders'),
        func.sum(Order.total).label('total_revenue')
    ).filter(
        Order.user_id == user_id,
        Order.created_at.between(prev_start_date, prev_end_date),
        Order.status != 'cancelled'
    ).first()
    
    # Calcular cambios porcentuales
    def calculate_change(current, previous):
        if not previous or previous == 0:
            return 0
        return round(((current - previous) / previous) * 100, 1)
    
    total_revenue = float(current_stats.total_revenue or 0)
    total_orders = int(current_stats.total_orders or 0)
    avg_ticket = float(current_stats.avg_ticket or 0)
    
    prev_revenue = float(prev_stats.total_revenue or 0)
    prev_orders = int(prev_stats.total_orders or 0)
    
    # Pedidos de hoy
    today_orders = db.session.query(func.count(Order.id)).filter(
        Order.user_id == user_id,
        func.date(Order.created_at) == datetime.utcnow().date()
    ).scalar() or 0
    
    # Tasa de conversión (simulada por ahora)
    completed_orders = total_orders
    total_visits = total_orders * 3  # Estimación simple
    conversion_rate = round((completed_orders / total_visits * 100) if total_visits > 0 else 0, 1)
    
    return {
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'avg_ticket': avg_ticket,
        'new_orders': today_orders,
        'revenue_change': calculate_change(total_revenue, prev_revenue),
        'orders_change': calculate_change(total_orders, prev_orders),
        'avg_ticket_change': calculate_change(avg_ticket, prev_revenue / prev_orders if prev_orders > 0 else 0),
        'conversion_rate': conversion_rate,
        'completed_orders': completed_orders,
        'total_visits': total_visits
    }


def get_sales_trend(user_id, start_date, end_date, period):
    """Obtiene tendencia de ventas optimizada para el período"""
    # Agrupar por día, semana o mes según el período
    if period <= 30:
        # Agrupar por día
        date_format = func.date(Order.created_at)
        group_format = '%d/%m'
    elif period <= 90:
        # Agrupar por semana
        date_format = func.date_trunc('week', Order.created_at)
        group_format = 'Sem %W'
    else:
        # Agrupar por mes
        date_format = func.date_trunc('month', Order.created_at)
        group_format = '%b %Y'
    
    sales_data = db.session.query(
        date_format.label('date'),
        func.sum(Order.total).label('revenue'),
        func.count(Order.id).label('orders')
    ).filter(
        Order.user_id == user_id,
        Order.created_at.between(start_date, end_date),
        Order.status != 'cancelled'
    ).group_by(date_format).order_by(date_format).all()
    
    # Formatear para Chart.js
    labels = []
    revenue_data = []
    orders_data = []
    
    for row in sales_data:
        if period <= 30:
            labels.append(row.date.strftime('%d/%m'))
        else:
            labels.append(row.date.strftime(group_format))
        revenue_data.append(float(row.revenue or 0))
        orders_data.append(int(row.orders or 0))
    
    return {
        'labels': labels,
        'data': revenue_data,
        'orders': orders_data
    }


def get_top_products(user_id, start_date, end_date, limit=10):
    """Obtiene los productos más vendidos"""
    products = db.session.query(
        Product.name,
        func.sum(OrderItem.quantity).label('units_sold')
    ).join(
        OrderItem, Product.id == OrderItem.product_id
    ).join(
        Order, OrderItem.order_id == Order.id
    ).filter(
        Product.user_id == user_id,
        Order.created_at.between(start_date, end_date),
        Order.status != 'cancelled'
    ).group_by(
        Product.id, Product.name
    ).order_by(
        func.sum(OrderItem.quantity).desc()
    ).limit(limit).all()
    
    return {
        'labels': [p.name[:20] + '...' if len(p.name) > 20 else p.name for p in products],
        'data': [int(p.units_sold) for p in products]
    }


def get_category_distribution(user_id, start_date, end_date):
    """Obtiene distribución de ventas por categoría"""
    categories = db.session.query(
        func.coalesce(Product.category, 'Sin categoría').label('category'),
        func.sum(OrderItem.subtotal).label('revenue')
    ).join(
        OrderItem, Product.id == OrderItem.product_id
    ).join(
        Order, OrderItem.order_id == Order.id
    ).filter(
        Product.user_id == user_id,
        Order.created_at.between(start_date, end_date),
        Order.status != 'cancelled'
    ).group_by(
        Product.category
    ).order_by(
        func.sum(OrderItem.subtotal).desc()
    ).limit(5).all()  # Top 5 categorías
    
    return {
        'labels': [c.category for c in categories],
        'data': [float(c.revenue) for c in categories]
    }


def get_peak_hours(user_id, start_date, end_date):
    """Obtiene las horas de mayor actividad"""
    # Agrupar pedidos por hora del día
    hours_data = db.session.query(
        extract('hour', Order.created_at).label('hour'),
        func.count(Order.id).label('orders')
    ).filter(
        Order.user_id == user_id,
        Order.created_at.between(start_date, end_date)
    ).group_by(
        extract('hour', Order.created_at)
    ).all()
    
    # Crear array de 24 horas
    hours_dict = {int(h.hour): int(h.orders) for h in hours_data}
    
    labels = []
    data = []
    
    for hour in range(24):
        if hour == 0:
            label = '12 AM'
        elif hour < 12:
            label = f'{hour} AM'
        elif hour == 12:
            label = '12 PM'
        else:
            label = f'{hour - 12} PM'
        
        labels.append(label)
        data.append(hours_dict.get(hour, 0))
    
    return {
        'labels': labels,
        'data': data
    }


@bp.route('/analytics/export')
@login_required
@active_business_required
def export_analytics():
    """Exporta reporte de analytics en CSV (ligero para conexiones lentas)"""
    period = request.args.get('period', '30', type=int)
    format_type = request.args.get('format', 'csv')
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=period)
    
    # Obtener datos
    orders = Order.query.filter(
        Order.user_id == current_user.id,
        Order.created_at.between(start_date, end_date)
    ).order_by(Order.created_at.desc()).all()
    
    if format_type == 'csv':
        # Crear CSV en memoria
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Headers
        writer.writerow([
            'Fecha', 'Número Pedido', 'Cliente', 'Total', 
            'Estado', 'Productos', 'Cantidad Total'
        ])
        
        # Datos
        for order in orders:
            total_items = sum(item.quantity for item in order.items)
            products = ', '.join([item.product.name for item in order.items])
            
            writer.writerow([
                order.created_at.strftime('%Y-%m-%d %H:%M'),
                order.order_number,
                order.customer_name,
                f"${order.total:.2f}",
                order.get_status_display(),
                products,
                total_items
            ])
        
        # Preparar descarga
        output.seek(0)
        output_bytes = io.BytesIO(output.getvalue().encode('utf-8-sig'))  # UTF-8 with BOM para Excel
        
        return send_file(
            output_bytes,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'reporte_ventas_{datetime.now().strftime("%Y%m%d")}.csv'
        )
    
    return jsonify({'error': 'Formato no soportado'}), 400


# Función auxiliar para cache
def cache_analytics(timeout=300):
    """
    Decorador simple para cachear respuestas de analytics
    En producción usar Redis o Memcached
    """
    def decorator(f):
        from functools import wraps
        cache = {}
        
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Crear key única basada en user_id y parámetros
            cache_key = f"{current_user.id}:{request.args.get('period', '30')}"
            
            # Verificar cache
            if cache_key in cache:
                cached_data, timestamp = cache[cache_key]
                if datetime.utcnow() - timestamp < timedelta(seconds=timeout):
                    return cached_data
            
            # Obtener datos frescos
            result = f(*args, **kwargs)
            
            # Guardar en cache
            cache[cache_key] = (result, datetime.utcnow())
            
            # Limpiar cache viejo (simple estrategia)
            if len(cache) > 100:
                oldest_key = min(cache.keys(), key=lambda k: cache[k][1])
                del cache[oldest_key]
            
            return result
        
        return decorated_function
    return decorator
