"""
Aplicación Flask para PedidosSaaS
Factory pattern para crear la aplicación con todas las funcionalidades
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request, current_app
from flask_migrate import Migrate
from config import config
from app.extensions import (
    db, login_manager, migrate, bcrypt, csrf, mail, cors, compress,
    cache, limiter, init_extensions
)

def create_app(config_name=None):
    """
    Factory function para crear la aplicación Flask
    
    Args:
        config_name: Nombre de la configuración a usar
    
    Returns:
        Aplicación Flask configurada
    """
    app = Flask(__name__)
    
    # Cargar configuración
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app.config.from_object(config[config_name])
    
    # Inicializar extensiones
    init_extensions(app)
    
    # Registrar blueprints
    register_blueprints(app)
    
    # Registrar manejadores de errores
    register_error_handlers(app)
    
    # Configurar logging
    configure_logging(app)
    
    # Registrar comandos CLI
    register_cli_commands(app)
    
    # Registrar template filters
    register_template_filters(app)
    
    # Registrar context processors
    register_context_processors(app)
    
    # Configurar Celery si está disponible
    configure_celery(app)
    
    # Crear directorios necesarios
    create_directories(app)
    
    return app

def register_blueprints(app):
    """Registra todos los blueprints de la aplicación"""
    
    # Blueprint principal
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    # Blueprint de autenticación
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # Blueprint del dashboard
    from app.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    
    # Blueprint de tienda pública
    from app.public import bp as public_bp
    app.register_blueprint(public_bp, url_prefix='/store')
    
    # Blueprint de API
    from app.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    
    # Blueprint de webhooks
    from app.webhooks import bp as webhooks_bp
    app.register_blueprint(webhooks_bp, url_prefix='/webhooks')

def register_error_handlers(app):
    """Registra manejadores de errores personalizados"""
    
    @app.errorhandler(404)
    def not_found_error(error):
        if request.path.startswith('/api/'):
            return {'error': 'Not found'}, 404
        from flask import render_template
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(403)
    def forbidden_error(error):
        if request.path.startswith('/api/'):
            return {'error': 'Forbidden'}, 403
        from flask import render_template
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        if request.path.startswith('/api/'):
            return {'error': 'Internal server error'}, 500
        from flask import render_template
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        if request.path.startswith('/api/'):
            return {'error': 'File too large'}, 413
        from flask import render_template
        return render_template('errors/413.html'), 413
    
    @app.errorhandler(429)
    def ratelimit_handler(error):
        if request.path.startswith('/api/'):
            return {'error': 'Rate limit exceeded', 'message': error.description}, 429
        from flask import render_template
        return render_template('errors/429.html'), 429

def configure_logging(app):
    """Configura el sistema de logging"""
    
    if not app.debug and not app.testing:
        # Crear directorio de logs si no existe
        os.makedirs('logs', exist_ok=True)
        
        # Configurar rotating file handler
        file_handler = RotatingFileHandler(
            'logs/pedidossaas.log',
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=10
        )
        
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('PedidosSaaS startup')

def register_cli_commands(app):
    """Registra comandos CLI personalizados"""
    
    @app.cli.command()
    def init_db():
        """Inicializa la base de datos"""
        import subprocess
        subprocess.run(['python', 'init_db.py'])
    
    @app.cli.command()
    def create_admin():
        """Crea un usuario administrador"""
        import subprocess
        subprocess.run(['python', 'scripts/create_admin.py'])
    
    @app.cli.command()
    def create_demo():
        """Crea datos de demostración"""
        import subprocess
        subprocess.run(['python', 'scripts/create_advanced_demo.py'])
    
    @app.cli.command()
    def test():
        """Ejecuta los tests"""
        import pytest
        pytest.main(['-v', 'tests/'])

def register_template_filters(app):
    """Registra filtros personalizados para templates"""
    
    @app.template_filter('currency')
    def currency_filter(value):
        """Formatea un valor como moneda"""
        if value is None:
            return '$0.00'
        return f'${value:,.2f}'
    
    @app.template_filter('datetime')
    def datetime_filter(value, format='%d/%m/%Y %H:%M'):
        """Formatea una fecha"""
        if value is None:
            return ''
        return value.strftime(format)
    
    @app.template_filter('phone')
    def phone_filter(value):
        """Formatea un número de teléfono"""
        if not value:
            return ''
        # Formato simple, mejorar según necesidad
        if len(value) == 10:
            return f'({value[:3]}) {value[3:6]}-{value[6:]}'
        return value
    
    @app.template_filter('truncate_middle')
    def truncate_middle_filter(value, length=30):
        """Trunca texto en el medio"""
        if not value or len(value) <= length:
            return value
        half = length // 2
        return f'{value[:half]}...{value[-half:]}'

def register_context_processors(app):
    """Registra context processors globales"""
    
    @app.context_processor
    def inject_globals():
        """Inyecta variables globales a todos los templates"""
        from datetime import datetime
        return {
            'now': datetime.utcnow(),
            'app_name': 'PedidosSaaS',
            'app_version': app.config.get('APP_VERSION', '1.0.0'),
            'features': app.config.get('FEATURES', {})
        }
    
    # @app.context_processor
    # def inject_user_data():
    #     """Inyecta datos del usuario actual"""
    #     from flask_login import current_user
    #     if current_user.is_authenticated:
            # Contar notificaciones no leídas, alertas, etc.
    #        from app.models.inventory import StockAlert
            
     #       unread_alerts = StockAlert.query.filter_by(
     #           user_id=current_user.id,
     #          is_read=False
     #       ).count()
            
     #       return {
     #           'unread_alerts': unread_alerts,
     #           'user_plan': getattr(current_user, 'plan', 'free')
     #       }
     #   return {}

def configure_celery(app):
    """Configura Celery para tareas asíncronas"""
    try:
        from app.celery import make_celery
        app.celery = make_celery(app)
    except ImportError:
        app.logger.warning("Celery no está instalado. Las tareas asíncronas no estarán disponibles.")
        app.celery = None

def create_directories(app):
    """Crea directorios necesarios para la aplicación"""
    directories = [
        'logs',
        'backups',
        'exports',
        'temp',
        'app/static/uploads/products',
        'app/static/uploads/products/thumb',
        'app/static/uploads/products/small',
        'app/static/uploads/products/medium',
        'app/static/uploads/logos',
        'app/static/uploads/invoices'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        
        # Crear .gitkeep en directorios vacíos
        gitkeep_path = os.path.join(directory, '.gitkeep')
        if not os.path.exists(gitkeep_path):
            open(gitkeep_path, 'a').close()

# Función helper para crear la app con contexto
def create_app_with_context():
    """Crea la aplicación con contexto activo (útil para scripts)"""
    app = create_app()
    app.app_context().push()
    return app

# Configuración de Shell Context
def make_shell_context():
    """Crea el contexto para flask shell"""
    from app.models import (
        User, Product, Order, OrderItem,
        Customer, Invoice, Warehouse, StockItem
    )
    
    return {
        'db': db,
        'User': User,
        'Product': Product,
        'Order': Order,
        'OrderItem': OrderItem,
        'Customer': Customer,
        'Invoice': Invoice,
        'Warehouse': Warehouse,
        'StockItem': StockItem
    }

# Variable global para mantener referencia a la app
_app = None

def get_app():
    """Obtiene la instancia de la aplicación (singleton)"""
    global _app
    if _app is None:
        _app = create_app()
    return _app
