"""
Sistema de Cache para PedidosSaaS
Implementa cache en memoria y Redis para optimización
"""
from functools import wraps, lru_cache
from datetime import datetime, timedelta
import json
import hashlib
import pickle
from flask import current_app, g
from app.extensions import db
import redis
from typing import Any, Optional, Union, Callable
import logging

logger = logging.getLogger(__name__)

class CacheManager:
    """Gestor principal de cache"""
    
    def __init__(self):
        self.redis_client = None
        self.local_cache = {}
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }
    
    def init_app(self, app):
        """Inicializa el sistema de cache"""
        # Configurar Redis si está disponible
        redis_url = app.config.get('REDIS_URL')
        if redis_url:
            try:
                self.redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_keepalive=True,
                    socket_keepalive_options={
                        1: 1,  # TCP_KEEPIDLE
                        2: 1,  # TCP_KEEPINTVL
                        3: 3,  # TCP_KEEPCNT
                    }
                )
                self.redis_client.ping()
                logger.info("Redis cache conectado")
            except Exception as e:
                logger.warning(f"No se pudo conectar a Redis: {e}. Usando cache local.")
                self.redis_client = None
        
        # Registrar comandos CLI
        app.cli.add_command(clear_cache_command)
    
    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """Genera una clave única para el cache"""
        # Crear una representación única de los argumentos
        key_parts = [prefix]
        
        # Agregar argumentos posicionales
        for arg in args:
            if isinstance(arg, (str, int, float, bool)):
                key_parts.append(str(arg))
            else:
                # Para objetos complejos, usar su representación
                key_parts.append(hashlib.md5(str(arg).encode()).hexdigest()[:8])
        
        # Agregar argumentos nombrados
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            for k, v in sorted_kwargs:
                key_parts.append(f"{k}={v}")
        
        return ":".join(key_parts)
    
    def get(self, key: str) -> Optional[Any]:
        """Obtiene un valor del cache"""
        # Intentar cache local primero
        if key in self.local_cache:
            value, expiry = self.local_cache[key]
            if expiry is None or expiry > datetime.utcnow():
                self.cache_stats['hits'] += 1
                return value
            else:
                # Expirado
                del self.local_cache[key]
        
        # Intentar Redis
        if self.redis_client:
            try:
                value = self.redis_client.get(key)
                if value:
                    self.cache_stats['hits'] += 1
                    # Deserializar si es necesario
                    try:
                        return json.loads(value)
                    except:
                        return value
            except Exception as e:
                logger.error(f"Error obteniendo de Redis: {e}")
        
        self.cache_stats['misses'] += 1
        return None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Establece un valor en el cache con TTL en segundos"""
        self.cache_stats['sets'] += 1
        
        # Cache local
        expiry = datetime.utcnow() + timedelta(seconds=ttl) if ttl else None
        self.local_cache[key] = (value, expiry)
        
        # Redis
        if self.redis_client:
            try:
                # Serializar si es necesario
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                
                if ttl:
                    self.redis_client.setex(key, ttl, value)
                else:
                    self.redis_client.set(key, value)
                return True
            except Exception as e:
                logger.error(f"Error guardando en Redis: {e}")
        
        return True
    
    def delete(self, key: str) -> bool:
        """Elimina un valor del cache"""
        self.cache_stats['deletes'] += 1
        
        # Cache local
        if key in self.local_cache:
            del self.local_cache[key]
        
        # Redis
        if self.redis_client:
            try:
                self.redis_client.delete(key)
            except Exception as e:
                logger.error(f"Error eliminando de Redis: {e}")
        
        return True
    
    def delete_pattern(self, pattern: str) -> int:
        """Elimina todas las claves que coincidan con el patrón"""
        count = 0
        
        # Cache local
        keys_to_delete = [k for k in self.local_cache.keys() if pattern in k]
        for key in keys_to_delete:
            del self.local_cache[key]
            count += 1
        
        # Redis
        if self.redis_client:
            try:
                # Usar SCAN para evitar bloquear Redis
                cursor = 0
                while True:
                    cursor, keys = self.redis_client.scan(
                        cursor, match=f"*{pattern}*", count=100
                    )
                    if keys:
                        self.redis_client.delete(*keys)
                        count += len(keys)
                    if cursor == 0:
                        break
            except Exception as e:
                logger.error(f"Error eliminando patrón de Redis: {e}")
        
        return count
    
    def clear(self) -> bool:
        """Limpia todo el cache"""
        # Cache local
        self.local_cache.clear()
        
        # Redis
        if self.redis_client:
            try:
                self.redis_client.flushdb()
            except Exception as e:
                logger.error(f"Error limpiando Redis: {e}")
                return False
        
        return True
    
    def get_stats(self) -> dict:
        """Obtiene estadísticas del cache"""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        stats = {
            **self.cache_stats,
            'hit_rate': f"{hit_rate:.2f}%",
            'local_cache_size': len(self.local_cache),
            'redis_connected': self.redis_client is not None
        }
        
        if self.redis_client:
            try:
                info = self.redis_client.info()
                stats['redis_memory'] = info.get('used_memory_human', 'N/A')
                stats['redis_keys'] = self.redis_client.dbsize()
            except:
                pass
        
        return stats


# Instancia global del cache
cache = CacheManager()


def cached(ttl: int = 300, key_prefix: str = None, 
          vary_on_user: bool = True, invalidate_on: list = None):
    """
    Decorador para cachear resultados de funciones
    
    Args:
        ttl: Time to live en segundos
        key_prefix: Prefijo personalizado para la clave
        vary_on_user: Si la clave debe incluir el user_id
        invalidate_on: Lista de eventos que invalidan el cache
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generar clave
            if key_prefix:
                cache_key_parts = [key_prefix]
            else:
                cache_key_parts = [func.__module__, func.__name__]
            
            # Agregar user_id si es necesario
            if vary_on_user and hasattr(g, 'current_user') and g.current_user:
                cache_key_parts.append(f"user_{g.current_user.id}")
            
            # Crear clave con argumentos
            cache_key = cache._make_key(*cache_key_parts, *args, **kwargs)
            
            # Intentar obtener del cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Ejecutar función
            result = func(*args, **kwargs)
            
            # Guardar en cache
            cache.set(cache_key, result, ttl)
            
            return result
        
        # Agregar método para invalidar cache
        def invalidate(*args, **kwargs):
            if key_prefix:
                cache_key_parts = [key_prefix]
            else:
                cache_key_parts = [func.__module__, func.__name__]
            
            if vary_on_user and hasattr(g, 'current_user') and g.current_user:
                cache_key_parts.append(f"user_{g.current_user.id}")
            
            cache_key = cache._make_key(*cache_key_parts, *args, **kwargs)
            cache.delete(cache_key)
        
        wrapper.invalidate = invalidate
        return wrapper
    return decorator


