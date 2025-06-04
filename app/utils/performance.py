"""
Sistema de optimizaciones de rendimiento para conexiones lentas
Diseñado específicamente para el contexto cubano
"""

import gzip
import json
from functools import wraps
from flask import request, make_response, current_app, g
from datetime import datetime, timedelta
import hashlib
import os
from PIL import Image
from werkzeug.utils import secure_filename


class PerformanceOptimizer:
    """Clase principal para optimizaciones de rendimiento"""
    
    @staticmethod
    def init_app(app):
        """Inicializa optimizaciones en la aplicación Flask"""
        
        # Compresión GZIP
        @app.after_request
        def compress_response(response):
            """Comprime respuestas grandes con GZIP"""
            if (response.status_code < 200 or 
                response.status_code >= 300 or
                'gzip' not in request.headers.get('Accept-Encoding', '').lower() or
                response.content_length < 500):  # No comprimir respuestas pequeñas
                return response
            
            response.direct_passthrough = False
            
            if response.content_type.startswith('text/') or \
               response.content_type == 'application/json':
                # Comprimir contenido
                gzip_buffer = gzip.compress(response.get_data())
                response.set_data(gzip_buffer)
                response.headers['Content-Encoding'] = 'gzip'
                response.headers['Content-Length'] = len(gzip_buffer)
                response.headers['Vary'] = 'Accept-Encoding'
            
            return response
        
        # Headers de cache
        @app.after_request
        def set_cache_headers(response):
            """Configura headers de cache apropiados"""
            # Cache para archivos estáticos
            if request.path.startswith('/static/'):
                # Cache largo para CSS, JS, imágenes
                if any(request.path.endswith(ext) for ext in ['.css', '.js', '.jpg', '.png', '.gif', '.webp']):
                    response.headers['Cache-Control'] = 'public, max-age=31536000'  # 1 año
                else:
                    response.headers['Cache-Control'] = 'public, max-age=3600'  # 1 hora
            
            # Cache para API responses
            elif request.path.startswith('/api/') or request.path.startswith('/dashboard/analytics/data'):
                response.headers['Cache-Control'] = 'private, max-age=300'  # 5 minutos
            
            # No cache para páginas dinámicas
            else:
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
            
            return response
        
        # Minificar HTML en producción
        if app.config.get('ENV') == 'production':
            @app.after_request
            def minify_html(response):
                """Minifica HTML removiendo espacios innecesarios"""
                if response.content_type == 'text/html; charset=utf-8':
                    # Minificación simple (en producción usar una librería especializada)
                    minified = response.get_data(as_text=True)
                    minified = ' '.join(minified.split())  # Remueve espacios extras
                    response.set_data(minified)
                return response


class ImageOptimizer:
    """Optimizador de imágenes para reducir tamaño"""
    
    @staticmethod
    def optimize_image(image_path, max_width=1200, quality=85):
        """
        Optimiza una imagen reduciendo su tamaño y calidad
        
        Args:
            image_path: Ruta de la imagen
            max_width: Ancho máximo (mantiene proporción)
            quality: Calidad de compresión (1-100)
        """
        try:
            with Image.open(image_path) as img:
                # Convertir a RGB si es necesario
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'RGBA':
                        rgb_img.paste(img, mask=img.split()[-1])
                    else:
                        rgb_img.paste(img)
                    img = rgb_img
                
                # Redimensionar si es muy grande
                if img.width > max_width:
                    ratio = max_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                
                # Guardar optimizada
                img.save(image_path, 'JPEG', quality=quality, optimize=True)
                
                # Crear versiones adicionales para diferentes tamaños
                ImageOptimizer.create_responsive_versions(image_path, img)
                
        except Exception as e:
            current_app.logger.error(f"Error optimizando imagen: {e}")
    
    @staticmethod
    def create_responsive_versions(original_path, img):
        """Crea versiones de diferentes tamaños para carga adaptativa"""
        base_dir = os.path.dirname(original_path)
        filename = os.path.basename(original_path)
        name, ext = os.path.splitext(filename)
        
        sizes = {
            'thumb': (150, 150),
            'small': (300, 300),
            'medium': (600, 600)
        }
        
        for size_name, dimensions in sizes.items():
            # Crear directorio si no existe
            size_dir = os.path.join(base_dir, size_name)
            os.makedirs(size_dir, exist_ok=True)
            
            # Crear imagen redimensionada
            resized = img.copy()
            resized.thumbnail(dimensions, Image.Resampling.LANCZOS)
            
            # Guardar
            output_path = os.path.join(size_dir, filename)
            resized.save(output_path, 'JPEG', quality=80, optimize=True)


