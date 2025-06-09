#!/usr/bin/env python
"""
Script de inicialización de base de datos para PedidosSaaS
Crea todas las tablas, índices y datos iniciales necesarios
"""
import os
import sys
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Agregar el directorio actual al path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.model import User, Product, Order, OrderItem
from app.models.invoice import Invoice, InvoiceSeries, InvoiceItem, InvoicePayment, RecurringInvoice
from app.models.inventory import Warehouse, StockItem, InventoryMovement, StockAlert, PurchaseOrder, PurchaseOrderItem
from app.models.customer import (Customer, CustomerGroup, CustomerInteraction, 
                                MarketingCampaign, CampaignRecipient, LoyaltyProgram, LoyaltyTransaction)

def create_tables():
    """Crea todas las tablas en la base de datos"""
    logger.info("Creando tablas...")
    
    try:
        # Crear todas las tablas
        db.create_all()
        logger.info("✓ Tablas creadas exitosamente")
        
        # Verificar tablas creadas
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        logger.info(f"✓ {len(tables)} tablas encontradas: {', '.join(sorted(tables))}")
        
    except Exception as e:
        logger.error(f"✗ Error creando tablas: {e}")
        raise

def create_indexes():
    """Crea índices optimizados para mejorar el rendimiento"""
    logger.info("Creando índices optimizados...")
    
    indexes = [
        # === ÍNDICES PRINCIPALES ===
        
        # Orders - Búsquedas frecuentes
        "CREATE INDEX IF NOT EXISTS idx_orders_user_status_created ON orders(user_id, status, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_orders_customer_phone ON orders(customer_phone)",
        "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status) WHERE status != 'delivered'",
        
        # Order Items - Joins y agregaciones
        "CREATE INDEX IF NOT EXISTS idx_order_items_order_product ON order_items(order_id, product_id)",
        "CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id)",
        
        # Products - Búsquedas y filtros
        "CREATE INDEX IF NOT EXISTS idx_products_user_active ON products(user_id, is_active)",
        "CREATE INDEX IF NOT EXISTS idx_products_category ON products(user_id, category)",
        "CREATE INDEX IF NOT EXISTS idx_products_name_gin ON products USING gin(to_tsvector('spanish', name))",
        
        # Customers - Búsquedas rápidas
        "CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone)",
        "CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email)",
        "CREATE INDEX IF NOT EXISTS idx_customers_user_segment ON customers(user_id, segment)",
        "CREATE INDEX IF NOT EXISTS idx_customers_last_order ON customers(last_order_date DESC)",
        
        # === ÍNDICES DE FACTURACIÓN ===
        
        # Invoices
        "CREATE INDEX IF NOT EXISTS idx_invoices_user_status ON invoices(user_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_invoices_number ON invoices(invoice_number)",
        "CREATE INDEX IF NOT EXISTS idx_invoices_due_date ON invoices(due_date) WHERE status != 'paid'",
        "CREATE INDEX IF NOT EXISTS idx_invoices_customer ON invoices(user_id, customer_tax_id)",
        
        # Invoice Items
        "CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice ON invoice_items(invoice_id)",
        "CREATE INDEX IF NOT EXISTS idx_invoice_items_product ON invoice_items(product_id)",
        
        # === ÍNDICES DE INVENTARIO ===
        
        # Stock Items
        "CREATE INDEX IF NOT EXISTS idx_stock_items_product_warehouse ON stock_items(product_id, warehouse_id)",
        "CREATE INDEX IF NOT EXISTS idx_stock_items_low_stock ON stock_items(product_id) WHERE quantity <= min_stock",
        
        # Inventory Movements
        "CREATE INDEX IF NOT EXISTS idx_inventory_movements_product ON inventory_movements(product_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_movements_warehouse ON inventory_movements(warehouse_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_inventory_movements_type ON inventory_movements(movement_type, created_at DESC)",
        
        # Stock Alerts
        "CREATE INDEX IF NOT EXISTS idx_stock_alerts_unresolved ON stock_alerts(user_id, is_resolved) WHERE is_resolved = false",
        
        # Purchase Orders
        "CREATE INDEX IF NOT EXISTS idx_purchase_orders_user_status ON purchase_orders(user_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_purchase_orders_supplier ON purchase_orders(user_id, supplier_name)",
        
        # === ÍNDICES CRM ===
        
        # Customer Interactions
        "CREATE INDEX IF NOT EXISTS idx_customer_interactions_customer ON customer_interactions(customer_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_customer_interactions_followup ON customer_interactions(followup_date) WHERE requires_followup = true",
        
        # Marketing Campaigns
        "CREATE INDEX IF NOT EXISTS idx_marketing_campaigns_status ON marketing_campaigns(user_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_marketing_campaigns_scheduled ON marketing_campaigns(scheduled_at) WHERE status = 'scheduled'",
        
        # Campaign Recipients
        "CREATE INDEX IF NOT EXISTS idx_campaign_recipients_campaign ON campaign_recipients(campaign_id)",
        "CREATE INDEX IF NOT EXISTS idx_campaign_recipients_customer ON campaign_recipients(customer_id)",
        
        # === ÍNDICES DE RENDIMIENTO ===
        
        # Índices compuestos para queries complejas
        "CREATE INDEX IF NOT EXISTS idx_orders_daily_summary ON orders(user_id, created_at::date, status)",
        "CREATE INDEX IF NOT EXISTS idx_customer_metrics ON customers(user_id, total_spent DESC, last_order_date DESC)",
        
        # Índices parciales para optimización
        "CREATE INDEX IF NOT EXISTS idx_orders_pending ON orders(user_id, created_at) WHERE status = 'pending'",
        "CREATE INDEX IF NOT EXISTS idx_invoices_overdue ON invoices(user_id, due_date) WHERE status IN ('issued', 'partial') AND due_date < CURRENT_DATE",
        
        # === ÍNDICES PARA BÚSQUEDAS DE TEXTO ===
        
        # Full text search
        "CREATE INDEX IF NOT EXISTS idx_products_search ON products USING gin((to_tsvector('spanish', name) || to_tsvector('spanish', COALESCE(description, ''))))",
        "CREATE INDEX IF NOT EXISTS idx_customers_search ON customers USING gin(to_tsvector('spanish', name))",
        
        # === ÍNDICES ÚNICOS COMPUESTOS ===
        
        # Prevenir duplicados
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_customer_phone ON customers(user_id, phone)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_stock_item ON stock_items(product_id, warehouse_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_warehouse_code ON warehouses(user_id, code)",
    ]
    
    success_count = 0
    error_count = 0
    
    with db.engine.connect() as conn:
        for index in indexes:
            try:
                conn.execute(index)
                conn.commit()
                success_count += 1
                index_name = index.split(' ')[5]
                logger.debug(f"✓ Índice creado: {index_name}")
            except Exception as e:
                error_count += 1
                logger.warning(f"✗ Error creando índice: {e}")
    
    logger.info(f"✓ Índices creados: {success_count} exitosos, {error_count} errores")

def create_constraints():
    """Crea constraints adicionales para integridad de datos"""
    logger.info("Creando constraints...")
    
    constraints = [
        # Check constraints
        "ALTER TABLE products ADD CONSTRAINT check_price_positive CHECK (price >= 0)",
        "ALTER TABLE order_items ADD CONSTRAINT check_quantity_positive CHECK (quantity > 0)",
        "ALTER TABLE stock_items ADD CONSTRAINT check_stock_non_negative CHECK (quantity >= 0)",
        "ALTER TABLE invoices ADD CONSTRAINT check_total_non_negative CHECK (total >= 0)",
        
        # Foreign key constraints con ON DELETE
        "ALTER TABLE order_items ADD CONSTRAINT fk_order_items_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT",
        "ALTER TABLE stock_items ADD CONSTRAINT fk_stock_items_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE",
        
        # Triggers para actualización automática
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql'
        """,
        
        # Aplicar trigger a tablas relevantes
        "CREATE TRIGGER update_products_updated_at BEFORE UPDATE ON products FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
        "CREATE TRIGGER update_customers_updated_at BEFORE UPDATE ON customers FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
        "CREATE TRIGGER update_invoices_updated_at BEFORE UPDATE ON invoices FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    ]
    
    with db.engine.connect() as conn:
        for constraint in constraints:
            try:
                conn.execute(constraint)
                conn.commit()
            except Exception as e:
                # Ignorar errores si el constraint ya existe
                if "already exists" not in str(e):
                    logger.warning(f"Error creando constraint: {e}")

def analyze_tables():
    """Ejecuta ANALYZE en todas las tablas para optimizar queries"""
    logger.info("Analizando tablas...")
    
    tables = [
        'users', 'products', 'orders', 'order_items',
        'customers', 'invoices', 'invoice_items',
        'stock_items', 'inventory_movements', 'warehouses'
    ]
    
    with db.engine.connect() as conn:
        for table in tables:
            try:
                conn.execute(f"ANALYZE {table}")
                conn.commit()
                logger.debug(f"✓ Tabla analizada: {table}")
            except Exception as e:
                logger.warning(f"Error analizando tabla {table}: {e}")

def create_initial_data():
    """Crea datos iniciales necesarios"""
    logger.info("Creando datos iniciales...")
    
    # Verificar si ya existen datos
    if User.query.first():
        logger.info("✓ Ya existen datos en la base de datos")
        return
    
    # Crear usuario de ejemplo
    from werkzeug.security import generate_password_hash
    
    admin_user = User(
        email='admin@pedidossaas.com',
        password_hash=generate_password_hash('admin123'),
        business_name='Administrador del Sistema',
        phone='+34600000000',
        address='Sistema',
        is_active=True,
        is_admin=True,
        plan='enterprise'
    )
    db.session.add(admin_user)
    
    try:
        db.session.commit()
        logger.info("✓ Usuario administrador creado")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creando usuario administrador: {e}")

def verify_database():
    """Verifica que la base de datos esté correctamente configurada"""
    logger.info("Verificando base de datos...")
    
    try:
        # Verificar conexión
        db.engine.execute("SELECT 1")
        logger.info("✓ Conexión a base de datos OK")
        
        # Verificar tablas principales
        inspector = db.inspect(db.engine)
        required_tables = [
            'users', 'products', 'orders', 'order_items',
            'customers', 'invoices', 'warehouses', 'stock_items'
        ]
        
        missing_tables = []
        for table in required_tables:
            if table not in inspector.get_table_names():
                missing_tables.append(table)
        
        if missing_tables:
            logger.error(f"✗ Tablas faltantes: {', '.join(missing_tables)}")
            return False
        
        logger.info("✓ Todas las tablas principales existen")
        
        # Verificar índices
        for table in required_tables:
            indexes = inspector.get_indexes(table)
            logger.debug(f"Tabla {table}: {len(indexes)} índices")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Error verificando base de datos: {e}")
        return False

def main():
    """Función principal"""
    app = create_app()
    
    with app.app_context():
        logger.info("="*50)
        logger.info("Inicializando base de datos PedidosSaaS")
        logger.info("="*50)
        
        start_time = datetime.utcnow()
        
        try:
            # 1. Crear tablas
            create_tables()
            
            # 2. Crear índices
            create_indexes()
            
            # 3. Crear constraints
            create_constraints()
            
            # 4. Analizar tablas
            analyze_tables()
            
            # 5. Crear datos iniciales
            create_initial_data()
            
            # 6. Verificar configuración
            if verify_database():
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                logger.info("="*50)
                logger.info(f"✓ Base de datos inicializada exitosamente en {elapsed:.2f} segundos")
                logger.info("="*50)
                
                # Mostrar información adicional
                logger.info("\nPróximos pasos:")
                logger.info("1. Ejecuta 'python scripts/create_advanced_demo.py' para crear datos de demostración")
                logger.info("2. Ejecuta 'python run.py' para iniciar el servidor")
                logger.info("3. Accede a http://localhost:5000")
            else:
                logger.error("✗ Error en la verificación de la base de datos")
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"✗ Error fatal: {e}")
            sys.exit(1)

if __name__ == '__main__':
    main()