class CachedQuery:
    """Clase para cachear queries de SQLAlchemy"""
    
    def __init__(self, query, cache_key: str, ttl: int = 300):
        self.query = query
        self.cache_key = cache_key
        self.ttl = ttl
    
    def all(self):
        """Obtiene todos los resultados (cacheados)"""
        results = cache.get(self.cache_key)
        if results is None:
            results = self.query.all()
            cache.set(self.cache_key, results, self.ttl)
        return results
    
    def first(self):
        """Obtiene el primer resultado (cacheado)"""
        cache_key = f"{self.cache_key}:first"
        result = cache.get(cache_key)
        if result is None:
            result = self.query.first()
            cache.set(cache_key, result, self.ttl)
        return result
    
    def count(self):
        """Cuenta los resultados (cacheado)"""
        cache_key = f"{self.cache_key}:count"
        count = cache.get(cache_key)
        if count is None:
            count = self.query.count()
            cache.set(cache_key, count, self.ttl)
        return count


def cached_property(ttl: int = 300):
    """Decorador para propiedades cacheadas"""
    def decorator(func: Callable) -> property:
        @wraps(func)
        def wrapper(self):
            cache_key = cache._make_key(
                self.__class__.__name__,
                func.__name__,
                self.id if hasattr(self, 'id') else id(self)
            )
            
            result = cache.get(cache_key)
            if result is None:
                result = func(self)
                cache.set(cache_key, result, ttl)
            
            return result
        
        return property(wrapper)
    return decorator


