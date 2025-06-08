"""
API de analytics para PedidosSaaS
Proporciona datos analíticos y reportes vía API
"""
from flask import jsonify, request
from datetime import datetime, timedelta
from app.api import bp
from app.api.auth import token_required
from app.dashboard.analytics import Analytics
from app.models import User

@bp.route('/analytics/dashboard', methods=['GET'])
@token_required
def get_dashboard_analytics():
    """
    Obtiene métricas del dashboard principal
    
    Query params:
        - date_from: Fecha inicial (YYYY-MM-DD)
        - date_to: Fecha final (YYYY-MM-DD)
        - period: today, week, month, quarter, year
    
    Returns:
        Métricas principales del negocio
    """
    user = request.current_api_user
    analytics = Analytics(user.id)
    
    # Parsear fechas
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    period = request.args.get('period', 'month')
    
    if not date_from or not date_to:
        # Usar período predefinido
        now = datetime.utcnow()
        if period == 'today':
            date_from = now.replace(hour=0, minute=0, second=0, microsecond=0)
            date_to = now
        elif period == 'week':
            date_from = now - timedelta(days=7)
            date_to = now
        elif period == 'month':
            date_from = now - timedelta(days=30)
            date_to = now
        elif period == 'quarter':
            date_from = now - timedelta(days=90)
            date_to = now
        elif period == 'year':
            date_from = now - timedelta(days=365)
            date_to = now
    else:
        date_from = datetime.strptime(date_from, '%Y-%m-%d')
        date_to = datetime.strptime(date_to, '%Y-%m-%d')
    
    metrics = analytics.get_dashboard_metrics(date_from, date_to)
    
    return jsonify({
        'success': True,
        'data': metrics
    })

@bp.route('/analytics/sales', methods=['GET'])
@token_required
def get_sales_analytics():
    """
    Obtiene análisis de ventas detallado
    
    Query params:
        - period: daily, weekly, monthly
        - days: Número de días a analizar (default: 30)
        - group_by: date, product, category, customer
    
    Returns:
        Datos de ventas agrupados
    """
    user = request.current_api_user
    analytics = Analytics(user.id)
    
    period = request.args.get('period', 'daily')
    days = request.args.get('days', 30, type=int)
    group_by = request.args.get('group_by', 'date')
    
    # Obtener tendencia de ventas
    sales_trend = analytics.get_sales_trend(period, days)
    
    # Productos más vendidos
    top_products = analytics.get_top_products(limit=10, days=days)
    
    # Ventas por hora
    hourly_sales = analytics.get_sales_by_hour(days=min(days, 7))
    
    # Rendimiento por categoría
    category_performance = analytics.get_category_performance()
    
    return jsonify({
        'success': True,
        'data': {
            'sales_trend': sales_trend,
            'top_products': top_products,
            'hourly_distribution': hourly_sales,
            'category_performance': category_performance,
            'period': {
                'type': period,
                'days': days
            }
        }
    })

@bp.route('/analytics/customers', methods=['GET'])
@token_required
def get_customer_analytics():
    """
    Obtiene análisis de clientes
    
    Returns:
        Métricas y segmentación de clientes
    """
    user = request.current_api_user
    analytics = Analytics(user.id)
    
    customer_data = analytics.get_customer_analytics()
    
    return jsonify({
        'success': True,
        'data': customer_data
    })

@bp.route('/analytics/inventory', methods=['GET'])
@token_required
def get_inventory_analytics():
    """
    Obtiene análisis de inventario
    
    Returns:
        Métricas de inventario y rotación
    """
    user = request.current_api_user
    analytics = Analytics(user.id)
    
    inventory_metrics = analytics.get_inventory_metrics()
    
    return jsonify({
        'success': True,
        'data': inventory_metrics
    })