class LazyLoadingHelper:
    """Helper para implementar lazy loading de contenido"""
    
    @staticmethod
    def paginate_query(query, page=1, per_page=20, max_per_page=100):
        """
        Paginación optimizada con límites para proteger el servidor
        
        Args:
            query: SQLAlchemy query
            page: Número de página
            per_page: Items por página
            max_per_page: Máximo permitido por página
        """
        # Validar y limitar per_page
        per_page = min(per_page, max_per_page)
        
        # Obtener total de forma eficiente
        total = query.count()
        
        # Calcular offset
        offset = (page - 1) * per_page
        
        # Obtener items
        items = query.limit(per_page).offset(offset).all()
        
        return {
            'items': items,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page,  # Ceiling division
            'has_prev': page > 1,
            'has_next': page < ((total + per_page - 1) // per_page)
        }


class RequestCache:
    """Cache simple en memoria para requests (usar Redis en producción)"""
    
    _cache = {}
    _timestamps = {}
    
    @classmethod
    def get(cls, key):
        """Obtiene valor del cache si no ha expirado"""
        if key in cls._cache:
            timestamp = cls._timestamps.get(key)
            if timestamp and datetime.utcnow() - timestamp < timedelta(minutes=5):
                return cls._cache[key]
            else:
                # Expirado, eliminar
                del cls._cache[key]
                del cls._timestamps[key]
        return None
    
    @classmethod
    def set(cls, key, value):
        """Guarda valor en cache"""
        cls._cache[key] = value
        cls._timestamps[key] = datetime.utcnow()
        
        # Limpieza simple si el cache crece mucho
        if len(cls._cache) > 1000:
            cls._cleanup()
    
    @classmethod
    def _cleanup(cls):
        """Limpia entradas expiradas"""
        now = datetime.utcnow()
        expired_keys = [
            key for key, timestamp in cls._timestamps.items()
            if now - timestamp > timedelta(minutes=5)
        ]
        for key in expired_keys:
            del cls._cache[key]
            del cls._timestamps[key]


def cached_route(timeout=300):
    """Decorador para cachear respuestas de rutas"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Crear cache key basada en la ruta y parámetros
            cache_key = hashlib.md5(
                f"{request.path}:{request.args}:{current_user.id if hasattr(g, 'current_user') else 'anon'}".encode()
            ).hexdigest()
            
            # Intentar obtener del cache
            cached = RequestCache.get(cache_key)
            if cached is not None:
                response = make_response(cached)
                response.headers['X-Cache'] = 'HIT'
                return response
            
            # Ejecutar función
            result = f(*args, **kwargs)
            
            # Cachear si es exitoso
            if isinstance(result, tuple):
                if result[1] == 200:  # Solo cachear respuestas exitosas
                    RequestCache.set(cache_key, result[0])
            else:
                RequestCache.set(cache_key, result)
            
            response = make_response(result)
            response.headers['X-Cache'] = 'MISS'
            return response
        
        return decorated_function
    return decorator


class OfflineSupport:
    """Soporte para funcionamiento offline con Service Workers"""
    
    @staticmethod
    def generate_service_worker():
        """Genera el Service Worker para cache offline"""
        return '''
// Service Worker para soporte offline
const CACHE_NAME = 'pedidossaas-v1';
const urlsToCache = [
  '/',
  '/static/css/style.css',
  '/static/js/main.js',
  '/offline.html'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Cache hit - return response
        if (response) {
          return response;
        }

        return fetch(event.request).then(
          response => {
            // Check if valid response
            if(!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }

            // Clone the response
            const responseToCache = response.clone();

            caches.open(CACHE_NAME)
              .then(cache => {
                cache.put(event.request, responseToCache);
              });

            return response;
          }
        );
      })
      .catch(() => {
        // Offline fallback
        return caches.match('/offline.html');
      })
  );
});

// Limpiar caches viejos
self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME];
  
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});
'''


class DatabaseOptimizer:
    """Optimizaciones a nivel de base de datos"""
    
    @staticmethod
    def create_indexes(db):
        """Crea índices para mejorar performance de queries comunes"""
        indexes = [
            # Índices para Orders
            'CREATE INDEX IF NOT EXISTS idx_orders_user_created ON orders(user_id, created_at DESC)',
            'CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)',
            'CREATE INDEX IF NOT EXISTS idx_orders_number ON orders(order_number)',
            
            # Índices para Products
            'CREATE INDEX IF NOT EXISTS idx_products_user_active ON products(user_id, is_active)',
            'CREATE INDEX IF NOT EXISTS idx_products_featured ON products(is_featured, created_at DESC)',
            
            # Índices para OrderItems
            'CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id)',
            'CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id)',
            
            # Índice para búsquedas de texto (PostgreSQL)
            "CREATE INDEX IF NOT EXISTS idx_products_search ON products USING gin(to_tsvector('spanish', name || ' ' || COALESCE(description, '')))"
        ]
        
        for index in indexes:
            try:
                db.session.execute(index)
            except Exception as e:
                current_app.logger.warning(f"No se pudo crear índice: {e}")
        
        db.session.commit()
    
    @staticmethod
    def optimize_query(query):
        """Aplica optimizaciones comunes a queries"""
        # Usar joinedload para relaciones que siempre se necesitan
        # Esto evita el problema N+1
        return query.options(
            db.joinedload('*')  # Carga todas las relaciones
        )


# Función para comprimir assets estáticos
def compress_static_files(app):
    """Comprime archivos CSS y JS para producción"""
    if app.config.get('ENV') != 'production':
        return
    
    static_dir = os.path.join(app.root_path, 'static')
    
    # Comprimir CSS
    css_files = [f for f in os.listdir(os.path.join(static_dir, 'css')) if f.endswith('.css')]
    for css_file in css_files:
        if '.min.' not in css_file:  # No comprimir archivos ya minificados
            # Aquí implementarías la minificación real
            pass
    
    # Comprimir JS
    js_files = [f for f in os.listdir(os.path.join(static_dir, 'js')) if f.endswith('.js')]
    for js_file in js_files:
        if '.min.' not in js_file:
            # Aquí implementarías la minificación real
            pass