# Cache específicos para diferentes áreas
class ProductCache:
    """Cache específico para productos"""
    
    @staticmethod
    @cached(ttl=600, key_prefix='product')
    def get_product_by_id(product_id: int):
        """Obtiene un producto por ID (cacheado)"""
        from app.models import Product
        return Product.query.get(product_id)
    
    @staticmethod
    @cached(ttl=300, key_prefix='product_stock')
    def get_product_stock(product_id: int, warehouse_id: int = None):
        """Obtiene el stock de un producto (cacheado)"""
        from app.models.inventory import StockItem
        
        query = StockItem.query.filter_by(product_id=product_id)
        if warehouse_id:
            query = query.filter_by(warehouse_id=warehouse_id)
        
        return query.all()
    
    @staticmethod
    def invalidate_product(product_id: int):
        """Invalida el cache de un producto"""
        cache.delete_pattern(f"product:{product_id}")
        cache.delete_pattern(f"product_stock:{product_id}")


class OrderCache:
    """Cache específico para pedidos"""
    
    @staticmethod
    @cached(ttl=60, key_prefix='order_stats')
    def get_daily_stats(user_id: int, date: datetime):
        """Obtiene estadísticas diarias (cacheadas)"""
        from app.models import Order
        
        start = date.replace(hour=0, minute=0, second=0)
        end = start + timedelta(days=1)
        
        orders = Order.query.filter(
            Order.user_id == user_id,
            Order.created_at >= start,
            Order.created_at < end
        ).all()
        
        return {
            'total_orders': len(orders),
            'completed_orders': len([o for o in orders if o.status == 'delivered']),
            'total_revenue': sum(o.total for o in orders if o.status == 'delivered'),
            'pending_orders': len([o for o in orders if o.status == 'pending'])
        }


class CustomerCache:
    """Cache específico para clientes"""
    
    @staticmethod
    @cached(ttl=300, key_prefix='customer_by_phone')
    def get_by_phone(user_id: int, phone: str):
        """Obtiene cliente por teléfono (cacheado)"""
        from app.models.customer import Customer
        return Customer.query.filter_by(
            user_id=user_id,
            phone=phone
        ).first()
    
    @staticmethod
    def invalidate_customer(customer_id: int):
        """Invalida el cache de un cliente"""
        cache.delete_pattern(f"customer:{customer_id}")
        cache.delete_pattern(f"customer_by_phone:")


# Funciones de utilidad
def warmup_cache(user_id: int):
    """Precalienta el cache con datos comunes"""
    from app.models import Product, User
    from app.models.customer import Customer
    
    # Cachear productos activos
    products = Product.query.filter_by(
        user_id=user_id,
        is_active=True
    ).all()
    
    for product in products:
        ProductCache.get_product_by_id(product.id)
    
    # Cachear clientes top
    top_customers = Customer.query.filter_by(
        user_id=user_id
    ).order_by(Customer.total_spent.desc()).limit(50).all()
    
    for customer in top_customers:
        CustomerCache.get_by_phone(user_id, customer.phone)
    
    logger.info(f"Cache precalentado para usuario {user_id}")


# Comando CLI
import click
from flask.cli import with_appcontext

@click.command()
@with_appcontext
def clear_cache_command():
    """Limpia todo el cache"""
    if cache.clear():
        click.echo("Cache limpiado exitosamente")
    else:
        click.echo("Error limpiando el cache")


# Middleware para estadísticas de cache
def cache_stats_middleware(app):
    """Agrega estadísticas de cache a los headers de respuesta"""
    @app.after_request
    def add_cache_stats(response):
        if app.debug:
            stats = cache.get_stats()
            response.headers['X-Cache-Hit-Rate'] = stats['hit_rate']
            response.headers['X-Cache-Hits'] = str(stats['hits'])
            response.headers['X-Cache-Misses'] = str(stats['misses'])
        return response