@bp.route('/analytics/financial', methods=['GET'])
@token_required
def get_financial_analytics():
    """
    Obtiene resumen financiero
    
    Query params:
        - month: Mes (1-12)
        - year: Año
    
    Returns:
        Métricas financieras del período
    """
    user = request.current_api_user
    analytics = Analytics(user.id)
    
    month = request.args.get('month', datetime.utcnow().month, type=int)
    year = request.args.get('year', datetime.utcnow().year, type=int)
    
    financial_summary = analytics.get_financial_summary(month, year)
    
    return jsonify({
        'success': True,
        'data': financial_summary
    })

@bp.route('/analytics/predictive', methods=['GET'])
@token_required
def get_predictive_analytics():
    """
    Obtiene análisis predictivo básico
    
    Returns:
        Tendencias y proyecciones
    """
    user = request.current_api_user
    analytics = Analytics(user.id)
    
    predictive_data = analytics.get_predictive_analytics()
    
    return jsonify({
        'success': True,
        'data': predictive_data
    })

@bp.route('/analytics/reports/generate', methods=['POST'])
@token_required
def generate_report():
    """
    Genera un reporte personalizado
    
    Body:
        {
            "report_type": "sales|customers|inventory|financial|full",
            "date_from": "2024-01-01",
            "date_to": "2024-01-31",
            "format": "json|csv|pdf",
            "filters": {
                "categories": ["Bebidas", "Comidas"],
                "products": [1, 2, 3]
            }
        }
    
    Returns:
        URL de descarga del reporte o datos JSON
    """
    user = request.current_api_user
    data = request.get_json()
    
    report_type = data.get('report_type', 'full')
    format_type = data.get('format', 'json')
    
    # Validar fechas
    try:
        date_from = datetime.strptime(data.get('date_from'), '%Y-%m-%d')
        date_to = datetime.strptime(data.get('date_to'), '%Y-%m-%d')
    except:
        return jsonify({
            'success': False,
            'message': 'Invalid date format. Use YYYY-MM-DD'
        }), 400
    
    analytics = Analytics(user.id)
    
    # Generar datos del reporte
    report_data = {
        'metadata': {
            'business_name': user.business_name,
            'report_type': report_type,
            'period': {
                'from': date_from.isoformat(),
                'to': date_to.isoformat()
            },
            'generated_at': datetime.utcnow().isoformat()
        }
    }
    
    # Agregar secciones según el tipo de reporte
    if report_type in ['sales', 'full']:
        report_data['sales'] = {
            'metrics': analytics.get_dashboard_metrics(date_from, date_to),
            'trend': analytics.get_sales_trend('daily', (date_to - date_from).days),
            'top_products': analytics.get_top_products(20, (date_to - date_from).days)
        }
    
    if report_type in ['customers', 'full']:
        report_data['customers'] = analytics.get_customer_analytics()
    
    if report_type in ['inventory', 'full']:
        report_data['inventory'] = analytics.get_inventory_metrics()
    
    if report_type in ['financial', 'full']:
        report_data['financial'] = []
        # Generar resumen financiero para cada mes en el rango
        current = date_from
        while current <= date_to:
            monthly_summary = analytics.get_financial_summary(
                current.month, 
                current.year
            )
            report_data['financial'].append(monthly_summary)
            # Avanzar al siguiente mes
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
    
    # Formatear según el tipo solicitado
    if format_type == 'json':
        return jsonify({
            'success': True,
            'data': report_data
        })
    
    elif format_type == 'csv':
        # Generar CSV
        from app.utils.helpers import export_to_csv
        import io
        
        # Convertir datos a formato tabular
        csv_data = []
        
        if 'sales' in report_data and 'top_products' in report_data['sales']:
            for product in report_data['sales']['top_products']:
                csv_data.append({
                    'Producto': product['name'],
                    'Cantidad Vendida': product['quantity_sold'],
                    'Ingresos': product['revenue'],
                    'Pedidos': product['order_count']
                })
        
        csv_file = export_to_csv(csv_data, 'report.csv')
        
        from flask import send_file
        return send_file(
            csv_file,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'report_{report_type}_{datetime.utcnow().strftime("%Y%m%d")}.csv'
        )
    
    elif format_type == 'pdf':
        # Para PDF, usar tarea asíncrona
        if hasattr(user, 'celery') and user.celery:
            from app.celery import generate_report_async
            
            task = generate_report_async.delay(
                user.id,
                report_type,
                {
                    'date_from': date_from.isoformat(),
                    'date_to': date_to.isoformat(),
                    'format': 'pdf'
                }
            )
            
            return jsonify({
                'success': True,
                'message': 'Report generation started',
                'task_id': task.id,
                'status_url': f'/api/v1/analytics/reports/status/{task.id}'
            }), 202
        else:
            return jsonify({
                'success': False,
                'message': 'PDF generation not available'
            }), 501

