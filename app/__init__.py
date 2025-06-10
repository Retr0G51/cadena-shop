"""
Aplicación Flask para PedidosSaaS
Factory pattern para crear la aplicación con todas las funcionalidades
"""
import os
import sys
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
    print("=== INICIANDO CREATE_APP ===", file=sys.stderr)
    app = Flask(__name__)
    
    # Cargar configuración
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    print(f"=== CONFIGURACIÓN: {config_name} ===", file=sys.stderr)
    app.config.from_object(config[config_name])
    
    # Inicializar extensiones
    print("=== INICIALIZANDO EXTENSIONES ===", file=sys.stderr)
    init_extensions(app)
    
    # Registrar blueprints
    print("=== REGISTRANDO BLUEPRINTS ===", file=sys.stderr)
    register_blueprints(app)
    
    # Registrar manejadores de errores
    print("=== REGISTRANDO ERROR HANDLERS ===", file=sys.stderr)
    register_error_handlers(app)
    
    # Configurar logging
    print("=== CONFIGURANDO LOGGING ===", file=sys.stderr)
    configure_logging(app)
    
    # Registrar comandos CLI
    print("=== REGISTRANDO CLI COMMANDS ===", file=sys.stderr)
    register_cli_commands(app)
    
    # Registrar template filters
    print("=== REGISTRANDO TEMPLATE FILTERS ===", file=sys.stderr)
    register_template_filters(app)
    
    # Registrar context processors
    print("=== REGISTRANDO CONTEXT PROCESSORS ===", file=sys.stderr)
    register_context_processors(app)
    
    # Configurar Celery si está disponible
    print("=== CONFIGURANDO CELERY ===", file=sys.stderr)
    configure_celery(app)
    
    # Crear directorios necesarios
    print("=== CREANDO DIRECTORIOS ===", file=sys.stderr)
    create_directories(app)
    
    print("=== CREATE_APP COMPLETADO ===", file=sys.stderr)
    return app

def register_blueprints(app):
    """Registra todos los blueprints de la aplicación"""
    try:
        # Blueprint principal
        print("=== IMPORTANDO BLUEPRINT MAIN ===", file=sys.stderr)
        from app.main import bp as main_bp
        print(f"=== MAIN BP IMPORTADO: {main_bp} ===", file=sys.stderr)
        app.register_blueprint(main_bp)
        print("=== MAIN BLUEPRINT REGISTRADO ===", file=sys.stderr)
        
        # Blueprint de autenticación
        print("=== IMPORTANDO BLUEPRINT AUTH ===", file=sys.stderr)
        from app.auth import bp as auth_bp
        app.register_blueprint(auth_bp, url_prefix='/auth')
        print("=== AUTH BLUEPRINT REGISTRADO ===", file=sys.stderr)
       
        # COMENTADOS TEMPORALMENTE PARA DEBUGGING
         # Blueprint del dashboard
         print("=== IMPORTANDO BLUEPRINT DASHBOARD ===", file=sys.stderr)
         from app.dashboard import bp as dashboard_bp
         app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
         print("=== DASHBOARD BLUEPRINT REGISTRADO ===", file=sys.stderr)
        
        # Blueprint de tienda pública
         print("=== IMPORTANDO BLUEPRINT PUBLIC ===", file=sys.stderr)
         from app.public import bp as public_bp
         app.register_blueprint(public_bp, url_prefix='/store')
         print("=== PUBLIC BLUEPRINT REGISTRADO ===", file=sys.stderr)
          
        # Blueprint de API
         print("=== IMPORTANDO BLUEPRINT API ===", file=sys.stderr)
         from app.api import bp as api_bp
         app.register_blueprint(api_bp, url_prefix='/api/v1')
         print("=== API BLUEPRINT REGISTRADO ===", file=sys.stderr)
        
        # Blueprint de webhooks
        # print("=== IMPORTANDO BLUEPRINT WEBHOOKS ===", file=sys.stderr)
        # from app.webhooks import bp as webhooks_bp
        # app.register_blueprint(webhooks_bp, url_prefix='/webhooks')
        # print("=== WEBHOOKS BLUEPRINT REGISTRADO ===", file=sys.stderr)
        
        print("=== TODOS LOS BLUEPRINTS REGISTRADOS ===", file=sys.stderr)
        
    except Exception as e:
        print(f"=== ERROR REGISTRANDO BLUEPRINTS: {str(e)} ===", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        raise

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
