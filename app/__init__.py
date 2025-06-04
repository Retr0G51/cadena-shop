"""
PedidosSaaS - Sistema de Pedidos Online Multiusuario
Versión 2.0 con funcionalidades empresariales
"""

__version__ = '2.0.0'
__author__ = 'Bruno Bernal'

import os
from flask import Flask, g
from flask_login import current_user
from flask_wtf.csrf import generate_csrf
from config import config
from app.extensions import db, login_manager, bcrypt, migrate
from app.utils.performance import PerformanceOptimizer, DatabaseOptimizer, compress_static_files
from app.automation.tasks import automation_system


def create_app(config_name=None):
    """Factory Pattern para crear la aplicación Flask con todas las funcionalidades"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Inicializar extensiones
    init_extensions(app)
    
    # Registrar blueprints
    register_blueprints(app)
    
    # Crear directorios necesarios
    create_directories(app)
    
    # Configurar login manager
    configure_login_manager(app)
    
    # Registrar context processors
    register_context_processors(app)
    
    # Aplicar optimizaciones de rendimiento
    apply_performance_optimizations(app)
    
    # Inicializar sistema de automatización
    if app.config.get('ENABLE_AUTOMATION', True):
        automation_system.init_app(app)
    
    # Registrar comandos CLI
    register_cli_commands(app)
    
    # Extender modelos existentes
    with app.app_context():
        extend_models()
    
    return app


def init_extensions(app):
    """Inicializa las extensiones Flask"""
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)


def register_blueprints(app):
    """Registra todos los blueprints incluyendo los nuevos"""
    from app.main import bp as main_bp
    from app.auth import bp as auth_bp
    from app.dashboard import bp as dashboard_bp
    from app.public import bp as public_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(public_bp, url_prefix='/tienda')
    
    # Registrar rutas de analytics
    from app.dashboard.analytics import bp as analytics_bp
    app.register_blueprint(analytics_bp, url_prefix='/dashboard/analytics')
    
    # Registrar API si está habilitada
    if app.config.get('ENABLE_API', True):
        from app.api import bp as api_bp
        app.register_blueprint(api_bp, url_prefix='/api/v1')


def create_directories(app):
    """Crea los directorios necesarios"""
    directories = [
        app.config['UPLOAD_FOLDER'],
        os.path.join(app.config['UPLOAD_FOLDER'], 'products'),
        os.path.join(app.config['UPLOAD_FOLDER'], 'products', 'thumb'),
        os.path.join(app.config['UPLOAD_FOLDER'], 'products', 'small'),
        os.path.join(app.config['UPLOAD_FOLDER'], 'products', 'medium'),
        os.path.join(app.config['UPLOAD_FOLDER'], 'logos'),
        os.path.join(app.config['UPLOAD_FOLDER'], 'invoices'),
        'logs',
        'backups',
        'exports'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def configure_login_manager(app):
    """Configura Flask-Login"""
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))


def register_context_processors(app):
    """Registra variables globales para templates"""
    @app.context_processor
    def inject_globals():
        return {
            'current_user': current_user,
            'site_name': 'PedidosSaaS',
            'version': __version__
        }
    
    @app.context_processor
    def inject_csrf_token():
        """Inyecta csrf_token en todos los templates"""
        def generate_csrf_token():
            if '_csrf_token' not in g:
                g._csrf_token = generate_csrf()
            return g._csrf_token
        return dict(csrf_token=generate_csrf_token)
    
    @app.context_processor
    def utility_functions():
        """Funciones útiles para templates"""
        from app.utils.helpers import format_currency
        from datetime import datetime
        
        def format_datetime(dt, format='%d/%m/%Y %H:%M'):
            """Formatea datetime para mostrar"""
            if dt:
                return dt.strftime(format)
            return ''
        
        def time_ago(dt):
            """Muestra tiempo transcurrido de forma amigable"""
            if not dt:
                return ''
            
            diff = datetime.utcnow() - dt
            
            if diff.days > 365:
                return f"hace {diff.days // 365} año{'s' if diff.days // 365 > 1 else ''}"
            elif diff.days > 30:
                return f"hace {diff.days // 30} mes{'es' if diff.days // 30 > 1 else ''}"
            elif diff.days > 0:
                return f"hace {diff.days} día{'s' if diff.days > 1 else ''}"
            elif diff.seconds > 3600:
                return f"hace {diff.seconds // 3600} hora{'s' if diff.seconds // 3600 > 1 else ''}"
            elif diff.seconds > 60:
                return f"hace {diff.seconds // 60} minuto{'s' if diff.seconds // 60 > 1 else ''}"
            else:
                return "hace un momento"
        
        return dict(
            format_currency=format_currency,
            format_datetime=format_datetime,
            time_ago=time_ago
        )


def apply_performance_optimizations(app):
    """Aplica todas las optimizaciones de rendimiento"""
    # Inicializar optimizador
    PerformanceOptimizer.init_app(app)
    
    # Comprimir archivos estáticos en producción
    if app.config.get('ENV') == 'production':
        compress_static_files(app)
    
    # Crear índices de base de datos
    @app.before_first_request
    def create_db_indexes():
        DatabaseOptimizer.create_indexes(db)
    
    # Configurar caché de consultas
    @app.before_request
    def before_request():
        g.request_start_time = datetime.utcnow()
    
    @app.after_request
    def after_request(response):
        if hasattr(g, 'request_start_time'):
            elapsed = datetime.utcnow() - g.request_start_time
            response.headers['X-Response-Time'] = str(elapsed.total_seconds())
        return response


def register_cli_commands(app):
    """Registra comandos CLI personalizados"""
    @app.cli.command()
    def init_db():
        """Inicializar la base de datos con todas las tablas"""
        db.create_all()
        print("✅ Base de datos inicializada!")
    
    @app.cli.command()
    def create_indexes():
        """Crear índices de base de datos para optimización"""
        DatabaseOptimizer.create_indexes(db)
        print("✅ Índices creados!")
    
    @app.cli.command()
    def run_automation():
        """Ejecutar tareas de automatización manualmente"""
        automation_system.daily_tasks()
        print("✅ Tareas de automatización ejecutadas!")
    
    @app.cli.command()
    def backup_db():
        """Crear backup de la base de datos"""
        automation_system.backup_database()
        print("✅ Backup creado!")
    
    @app.cli.command()
    def generate_demo_data():
        """Generar datos de demostración avanzados"""
        from scripts.create_advanced_demo import create_advanced_demo_data
        create_advanced_demo_data()
        print("✅ Datos de demostración avanzados creados!")


def extend_models():
    """Extiende modelos existentes con nuevas funcionalidades"""
    # Importar modelos
    from app.models import User, Product, Order
    from app.models.inventory import extend_product_model
    
    # Extender modelo Product con campos de inventario
    extend_product_model()
    
    # Agregar campos a User si no existen
    if not hasattr(User, 'notification_preferences'):
        User.notification_preferences = db.Column(db.JSON, default={
            'daily_summary': True,
            'low_stock_alerts': True,
            'new_orders': True,
            'payment_reminders': True,
            'weekly_reports': True
        })
    
    if not hasattr(User, 'business_settings'):
        User.business_settings = db.Column(db.JSON, default={
            'tax_rate': 0,
            'invoice_footer': '',
            'order_confirmation_message': 'Gracias por tu pedido!'
        })
    
    # Agregar método para obtener configuración
    def get_setting(self, key, default=None):
        if self.business_settings:
            return self.business_settings.get(key, default)
        return default
    
    User.get_setting = get_setting
    
    # Agregar relación con Customer en Order
    if not hasattr(Order, 'customer_id'):
        Order.customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
        Order.customer = db.relationship('Customer', backref='orders', foreign_keys=[Order.customer_id])


# Service Worker para soporte offline
@app.route('/service-worker.js')
def service_worker():
    """Sirve el Service Worker para soporte offline"""
    from app.utils.performance import OfflineSupport
    from flask import Response
    
    js = OfflineSupport.generate_service_worker()
    return Response(js, mimetype='application/javascript')


# Página offline
@app.route('/offline.html')
def offline_page():
    """Página mostrada cuando no hay conexión"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sin Conexión - PedidosSaaS</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                font-family: Arial, sans-serif;
                text-align: center;
                padding: 50px;
                background-color: #f5f5f5;
            }
            .container {
                max-width: 500px;
                margin: 0 auto;
                background: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            .icon {
                font-size: 80px;
                color: #ccc;
                margin-bottom: 20px;
            }
            h1 {
                color: #333;
                margin-bottom: 10px;
            }
            p {
                color: #666;
                line-height: 1.6;
            }
            .retry-btn {
                display: inline-block;
                margin-top: 20px;
                padding: 12px 30px;
                background-color: #7c3aed;
                color: white;
                text-decoration: none;
                border-radius: 5px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">📡</div>
            <h1>Sin Conexión a Internet</h1>
            <p>Parece que no tienes conexión a internet en este momento.</p>
            <p>PedidosSaaS necesita conexión para funcionar correctamente. Por favor verifica tu conexión e intenta nuevamente.</p>
            <a href="/" class="retry-btn" onclick="window.location.reload()">Reintentar</a>
        </div>
    </body>
    </html>
    '''