@bp.route('/analytics/reports/status/<task_id>', methods=['GET'])
@token_required
def get_report_status(task_id):
    """
    Obtiene el estado de generación de un reporte
    
    Args:
        task_id: ID de la tarea de Celery
    
    Returns:
        Estado y URL de descarga si está listo
    """
    from app.celery import celery
    
    if not celery:
        return jsonify({
            'success': False,
            'message': 'Task system not available'
        }), 501
    
    task = celery.AsyncResult(task_id)
    
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'status': 'Report generation pending...'
        }
    elif task.state == 'SUCCESS':
        response = {
            'state': task.state,
            'status': 'Report ready',
            'result': task.result
        }
    elif task.state == 'FAILURE':
        response = {
            'state': task.state,
            'status': 'Report generation failed',
            'error': str(task.info)
        }
    else:
        response = {
            'state': task.state,
            'status': 'Processing...'
        }
    
    return jsonify(response)

@bp.route('/analytics/export', methods=['GET'])
@token_required
def export_analytics():
    """
    Exporta datos analíticos en formato bruto
    
    Query params:
        - type: Tipo de datos a exportar
        - format: json o csv
    
    Returns:
        Archivo de exportación
    """
    user = request.current_api_user
    analytics = Analytics(user.id)
    
    export_type = request.args.get('type', 'full')
    format_type = request.args.get('format', 'json')
    
    data = analytics.export_analytics_data(export_type)
    
    if format_type == 'json':
        return jsonify({
            'success': True,
            'data': data
        })
    else:
        # Implementar exportación CSV según necesidad
        return jsonify({
            'success': False,
            'message': 'CSV export not implemented for this endpoint'
        }), 501

# Namespace para documentación
api_analytics = {
    'name': 'Analytics',
    'description': 'Business analytics and reporting endpoints',
    'endpoints': [
        {
            'path': '/analytics/dashboard',
            'method': 'GET',
            'description': 'Get dashboard metrics',
            'auth_required': True
        },
        {
            'path': '/analytics/sales',
            'method': 'GET',
            'description': 'Get sales analytics',
            'auth_required': True
        },
        {
            'path': '/analytics/customers',
            'method': 'GET',
            'description': 'Get customer analytics',
            'auth_required': True
        },
        {
            'path': '/analytics/inventory',
            'method': 'GET',
            'description': 'Get inventory analytics',
            'auth_required': True
        },
        {
            'path': '/analytics/financial',
            'method': 'GET',
            'description': 'Get financial summary',
            'auth_required': True
        },
        {
            'path': '/analytics/predictive',
            'method': 'GET',
            'description': 'Get predictive analytics',
            'auth_required': True
        },
        {
            'path': '/analytics/reports/generate',
            'method': 'POST',
            'description': 'Generate custom report',
            'auth_required': True
        },
        {
            'path': '/analytics/reports/status/{task_id}',
            'method': 'GET',
            'description': 'Check report generation status',
            'auth_required': True
        },
        {
            'path': '/analytics/export',
            'method': 'GET',
            'description': 'Export analytics data',
            'auth_required': True
        }
    ]
}
