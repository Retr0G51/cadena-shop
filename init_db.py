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
    logger.info("Creando constraints y migraciones...")
    
    constraints = [
        # === MIGRACIÓN: Agregar customer_id a orders ===
        """
        DO $$ 
        BEGIN
            -- Verificar si la columna customer_id existe
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='orders' AND column_name='customer_id'
            ) THEN
                ALTER TABLE orders ADD COLUMN customer_id INTEGER;
                ALTER TABLE orders ADD CONSTRAINT fk_orders_customer_id 
                    FOREIGN KEY (customer_id) REFERENCES customers(id);
                RAISE NOTICE 'Columna customer_id agregada a orders';
            ELSE
                RAISE NOTICE 'Columna customer_id ya existe en orders';
            END IF;
        END $$
        """,
        
        # === CHECK CONSTRAINTS ===
        """
        DO $$ 
        BEGIN
            -- Check constraint para price
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.constraint_column_usage 
                WHERE constraint_name = 'check_price_positive'
            ) THEN
                ALTER TABLE products ADD CONSTRAINT check_price_positive CHECK (price >= 0);
                RAISE NOTICE 'Constraint check_price_positive agregado';
            END IF;
        END $$
        """,
        
        """
        DO $$ 
        BEGIN
            -- Check constraint para quantity
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.constraint_column_usage 
                WHERE constraint_name = 'check_quantity_positive'
            ) THEN
                ALTER TABLE order_items ADD CONSTRAINT check_quantity_positive CHECK (quantity > 0);
                RAISE NOTICE 'Constraint check_quantity_positive agregado';
            END IF;
        END $$
        """,
        
        """
        DO $$ 
        BEGIN
            -- Check constraint para stock
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.constraint_column_usage 
                WHERE constraint_name = 'check_stock_non_negative'
            ) THEN
                ALTER TABLE stock_items ADD CONSTRAINT check_stock_non_negative CHECK (quantity >= 0);
                RAISE NOTICE 'Constraint check_stock_non_negative agregado';
            END IF;
        END $$
        """,
        
        """
        DO $$ 
        BEGIN
            -- Check constraint para total
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.constraint_column_usage 
                WHERE constraint_name = 'check_total_non_negative'
            ) THEN
                ALTER TABLE invoices ADD CONSTRAINT check_total_non_negative CHECK (total >= 0);
                RAISE NOTICE 'Constraint check_total_non_negative agregado';
            END IF;
        END $$
        """,
        
        # === FOREIGN KEY CONSTRAINTS ===
        """
        DO $$ 
        BEGIN
            -- FK constraint para order_items -> products
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.constraint_column_usage 
                WHERE constraint_name = 'fk_order_items_product'
            ) THEN
                ALTER TABLE order_items ADD CONSTRAINT fk_order_items_product 
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT;
                RAISE NOTICE 'FK constraint fk_order_items_product agregado';
            END IF;
        END $$
        """,
        
        """
        DO $$ 
        BEGIN
            -- FK constraint para stock_items -> products
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.constraint_column_usage 
                WHERE constraint_name = 'fk_stock_items_product'
            ) THEN
                ALTER TABLE stock_items ADD CONSTRAINT fk_stock_items_product 
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE;
                RAISE NOTICE 'FK constraint fk_stock_items_product agregado';
            END IF;
        END $$
        """,
        
        # === TRIGGER FUNCTION ===
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql'
        """,
        
        # === TRIGGERS ===
        """
        DO $$ 
        BEGIN
            -- Trigger para products
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.triggers 
                WHERE trigger_name = 'update_products_updated_at'
            ) THEN
                CREATE TRIGGER update_products_updated_at 
                    BEFORE UPDATE ON products 
                    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
                RAISE NOTICE 'Trigger update_products_updated_at creado';
            END IF;
        END $$
        """,
        
        """
        DO $$ 
        BEGIN
            -- Trigger para customers
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.triggers 
                WHERE trigger_name = 'update_customers_updated_at'
            ) THEN
                CREATE TRIGGER update_customers_updated_at 
                    BEFORE UPDATE ON customers 
                    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
                RAISE NOTICE 'Trigger update_customers_updated_at creado';
            END IF;
        END $$
        """,
        
        """
        DO $$ 
        BEGIN
            -- Trigger para invoices
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.triggers 
                WHERE trigger_name = 'update_invoices_updated_at'
            ) THEN
                CREATE TRIGGER update_invoices_updated_at 
                    BEFORE UPDATE ON invoices 
                    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
                RAISE NOTICE 'Trigger update_invoices_updated_at creado';
            END IF;
        END $$
        """,
    ]
    
    success_count = 0
    error_count = 0
    
    with db.engine.connect() as conn:
        for constraint in constraints:
            try:
                conn.execute(constraint)
                conn.commit()
                success_count += 1
                logger.debug("✓ Constraint/trigger ejecutado exitosamente")
            except Exception as e:
                error_count += 1
                # Solo mostrar errores que no sean de "ya existe"
                if "already exists" not in str(e).lower() and "duplicate" not in str(e).lower():
                    logger.warning(f"✗ Error ejecutando constraint: {e}")
    
    logger.info(f"✓ Constraints procesados: {success_count} exitosos, {error_count} errores")

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
    
    # Crear usuario administrador
    from werkzeug.security import generate_password_hash
    
    admin_user = User(
        business_name='Admin PedidosSaaS',
        email='admin@pedidossaas.com',
        phone='+34600000000',
        address='Sistema',
        is_active=True
    )
    admin_user.set_password('admin123')
    
    db.session.add(admin_user)
    
    try:
        db.session.commit()
        logger.info("✓ Usuario administrador creado")
        logger.info("  Email: admin@pedidossaas.com")
        logger.info("  Password: admin123")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creando usuario administrador: {e}")

def verify_database():
    """Verifica que la base de datos esté correctamente configurada"""
    logger.info("Verificando base de datos...")
    
    try:
        # Verificar conexión
        with db.engine.connect() as conn:
            result = conn.execute("SELECT 1")
            logger.info("✓ Conexión a base de datos OK")
        
        # Verificar tablas principales
        inspector = db.inspect(db.engine)
        required_tables = [
            'users', 'products', 'orders', 'order_items',
            'customers', 'invoices', 'warehouses', 'stock_items'
        ]
        
        existing_tables = inspector.get_table_names()
        missing_tables = [table for table in required_tables if table not in existing_tables]
        
        if missing_tables:
            logger.error(f"✗ Tablas faltantes: {', '.join(missing_tables)}")
            return False
        
        logger.info("✓ Todas las tablas principales existen")
        
        # Verificar columna customer_id en orders
        orders_columns = [col['name'] for col in inspector.get_columns('orders')]
        if 'customer_id' in orders_columns:
            logger.info("✓ Columna customer_id existe en orders")
        else:
            logger.warning("⚠ Columna customer_id NO existe en orders")
        
        # Verificar índices
        total_indexes = 0
        for table in required_tables:
            if table in existing_tables:
                indexes = inspector.get_indexes(table)
                total_indexes += len(indexes)
                logger.debug(f"Tabla {table}: {len(indexes)} índices")
        
        logger.info(f"✓ Total de índices: {total_indexes}")
        
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
            
            # 2. Crear constraints y migraciones (INCLUYE customer_id)
            create_constraints()
            
            # 3. Crear índices
            create_indexes()
            
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
                logger.info("1. Probar login con admin@pedidossaas.com / admin123")
                logger.info("2. Crear datos de demo: 'python scripts/create_advanced_demo.py'")
                logger.info("3. Acceder a la aplicación y verificar funcionalidad")
                
                logger.info("\n✅ MIGRACIÓN customer_id APLICADA")
                logger.info("El error 500 de login debería estar resuelto")
                
            else:
                logger.error("✗ Error en la verificación de la base de datos")
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"✗ Error fatal: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    main()
