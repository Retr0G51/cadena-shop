"""
Rutas principales de la aplicación
Incluye landing page y health checks
"""
from flask import render_template, jsonify, request
from flask_login import current_user
from datetime import datetime
from app.main import bp
from app.extensions import db
from app.models import User, Product, Order
from app.utils.cache import cache
import os
from sqlalchemy import text

@bp.route('/')
def index():
    """Página principal / Landing page - VERSIÓN DEBUG"""
    try:
        return "🎉 ¡PedidosSaaS funcionando! La app está corriendo correctamente.", 200
    except Exception as e:
        return f"Error: {str(e)}", 500

@bp.route('/features')
def features():
    """Página de características"""
    return render_template('main/features.html')

@bp.route('/pricing')
def pricing():
    """Página de precios"""
    plans = [
        {
            'name': 'Básico',
            'price': 0,
            'features': [
                'Hasta 50 productos',
                'Hasta 100 pedidos/mes',
                'Panel de administración',
                'Soporte por email'
            ]
        },
        {
            'name': 'Profesional',
            'price': 29,
            'features': [
                'Productos ilimitados',
                'Pedidos ilimitados',
                'Facturación electrónica',
                'Gestión de inventario',
                'Reportes avanzados',
                'Soporte prioritario'
            ]
        },
        {
            'name': 'Empresa',
            'price': 99,
            'features': [
                'Todo lo del plan Profesional',
                'Multi-almacén',
                'API completa',
                'CRM integrado',
                'Campañas de marketing',
                'Soporte 24/7',
                'Personalización'
            ]
        }
    ]
    return render_template('main/pricing.html', plans=plans)

@bp.route('/contact')
def contact():
    """Página de contacto"""
    return render_template('main/contact.html')

@bp.route('/health')
def health_check():
    """
    Health check endpoint para monitoreo
    Usado por Railway, Render y otros servicios
    """
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': os.environ.get('APP_VERSION', '1.0.0'),
        'checks': {}
    }
    
    # Check database
    try:
        db.session.execute(text('SELECT 1'))
        health_status['checks']['database'] = {
            'status': 'up',
            'response_time_ms': 0
        }
    except Exception as e:
        health_status['status'] = 'unhealthy'
        health_status['checks']['database'] = {
            'status': 'down',
            'error': str(e)
        }
    
    # Check Redis/Cache
    try:
        cache.set('health_check', 'ok', ttl=10)
        if cache.get('health_check') == 'ok':
            health_status['checks']['cache'] = {
                'status': 'up',
                'type': 'redis' if cache.redis_client else 'memory'
            }
        else:
            raise Exception("Cache write/read failed")
    except Exception as e:
        health_status['checks']['cache'] = {
            'status': 'down',
            'error': str(e)
        }
    
    # Check disk space
    try:
        import shutil
        disk_usage = shutil.disk_usage('/')
        free_percentage = (disk_usage.free / disk_usage.total) * 100
        
        health_status['checks']['disk'] = {
            'status': 'up' if free_percentage > 10 else 'warning',
            'free_percentage': round(free_percentage, 2)
        }
    except:
        health_status['checks']['disk'] = {'status': 'unknown'}
    
    # Determine HTTP status code
    if health_status['status'] == 'unhealthy':
        status_code = 503
    else:
        status_code = 200
    
    return jsonify(health_status), status_code

@bp.route('/status')
def status():
    """
    Status page más detallado para administradores
    """
    if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
        return jsonify({'error': 'Unauthorized'}), 401
    
    status_info = {
        'application': {
            'version': os.environ.get('APP_VERSION', '1.0.0'),
            'environment': os.environ.get('FLASK_ENV', 'production'),
            'debug': os.environ.get('DEBUG', 'False') == 'True',
            'workers': os.environ.get('WEB_CONCURRENCY', '1')
        },
        'database': {
            'url': 'configured' if os.environ.get('DATABASE_URL') else 'not configured',
            'pool_size': db.engine.pool.size() if hasattr(db.engine.pool, 'size') else 'N/A'
        },
        'cache': {
            'backend': 'redis' if cache.redis_client else 'memory',
            'stats': cache.get_stats()
        },
        'statistics': {
            'total_users': User.query.count(),
            'active_users': User.query.filter_by(is_active=True).count(),
            'total_products': Product.query.count(),
            'total_orders': Order.query.count()
        },
        'system': {
            'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
            'platform': os.sys.platform
        }
    }
    
    return jsonify(status_info)

@bp.route('/robots.txt')
def robots():
    """Robots.txt para SEO"""
    return """User-agent: *
Disallow: /dashboard/
Disallow: /admin/
Disallow: /api/
Disallow: /static/uploads/
Allow: /
Sitemap: /sitemap.xml
""", 200, {'Content-Type': 'text/plain'}

@bp.route('/sitemap.xml')
def sitemap():
    """Sitemap básico para SEO"""
    pages = []
    
    # Páginas estáticas
    static_pages = ['index', 'features', 'pricing', 'contact']
    for page in static_pages:
        pages.append({
            'loc': url_for(f'main.{page}', _external=True),
            'changefreq': 'weekly',
            'priority': '0.8' if page == 'index' else '0.6'
        })
    
    # Tiendas públicas activas (si quieres incluirlas)
    # for user in User.query.filter_by(is_active=True).limit(100):
    #     pages.append({
    #         'loc': url_for('public.store', username=user.username, _external=True),
    #         'changefreq': 'daily',
    #         'priority': '0.7'
    #     })
    
    sitemap_xml = render_template('main/sitemap.xml', pages=pages)
    response = make_response(sitemap_xml)
    response.headers["Content-Type"] = "application/xml"
    
    return response

@bp.route('/terms')
def terms():
    """Términos y condiciones"""
    return render_template('main/terms.html')

@bp.route('/privacy')
def privacy():
    """Política de privacidad"""
    return render_template('main/privacy.html')

@bp.route('/api-docs')
def api_docs():
    """Documentación de API"""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    
    return render_template('main/api_docs.html')

# Error handlers
@bp.app_errorhandler(404)
def not_found_error(error):
    """Manejo de error 404"""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    return render_template('errors/404.html'), 404

@bp.app_errorhandler(500)
def internal_error(error):
    """Manejo de error 500"""
    db.session.rollback()
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('errors/500.html'), 500

@bp.app_errorhandler(403)
def forbidden_error(error):
    """Manejo de error 403"""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Forbidden'}), 403
    return render_template('errors/403.html'), 403

@bp.app_errorhandler(413)
def request_entity_too_large(error):
    """Manejo de error 413 - Archivo muy grande"""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'File too large'}), 413
    return render_template('errors/413.html'), 413
