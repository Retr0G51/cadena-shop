"""
Configuración avanzada para PedidosSaaS
Incluye todas las configuraciones para las funcionalidades extendidas
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

# Cargar variables de entorno
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    """Configuración base"""
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Base URL
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', '').replace('postgres://', 'postgresql://') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 20,
        'connect_args': {
            'connect_timeout': 10,
            'options': '-c statement_timeout=30000'  # 30 segundos
        }
    }
    
    # Seguridad
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Uploads
    UPLOAD_FOLDER = os.path.join(basedir, 'app/static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB máximo
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'xlsx', 'xls', 'csv'}
    
    # Imagen processing
    THUMBNAIL_SIZE = (150, 150)
    SMALL_SIZE = (300, 300)
    MEDIUM_SIZE = (600, 600)
    IMAGE_QUALITY = 85
    
    # Redis y Cache
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    CACHE_TYPE = 'redis' if os.environ.get('REDIS_URL') else 'simple'
    CACHE_DEFAULT_TIMEOUT = 300
    CACHE_KEY_PREFIX = 'pedidossaas:'
    
    # Celery (para tareas en background)
    CELERY_BROKER_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_TIMEZONE = 'UTC'
    CELERY_ENABLE_UTC = True
    
    # Email
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@pedidossaas.com')
    MAIL_MAX_EMAILS = 50
    
    # Rate Limiting
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL') or 'memory://'
    RATELIMIT_DEFAULT = "100 per hour"
    RATELIMIT_HEADERS_ENABLED = True
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'logs/app.log')
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 10
    
    # Sentry (Error tracking)
    SENTRY_DSN = os.environ.get('SENTRY_DSN')
    
    # Pagination
    ITEMS_PER_PAGE = 20
    MAX_ITEMS_PER_PAGE = 100
    
    # Business Rules
    MAX_PRODUCTS_FREE = 50
    MAX_ORDERS_FREE = 100
    TRIAL_DAYS = 30
    
    # Analytics
    ANALYTICS_RETENTION_DAYS = 365
    ANALYTICS_AGGREGATION_INTERVAL = 3600  # 1 hora
    
    # Invoicing
    INVOICE_PREFIX = 'FAC'
    INVOICE_DUE_DAYS = 30
    TAX_RATE = 18.0  # Porcentaje
    
    # Inventory
    LOW_STOCK_THRESHOLD = 10
    REORDER_POINT_MULTIPLIER = 1.5
    
    # SMS (Twilio)
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
    
    # Payments (Stripe)
    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    
    # AWS S3 (para backups y archivos)
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_S3_BUCKET = os.environ.get('AWS_S3_BUCKET')
    AWS_S3_REGION = os.environ.get('AWS_S3_REGION', 'us-east-1')
    
    # Feature Flags
    FEATURES = {
        'ADVANCED_ANALYTICS': True,
        'INVOICING': True,
        'INVENTORY_MANAGEMENT': True,
        'CRM': True,
        'EMAIL_CAMPAIGNS': True,
        'SMS_NOTIFICATIONS': False,
        'PAYMENT_PROCESSING': False,
        'API_ACCESS': True,
        'MULTI_WAREHOUSE': True,
        'BARCODE_SCANNING': True,
        'LOYALTY_PROGRAM': True,
        'RECURRING_INVOICES': True,
        'AUTOMATED_REPORTS': True
    }
    
    # API Configuration
    API_RATE_LIMIT = "1000 per hour"
    API_VERSION = "v1"
    
    # Scheduled Tasks
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = "UTC"
    
    # Performance
    SLOW_QUERY_THRESHOLD = 0.5  # segundos
    REQUEST_TIMEOUT = 30  # segundos
    
    # Localization
    LANGUAGES = ['es', 'en']
    DEFAULT_LANGUAGE = 'es'
    CURRENCY = 'MXN'
    CURRENCY_SYMBOL = '$'
    
    # Export Settings
    EXPORT_MAX_ROWS = 10000
    EXPORT_FORMATS = ['csv', 'xlsx', 'pdf']
    
    # Security Headers
    SECURITY_HEADERS = {
        'X-Frame-Options': 'SAMEORIGIN',
        'X-Content-Type-Options': 'nosniff',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin'
    }


class DevelopmentConfig(Config):
    """Configuración de desarrollo"""
    DEBUG = True
    TESTING = False
    WTF_CSRF_ENABLED = False
    
    # Flask Debug Toolbar
    DEBUG_TB_ENABLED = True
    DEBUG_TB_INTERCEPT_REDIRECTS = False
    DEBUG_TB_PROFILER_ENABLED = True
    
    # Logging más detallado
    LOG_LEVEL = 'DEBUG'
    SQLALCHEMY_ECHO = False  # Cambiar a True para ver queries SQL
    
    # Cache más corto en desarrollo
    CACHE_DEFAULT_TIMEOUT = 60
    
    # Email en desarrollo (usar servidor local o servicio de prueba)
    MAIL_DEBUG = True
    MAIL_SUPPRESS_SEND = True  # No enviar emails realmente


class ProductionConfig(Config):
    """Configuración de producción"""
    DEBUG = False
    TESTING = False
    
    # Seguridad reforzada
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_ENABLED = True
    
    # URLs de producción
    PREFERRED_URL_SCHEME = 'https'
    
    # Cache más largo en producción
    CACHE_DEFAULT_TIMEOUT = 600
    
    # Comprimir respuestas
    COMPRESS_MIMETYPES = [
        'text/html', 'text/css', 'text/xml', 'application/json',
        'application/javascript'
    ]
    COMPRESS_LEVEL = 6
    COMPRESS_MIN_SIZE = 500
    
    # Límites más estrictos
    RATELIMIT_DEFAULT = "60 per hour"
    
    # Configuración de workers
    WORKERS = int(os.environ.get('WEB_CONCURRENCY', 4))
    THREADS_PER_WORKER = 2
    WORKER_CONNECTIONS = 1000
    
    # Timeouts
    WORKER_TIMEOUT = 30
    GRACEFUL_TIMEOUT = 30
    KEEPALIVE = 5


class TestingConfig(Config):
    """Configuración para tests"""
    TESTING = True
    DEBUG = True
    
    # Base de datos en memoria
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Desactivar CSRF para tests
    WTF_CSRF_ENABLED = False
    
    # Cache simple para tests
    CACHE_TYPE = 'simple'
    
    # No enviar emails en tests
    MAIL_SUPPRESS_SEND = True
    
    # Login más simple para tests
    LOGIN_DISABLED = False


# Mapeo de configuraciones
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

# Configuración activa
def get_config():
    """Obtiene la configuración según el entorno"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])
