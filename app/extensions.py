"""
Extensiones de Flask centralizadas
Evita imports circulares y facilita el testing
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_mail import Mail
from flask_cors import CORS
from flask_compress import Compress
import redis
import logging

# Inicializar extensiones sin app
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
bcrypt = Bcrypt()
csrf = CSRFProtect()
mail = Mail()
cors = CORS()
compress = Compress()
cache = Cache()

# Rate limiter con configuración flexible
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100 per hour"],
    storage_uri="memory://"  # Se actualizará con Redis si está disponible
)

# Logger
logger = logging.getLogger('pedidossaas')

# Cliente Redis (opcional)
redis_client = None

def init_extensions(app):
    """
    Inicializa todas las extensiones con la aplicación Flask
    """
    # Base de datos
    db.init_app(app)
    
    # Migraciones
    migrate.init_app(app, db)
    
    # Autenticación
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
    login_manager.login_message_category = 'info'
    
    # Seguridad
    bcrypt.init_app(app)
    csrf.init_app(app)
    
    # Email
    mail.init_app(app)
    
    # CORS (para API)
    cors.init_app(app, resources={
        r"/api/*": {
            "origins": app.config.get('CORS_ORIGINS', '*'),
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    # Compresión
    compress.init_app(app)
    
    # Cache
    cache_config = {
        'CACHE_TYPE': 'simple',
        'CACHE_DEFAULT_TIMEOUT': app.config.get('CACHE_DEFAULT_TIMEOUT', 300)
    }
    
    # Intentar usar Redis para cache si está disponible
    redis_url = app.config.get('REDIS_URL')
    if redis_url:
        try:
            global redis_client
            redis_client = redis.from_url(redis_url, decode_responses=True)
            redis_client.ping()
            
            cache_config = {
                'CACHE_TYPE': 'redis',
                'CACHE_REDIS_URL': redis_url,
                'CACHE_DEFAULT_TIMEOUT': app.config.get('CACHE_DEFAULT_TIMEOUT', 300),
                'CACHE_KEY_PREFIX': app.config.get('CACHE_KEY_PREFIX', 'pedidossaas:')
            }
            
            # Actualizar limiter para usar Redis
            limiter.storage_uri = redis_url
            
            logger.info("Redis conectado para cache y rate limiting")
        except Exception as e:
            logger.warning(f"No se pudo conectar a Redis: {e}. Usando cache en memoria.")
    
    cache.init_app(app, config=cache_config)
    
    # Rate limiting
    limiter.init_app(app)
    
    # Configurar callbacks
    setup_login_manager(app)
    
    # Comandos CLI personalizados
    register_cli_commands(app)

def setup_login_manager(app):
    """
    Configura los callbacks del login manager
    """
    from app.models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        """Carga un usuario por su ID"""
        return User.query.get(int(user_id))
    
    @login_manager.unauthorized_handler
    def unauthorized():
        """Maneja solicitudes no autorizadas"""
        from flask import request, jsonify, redirect, url_for, flash
        
        # Para solicitudes API, devolver JSON
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Authentication required'}), 401
        
        # Para solicitudes web, redirigir al login
        flash('Por favor inicia sesión para acceder a esta página.', 'warning')
        return redirect(url_for('auth.login', next=request.url))

def register_cli_commands(app):
    """
    Registra comandos CLI personalizados
    """
    @app.cli.command()
    def init_db():
        """Inicializa la base de datos"""
        import subprocess
        subprocess.run(['python', 'init_db.py'])
    
    @app.cli.command()
    def create_demo():
        """Crea datos de demostración"""
        import subprocess
        subprocess.run(['python', 'scripts/create_advanced_demo.py'])
    
    @app.cli.command()
    def backup_db():
        """Crea backup de la base de datos"""
        import subprocess
        subprocess.run(['python', 'scripts/backup_db.py', 'create'])
    
    @app.cli.command()
    def clean_uploads():
        """Limpia archivos huérfanos"""
        import subprocess
        subprocess.run(['python', 'scripts/clean_uploads.py'])
    
    @app.cli.command()
    def run_scheduler():
        """Ejecuta el scheduler de tareas"""
        from app.automation.scheduler import start_scheduler
        start_scheduler()
    
    @app.cli.command()
    def clear_cache():
        """Limpia todo el cache"""
        cache.clear()
        print("Cache limpiado exitosamente")
    
    @app.cli.command()
    def test_email():
        """Prueba el envío de emails"""
        from flask_mail import Message
        
        try:
            msg = Message(
                subject='Test Email - PedidosSaaS',
                sender=app.config['MAIL_DEFAULT_SENDER'],
                recipients=[app.config.get('ADMIN_EMAIL', 'admin@example.com')]
            )
            msg.body = 'Este es un email de prueba desde PedidosSaaS'
            msg.html = '<p>Este es un <strong>email de prueba</strong> desde PedidosSaaS</p>'
            
            mail.send(msg)
            print("Email de prueba enviado exitosamente")
        except Exception as e:
            print(f"Error enviando email: {e}")

# Decoradores útiles
def async_task(f):
    """
    Decorador para ejecutar tareas en background
    Usa Celery si está disponible, sino ejecuta sincrónicamente
    """
    def wrapper(*args, **kwargs):
        try:
            # Intentar usar Celery
            from app.celery import celery
            return f.apply_async(args=args, kwargs=kwargs)
        except:
            # Ejecutar sincrónicamente
            return f(*args, **kwargs)
    return wrapper

def cached(timeout=300, key_prefix='view'):
    """
    Decorador para cachear vistas
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Generar clave de cache
            from flask import request
            cache_key = f"{key_prefix}:{request.path}:{request.query_string.decode()}"
            
            # Intentar obtener del cache
            rv = cache.get(cache_key)
            if rv is not None:
                return rv
            
            # Ejecutar función y cachear resultado
            rv = f(*args, **kwargs)
            cache.set(cache_key, rv, timeout=timeout)
            return rv
        
        return wrapper
    return decorator

# Funciones de utilidad para extensiones
def get_redis_client():
    """
    Obtiene el cliente Redis si está disponible
    """
    return redis_client

def is_redis_available():
    """
    Verifica si Redis está disponible
    """
    if redis_client:
        try:
            redis_client.ping()
            return True
        except:
            return False
    return False

def get_db_session():
    """
    Obtiene una sesión de base de datos para uso fuera del contexto de Flask
    """
    return db.session

# Excepciones personalizadas
class PedidosSaaSException(Exception):
    """Excepción base para la aplicación"""
    pass

class ValidationError(PedidosSaaSException):
    """Error de validación"""
    pass

class BusinessLogicError(PedidosSaaSException):
    """Error de lógica de negocio"""
    pass

class PaymentError(PedidosSaaSException):
    """Error en procesamiento de pagos"""
    pass

class InventoryError(PedidosSaaSException):
    """Error en gestión de inventario"""
    pass
