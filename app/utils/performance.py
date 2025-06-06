"""
Optimizaciones de rendimiento para PedidosSaaS
Includes caching, query optimization, and performance monitoring
"""
from functools import wraps
from datetime import datetime, timedelta
import time
import json
from flask import g, request, current_app
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import joinedload, selectinload, contains_eager
from app.extensions import db
import logging

logger = logging.getLogger(__name__)

class PerformanceOptimizer:
    """Clase principal para optimizaciones de rendimiento"""
    
    @staticmethod
    def init_app(app):
        """Inicializa optimizaciones para la aplicación"""
        # Habilitar query logging en desarrollo
        if app.config.get('DEBUG'):
            PerformanceOptimizer._setup_query_logging()
        
        # Configurar pool de conexiones
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 10,
            'pool_recycle': 3600,
            'pool_pre_ping': True,
            'max_overflow': 20
        }
        
        # Configurar timeouts
        app.config['SQLALCHEMY_POOL_TIMEOUT'] = 30
        
        # Registrar middleware de performance
        app.before_request(PerformanceOptimizer._before_request)
        app.after_request(PerformanceOptimizer._after_request)
    
    @staticmethod
    def _setup_query_logging():
        """Configura logging de queries SQL"""
        @event.listens_for(Engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            conn.info.setdefault('query_start_time', []).append(time.time())
            
        @event.listens_for(Engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            total = time.time() - conn.info['query_start_time'].pop(-1)
            if total > 0.5:  # Log queries que toman más de 500ms
                logger.warning(f"Slow query ({total:.3f}s): {statement[:100]}...")
    
    @staticmethod
    def _before_request():
        """Ejecuta antes de cada request"""
        g.start_time = time.time()
        g.db_queries = 0
    
    @staticmethod
    def _after_request(response):
        """Ejecuta después de cada request"""
        if hasattr(g, 'start_time'):
            total_time = time.time() - g.start_time
            response.headers['X-Response-Time'] = str(int(total_time * 1000))
            
            # Log requests lentos
            if total_time > 1:
                logger.warning(
                    f"Slow request: {request.method} {request.path} "
                    f"took {total_time:.3f}s with {getattr(g, 'db_queries', 0)} queries"
                )
        
        return response


def optimize_query(func):
    """Decorador para optimizar queries automáticamente"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Habilitar eager loading para relaciones comunes
        with db.session.no_autoflush:
            result = func(*args, **kwargs)
            
            # Si es una query, aplicar optimizaciones
            if hasattr(result, 'options'):
                # Detectar relaciones y aplicar eager loading
                model = result.column_descriptions[0]['type']
                
                # Aplicar eager loading basado en el modelo
                if hasattr(model, '__tablename__'):
                    if model.__tablename__ == 'orders':
                        result = result.options(
                            selectinload('items').joinedload('product'),
                            selectinload('customer')
                        )
                    elif model.__tablename__ == 'products':
                        result = result.options(
                            selectinload('stock_items'),
                            selectinload('category_rel')
                        )
                    elif model.__tablename__ == 'customers':
                        result = result.options(
                            selectinload('orders'),
                            selectinload('groups')
                        )
            
            return result
    return wrapper


class QueryOptimizer:
    """Optimizador de queries específicas"""
    
    @staticmethod
    def get_orders_with_items(user_id, limit=50, offset=0, filters=None):
        """Obtiene pedidos con items de forma optimizada"""
        query = db.session.query(Order).filter_by(user_id=user_id)
        
        # Aplicar filtros
        if filters:
            if filters.get('status'):
                query = query.filter_by(status=filters['status'])
            if filters.get('date_from'):
                query = query.filter(Order.created_at >= filters['date_from'])
            if filters.get('date_to'):
                query = query.filter(Order.created_at <= filters['date_to'])
        
        # Eager loading optimizado
        query = query.options(
            selectinload(Order.items).joinedload(OrderItem.product)
        )
        
        # Ordenar y paginar
        query = query.order_by(Order.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        return query.all()
    
    @staticmethod
    def get_product_analytics(user_id, product_id, days=30):
        """Obtiene analytics de producto de forma optimizada"""
        # Usar una sola query con agregaciones
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        result = db.session.query(
            func.count(distinct(Order.id)).label('order_count'),
            func.sum(OrderItem.quantity).label('total_quantity'),
            func.sum(OrderItem.subtotal).label('total_revenue'),
            func.avg(OrderItem.quantity).label('avg_quantity_per_order')
        ).select_from(OrderItem).join(
            Order
        ).filter(
            OrderItem.product_id == product_id,
            Order.user_id == user_id,
            Order.created_at >= start_date,
            Order.status == 'delivered'
        ).first()
        
        return {
            'order_count': result.order_count or 0,
            'total_quantity': float(result.total_quantity or 0),
            'total_revenue': float(result.total_revenue or 0),
            'avg_quantity_per_order': float(result.avg_quantity_per_order or 0)
        }
    
    @staticmethod
    def bulk_update_stock(updates):
        """Actualización masiva de stock"""
        # Usar bulk_update_mappings para mejor performance
        if updates:
            db.session.bulk_update_mappings(StockItem, updates)
            db.session.commit()
    
    @staticmethod
    def get_customer_orders_summary(user_id, limit=100):
        """Obtiene resumen de pedidos por cliente de forma optimizada"""
        # Usar CTE (Common Table Expression) para mejor performance
        from sqlalchemy import select, func, and_
        
        orders_cte = select(
            Order.customer_phone,
            func.count(Order.id).label('order_count'),
            func.sum(Order.total).label('total_spent'),
            func.max(Order.created_at).label('last_order_date')
        ).where(
            and_(
                Order.user_id == user_id,
                Order.status == 'delivered'
            )
        ).group_by(Order.customer_phone).cte('customer_orders')
        
        # Query principal con el CTE
        query = db.session.query(
            Customer,
            orders_cte.c.order_count,
            orders_cte.c.total_spent,
            orders_cte.c.last_order_date
        ).outerjoin(
            orders_cte,
            Customer.phone == orders_cte.c.customer_phone
        ).filter(
            Customer.user_id == user_id
        ).limit(limit)
        
        return query.all()


class DatabaseOptimizer:
    """Optimizador de base de datos"""
    
    @staticmethod
    def create_indexes():
        """Crea índices optimizados"""
        indexes = [
            # Índices compuestos para queries frecuentes
            "CREATE INDEX IF NOT EXISTS idx_orders_user_status_created ON orders(user_id, status, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_order_items_order_product ON order_items(order_id, product_id)",
            "CREATE INDEX IF NOT EXISTS idx_products_user_active ON products(user_id, is_active)",
            "CREATE INDEX IF NOT EXISTS idx_invoices_user_status ON invoices(user_id, status)",
            "CREATE INDEX IF NOT EXISTS idx_stock_items_product_warehouse ON stock_items(product_id, warehouse_id)",
            
            # Índices para búsquedas
            "CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone)",
            "CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email)",
            "CREATE INDEX IF NOT EXISTS idx_products_name ON products USING gin(to_tsvector('spanish', name))",
            
            # Índices para fechas
            "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_invoices_due_date ON invoices(due_date) WHERE status != 'paid'",
        ]
        
        with db.engine.connect() as conn:
            for index in indexes:
                try:
                    conn.execute(index)
                    logger.info(f"Índice creado: {index.split(' ')[5]}")
                except Exception as e:
                    logger.error(f"Error creando índice: {e}")
            conn.commit()
    
    @staticmethod
    def analyze_tables():
        """Ejecuta ANALYZE en tablas principales"""
        tables = ['orders', 'order_items', 'products', 'customers', 'invoices', 'stock_items']
        
        with db.engine.connect() as conn:
            for table in tables:
                try:
                    conn.execute(f"ANALYZE {table}")
                    logger.info(f"ANALYZE ejecutado en tabla {table}")
                except Exception as e:
                    logger.error(f"Error en ANALYZE {table}: {e}")
            conn.commit()
    
    @staticmethod
    def vacuum_tables():
        """Ejecuta VACUUM en tablas (solo en mantenimiento)"""
        # VACUUM no puede ejecutarse dentro de una transacción
        # Debe ejecutarse durante mantenimiento programado
        pass


class ConnectionPool:
    """Gestión optimizada del pool de conexiones"""
    
    @staticmethod
    def get_pool_status():
        """Obtiene estado del pool de conexiones"""
        pool = db.engine.pool
        return {
            'size': pool.size(),
            'checked_in': pool.checkedin(),
            'overflow': pool.overflow(),
            'total': pool.size() + pool.overflow() - pool.checkedin()
        }
    
    @staticmethod
    def reset_pool():
        """Reinicia el pool de conexiones"""
        db.engine.dispose()
        logger.info("Pool de conexiones reiniciado")


def batch_process(items, batch_size=100, processor_func=None):
    """Procesa items en lotes para mejor performance"""
    results = []
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        
        if processor_func:
            batch_results = processor_func(batch)
            results.extend(batch_results)
        
        # Limpiar sesión cada X lotes para liberar memoria
        if i % (batch_size * 10) == 0:
            db.session.flush()
            db.session.expire_all()
    
    return results


def profile_function(func):
    """Decorador para perfilar funciones"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        import cProfile
        import pstats
        from io import StringIO
        
        profiler = cProfile.Profile()
        profiler.enable()
        
        try:
            result = func(*args, **kwargs)
        finally:
            profiler.disable()
            
            # Solo en debug
            if current_app.debug:
                stream = StringIO()
                stats = pstats.Stats(profiler, stream=stream)
                stats.sort_stats('cumulative')
                stats.print_stats(10)  # Top 10 funciones
                
                logger.debug(f"Profile for {func.__name__}:\n{stream.getvalue()}")
        
        return result
    return wrapper


# Queries optimizadas predefinidas
class OptimizedQueries:
    """Queries optimizadas comunes"""
    
    @staticmethod
    def daily_sales_summary(user_id, date):
        """Resumen de ventas diario optimizado"""
        return db.session.execute(
            """
            SELECT 
                COUNT(DISTINCT o.id) as order_count,
                COUNT(DISTINCT o.customer_phone) as unique_customers,
                SUM(o.total) as total_revenue,
                AVG(o.total) as avg_order_value,
                COUNT(DISTINCT oi.product_id) as products_sold,
                SUM(oi.quantity) as total_items
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            WHERE o.user_id = :user_id
                AND DATE(o.created_at) = :date
                AND o.status = 'delivered'
            """,
            {'user_id': user_id, 'date': date}
        ).first()
    
    @staticmethod
    def top_customers_by_revenue(user_id, limit=10):
        """Top clientes por ingresos"""
        return db.session.execute(
            """
            SELECT 
                c.id,
                c.name,
                c.phone,
                COUNT(DISTINCT o.id) as order_count,
                SUM(o.total) as total_revenue,
                MAX(o.created_at) as last_order_date
            FROM customers c
            INNER JOIN orders o ON c.phone = o.customer_phone
            WHERE c.user_id = :user_id
                AND o.status = 'delivered'
            GROUP BY c.id, c.name, c.phone
            ORDER BY total_revenue DESC
            LIMIT :limit
            """,
            {'user_id': user_id, 'limit': limit}
        ).fetchall()


# Singleton para gestión de performance
performance_optimizer = PerformanceOptimizer()
