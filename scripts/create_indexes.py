#!/usr/bin/env python
"""
Script para crear índices optimizados en la base de datos
Se ejecuta después de init_db.py
"""
import os
import sys
import logging

# Configurar path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_indexes():
    """Crea índices optimizados para mejorar el rendimiento"""
    
    indexes = [
        # === ÍNDICES PRINCIPALES ===
        
        # Orders
        "CREATE INDEX IF NOT EXISTS idx_orders_user_status_created ON orders(user_id, status, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_orders_customer_phone ON orders(customer_phone)",
        "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_orders_daily ON orders(user_id, created_at::date) WHERE status = 'delivered'",
        
        # Order Items
        "CREATE INDEX IF NOT EXISTS idx_order_items_order_product ON order_items(order_id, product_id)",
        
        # Products
        "CREATE INDEX IF NOT EXISTS idx_products_user_active ON products(user_id, is_active)",
        "CREATE INDEX IF NOT EXISTS idx_products_name_gin ON products USING gin(to_tsvector('spanish', name))",
        
        # Customers
        "CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone)",
        "CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email)",
        "CREATE INDEX IF NOT EXISTS idx_customers_user_segment ON customers(user_id, segment)",
        
        # Invoices
        "CREATE INDEX IF NOT EXISTS idx_invoices_user_status ON invoices(user_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_invoices_due_date ON invoices(due_date) WHERE status != 'paid'",
        
        # Stock Items
        "CREATE INDEX IF NOT EXISTS idx_stock_items_product_warehouse ON stock_items(product_id, warehouse_id)",
        "CREATE INDEX IF NOT EXISTS idx_stock_items_low_stock ON stock_items(warehouse_id) WHERE quantity <= min_stock",
        
        # Inventory Movements
        "CREATE INDEX IF NOT EXISTS idx_inventory_movements_product ON inventory_movements(product_id, created_at DESC)",
        
        # Unique constraints
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_customer_phone ON customers(user_id, phone)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_stock_item ON stock_items(product_id, warehouse_id)",
    ]
    
    success_count = 0
    error_count = 0
    
    with db.engine.connect() as conn:
        for index in indexes:
            try:
                conn.execute(index)
                conn.commit()
                success_count += 1
                logger.info(f"✓ Índice creado: {index.split(' ')[5]}")
            except Exception as e:
                error_count += 1
                if "already exists" not in str(e):
                    logger.error(f"✗ Error creando índice: {e}")
    
    logger.info(f"\n✓ Índices creados: {success_count} exitosos, {error_count} errores")
    
    # Analizar tablas
    logger.info("\nAnalizando tablas para optimizar queries...")
    tables = ['users', 'products', 'orders', 'order_items', 'customers', 'invoices', 'stock_items']
    
    with db.engine.connect() as conn:
        for table in tables:
            try:
                conn.execute(f"ANALYZE {table}")
                conn.commit()
                logger.info(f"✓ Tabla analizada: {table}")
            except Exception as e:
                logger.warning(f"Error analizando tabla {table}: {e}")

def main():
    """Función principal"""
    app = create_app()
    
    with app.app_context():
        logger.info("="*50)
        logger.info("Creando índices optimizados...")
        logger.info("="*50)
        
        create_indexes()
        
        logger.info("\n✓ Proceso completado")

if __name__ == '__main__':
    main()
