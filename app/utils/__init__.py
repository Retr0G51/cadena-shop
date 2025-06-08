"""
Utilidades para PedidosSaaS
Funciones y clases de apoyo reutilizables
"""

from app.utils.decorators import (
    business_required, 
    active_business_required,
    admin_required,
    async_task,
    rate_limit
)

from app.utils.helpers import (
    format_currency,
    format_phone,
    generate_slug,
    sanitize_filename,
    paginate_query,
    export_to_csv,
    export_to_excel,
    send_sms,
    calculate_distance,
    parse_date_range
)

from app.utils.cache import (
    cache,
    cached,
    cached_property,
    ProductCache,
    OrderCache,
    CustomerCache,
    warmup_cache
)

from app.utils.performance import (
    PerformanceOptimizer,
    optimize_query,
    QueryOptimizer,
    DatabaseOptimizer,
    batch_process,
    profile_function
)

__all__ = [
    # Decoradores
    'business_required',
    'active_business_required', 
    'admin_required',
    'async_task',
    'rate_limit',
    
    # Helpers
    'format_currency',
    'format_phone',
    'generate_slug',
    'sanitize_filename',
    'paginate_query',
    'export_to_csv',
    'export_to_excel',
    'send_sms',
    'calculate_distance',
    'parse_date_range',
    
    # Cache
    'cache',
    'cached',
    'cached_property',
    'ProductCache',
    'OrderCache',
    'CustomerCache',
    'warmup_cache',
    
    # Performance
    'PerformanceOptimizer',
    'optimize_query',
    'QueryOptimizer',
    'DatabaseOptimizer',
    'batch_process',
    'profile_function'
]

# Constantes útiles
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

# Expresiones regulares comunes
import re

PHONE_REGEX = re.compile(r'^\+?[1-9]\d{1,14}$')
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
TAX_ID_REGEX = re.compile(r'^[A-Z0-9]{8,15}$')

# Funciones de validación
def is_valid_phone(phone):
    """Valida un número de teléfono"""
    return bool(PHONE_REGEX.match(phone))

def is_valid_email(email):
    """Valida una dirección de email"""
    return bool(EMAIL_REGEX.match(email))

def is_valid_tax_id(tax_id):
    """Valida un NIF/CIF/RUT"""
    return bool(TAX_ID_REGEX.match(tax_id.upper()))

# Configuración de logging específica para utils
import logging

utils_logger = logging.getLogger('pedidossaas.utils')
utils_logger.setLevel(logging.INFO)
