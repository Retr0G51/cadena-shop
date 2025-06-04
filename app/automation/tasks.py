"""
Sistema de automatización para tareas programadas y recordatorios
Optimizado para funcionar con recursos limitados
"""

import os
from datetime import datetime, timedelta
from flask import current_app, render_template
from flask_mail import Mail, Message
from app.extensions import db
from app.models import User, Order, Invoice, Customer, Product, StockAlert
from app.models.invoice import Invoice
from app.models.inventory import StockMovement, InventoryValuation
from app.models.customer import Customer, CustomerInteraction
import logging
from functools import wraps
import schedule
import time
import threading
from sqlalchemy import and_, or_


# Configurar logging
logger = logging.getLogger(__name__)


class AutomationSystem:
    """Sistema principal de automatización"""
    
    def __init__(self, app=None):
        self.app = app
        self.mail = None
        self.running = False
        self.thread = None
        
    def init_app(self, app):
        """Inicializa el sistema con la aplicación Flask"""
        self.app = app
        self.mail = Mail(app)
        
        # Configurar tareas programadas
        self.setup_scheduled_tasks()
        
        # Iniciar en un thread separado
        if app.config.get('ENABLE_AUTOMATION', True):
            self.start()
    
    def setup_scheduled_tasks(self):
        """Configura todas las tareas programadas"""
        # Tareas diarias
        schedule.every().day.at("09:00").do(self.daily_tasks)
        schedule.every().day.at("14:00").do(self.check_pending_payments)
        schedule.every().day.at("18:00").do(self.send_daily_summary)
        
        # Tareas cada hora
        schedule.every().hour.do(self.check_low_stock)
        
        # Tareas semanales
        schedule.every().monday.at("10:00").do(self.weekly_reports)
        
        # Tareas mensuales (primer día del mes)
        schedule.every().day.at("01:00").do(self.monthly_tasks)
        
        # Backup automático (cada 6 horas)
        schedule.every(6).hours.do(self.backup_database)
    
    def start(self):
        """Inicia el sistema de automatización en un thread"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run_scheduler)
            self.thread.daemon = True
            self.thread.start()
            logger.info("Sistema de automatización iniciado")
    
    def stop(self):
        """Detiene el sistema de automatización"""
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("Sistema de automatización detenido")
    
    def _run_scheduler(self):
        """Ejecuta el scheduler en un loop"""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Verificar cada minuto
            except Exception as e:
                logger.error(f"Error en scheduler: {e}")
    
    def daily_tasks(self):
        """Tareas diarias automáticas"""
        with self.app.app_context():
            try:
                # 1. Actualizar estadísticas de clientes
                self.update_customer_statistics()
                
                # 2. Verificar cumpleaños
                self.check_customer_birthdays()
                
                # 3. Actualizar segmentación automática
                self.update_customer_segments()
                
                # 4. Limpiar datos antiguos
                self.cleanup_old_data()
                
                logger.info("Tareas diarias completadas")
            except Exception as e:
                logger.error(f"Error en tareas diarias: {e}")
    
    def check_pending_payments(self):
        """Verifica pagos pendientes y envía recordatorios"""
        with self.app.app_context():
            try:
                # Facturas vencidas
                overdue_invoices = Invoice.query.filter(
                    Invoice.status == 'sent',
                    Invoice.due_date < datetime.utcnow(),
                    Invoice.payment_status != 'paid'
                ).all()
                
                for invoice in overdue_invoices:
                    # Actualizar estado
                    invoice.status = 'overdue'
                    
                    # Enviar recordatorio si no se ha enviado en los últimos 3 días
                    if not invoice.last_reminder_sent or \
                       (datetime.utcnow() - invoice.last_reminder_sent).days >= 3:
                        self.send_payment_reminder(invoice)
                        invoice.last_reminder_sent = datetime.utcnow()
                
                db.session.commit()
                logger.info(f"Procesados {len(overdue_invoices)} pagos vencidos")
                
            except Exception as e:
                logger.error(f"Error verificando pagos: {e}")
                db.session.rollback()
    
    def check_low_stock(self):
        """Verifica productos con stock bajo y crea alertas"""
        with self.app.app_context():
            try:
                # Productos con stock bajo
                from app.models import Product
                
                low_stock_products = Product.query.filter(
                    Product.is_active == True,
                    Product.track_inventory == True,
                    Product.stock <= Product.min_stock
                ).all()
                
                alerts_created = 0
                for product in low_stock_products:
                    # Crear o actualizar alerta
                    alert = StockAlert.create_or_update_alert(product)
                    
                    # Notificar si es crítico o no se ha notificado en 24h
                    if alert.severity == 'critical' or not alert.last_notified_at or \
                       (datetime.utcnow() - alert.last_notified_at).hours >= 24:
                        self.notify_stock_alert(alert)
                        alert.last_notified_at = datetime.utcnow()
                        alerts_created += 1
                
                db.session.commit()
                
                if alerts_created > 0:
                    logger.info(f"Creadas {alerts_created} alertas de stock")
                    
            except Exception as e:
                logger.error(f"Error verificando stock: {e}")
                db.session.rollback()
    
    def send_daily_summary(self):
        """Envía resumen diario a cada negocio"""
        with self.app.app_context():
            try:
                # Obtener negocios activos
                active_businesses = User.query.filter_by(
                    is_active=True,
                    accept_orders=True
                ).all()
                
                for business in active_businesses:
                    # Generar resumen del día
                    summary = self.generate_daily_summary(business)
                    
                    # Enviar por email si está configurado
                    if business.email and business.notification_preferences.get('daily_summary', True):
                        self.send_summary_email(business, summary)
                
                logger.info(f"Enviados {len(active_businesses)} resúmenes diarios")
                
            except Exception as e:
                logger.error(f"Error enviando resúmenes: {e}")
    
    def weekly_reports(self):
        """Genera reportes semanales"""
        with self.app.app_context():
            try:
                # Generar reportes para cada negocio
                businesses = User.query.filter_by(is_active=True).all()
                
                for business in businesses:
                    # Generar reporte
                    report = self.generate_weekly_report(business)
                    
                    # Guardar en base de datos
                    self.save_report(business, 'weekly', report)
                    
                    # Notificar si está habilitado
                    if business.notification_preferences.get('weekly_reports', True):
                        self.notify_report_ready(business, 'weekly')
                
                logger.info(f"Generados {len(businesses)} reportes semanales")
                
            except Exception as e:
                logger.error(f"Error generando reportes semanales: {e}")
    
    def monthly_tasks(self):
        """Tareas mensuales"""
        # Solo ejecutar el primer día del mes
        if datetime.utcnow().day != 1:
            return
        
        with self.app.app_context():
            try:
                # 1. Generar valoración de inventario
                self.generate_inventory_valuations()
                
                # 2. Actualizar lifetime value de clientes
                self.update_customer_lifetime_values()
                
                # 3. Archivar datos antiguos
                self.archive_old_data()
                
                # 4. Generar reportes mensuales
                self.generate_monthly_reports()
                
                logger.info("Tareas mensuales completadas")
                
            except Exception as e:
                logger.error(f"Error en tareas mensuales: {e}")
    
    def backup_database(self):
        """Realiza backup de la base de datos"""
        with self.app.app_context():
            try:
                # Crear directorio de backups si no existe
                backup_dir = os.path.join(self.app.root_path, 'backups')
                os.makedirs(backup_dir, exist_ok=True)
                
                # Generar nombre del archivo
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                
                # Si es PostgreSQL
                db_url = self.app.config['SQLALCHEMY_DATABASE_URI']
                if 'postgresql' in db_url:
                    backup_file = os.path.join(backup_dir, f'backup_{timestamp}.sql')
                    
                    # Comando pg_dump
                    import subprocess
                    cmd = f'pg_dump {db_url} > {backup_file}'
                    subprocess.run(cmd, shell=True, check=True)
                    
                    # Comprimir
                    import gzip
                    with open(backup_file, 'rb') as f_in:
                        with gzip.open(f'{backup_file}.gz', 'wb') as f_out:
                            f_out.writelines(f_in)
                    
                    # Eliminar archivo sin comprimir
                    os.remove(backup_file)
                    
                    logger.info(f"Backup creado: {backup_file}.gz")
                
                # Limpiar backups antiguos (mantener últimos 30)
                self.cleanup_old_backups(backup_dir, keep_last=30)
                
            except Exception as e:
                logger.error(f"Error creando backup: {e}")
    
    # Métodos auxiliares
    
    def update_customer_statistics(self):
        """Actualiza estadísticas de todos los clientes"""
        customers = Customer.query.all()
        for customer in customers:
            customer.update_statistics()
        db.session.commit()
    
    def check_customer_birthdays(self):
        """Verifica cumpleaños próximos y envía felicitaciones"""
        # Clientes con cumpleaños en los próximos 7 días
        today = datetime.utcnow().date()
        
        customers_with_birthdays = Customer.query.filter(
            Customer.birthdate.isnot(None),
            Customer.status == 'active',
            Customer.marketing_consent == True
        ).all()
        
        for customer in customers_with_birthdays:
            if customer.is_birthday_soon:
                # Crear interacción
                interaction = CustomerInteraction(
                    customer_id=customer.id,
                    user_id=customer.user_id,
                    interaction_type='note',
                    subject='Cumpleaños próximo',
                    description=f'Cumpleaños el {customer.birthdate.strftime("%d/%m")}',
                    follow_up_required=True,
                    follow_up_date=customer.birthdate.replace(year=today.year)
                )
                db.session.add(interaction)
    
    def update_customer_segments(self):
        """Actualiza segmentación automática de clientes"""
        from app.models.customer import CustomerGroup
        
        auto_groups = CustomerGroup.query.filter_by(
            group_type='automatic',
            is_active=True
        ).all()
        
        for group in auto_groups:
            group.update_automatic_members()
        
        db.session.commit()
    
    def cleanup_old_data(self):
        """Limpia datos antiguos para optimizar rendimiento"""
        # Eliminar movimientos de stock muy antiguos (> 2 años)
        cutoff_date = datetime.utcnow() - timedelta(days=730)
        
        old_movements = StockMovement.query.filter(
            StockMovement.created_at < cutoff_date
        ).limit(1000).all()  # Procesar en lotes
        
        for movement in old_movements:
            db.session.delete(movement)
        
        db.session.commit()
    
    def generate_daily_summary(self, business):
        """Genera resumen diario para un negocio"""
        today = datetime.utcnow().date()
        
        # Pedidos del día
        today_orders = Order.query.filter(
            Order.user_id == business.id,
            func.date(Order.created_at) == today
        ).all()
        
        # Calcular totales
        total_revenue = sum(order.total for order in today_orders if order.status != 'cancelled')
        
        # Productos más vendidos hoy
        from sqlalchemy import func
        top_products = db.session.query(
            Product.name,
            func.sum(OrderItem.quantity).label('total_sold')
        ).join(OrderItem).join(Order).filter(
            Order.user_id == business.id,
            func.date(Order.created_at) == today,
            Order.status != 'cancelled'
        ).group_by(Product.id).order_by(
            func.sum(OrderItem.quantity).desc()
        ).limit(5).all()
        
        return {
            'date': today,
            'total_orders': len(today_orders),
            'total_revenue': total_revenue,
            'pending_orders': len([o for o in today_orders if o.status == 'pending']),
            'top_products': top_products,
            'low_stock_alerts': StockAlert.query.filter_by(
                user_id=business.id,
                status='active'
            ).count()
        }
    
    def send_summary_email(self, business, summary):
        """Envía email con resumen diario"""
        try:
            msg = Message(
                subject=f"Resumen diario - {summary['date'].strftime('%d/%m/%Y')}",
                sender=self.app.config['MAIL_DEFAULT_SENDER'],
                recipients=[business.email]
            )
            
            # Renderizar template
            msg.html = render_template('emails/daily_summary.html',
                business=business,
                summary=summary
            )
            
            self.mail.send(msg)
            
        except Exception as e:
            logger.error(f"Error enviando email a {business.email}: {e}")
    
    def send_payment_reminder(self, invoice):
        """Envía recordatorio de pago"""
        try:
            if not invoice.client_email:
                return
            
            msg = Message(
                subject=f"Recordatorio de pago - Factura {invoice.invoice_number}",
                sender=self.app.config['MAIL_DEFAULT_SENDER'],
                recipients=[invoice.client_email]
            )
            
            msg.html = render_template('emails/payment_reminder.html',
                invoice=invoice,
                business=invoice.business
            )
            
            self.mail.send(msg)
            
            # Registrar interacción
            if invoice.order and invoice.order.customer_id:
                interaction = CustomerInteraction(
                    customer_id=invoice.order.customer_id,
                    user_id=invoice.user_id,
                    interaction_type='email',
                    channel='email',
                    subject='Recordatorio de pago enviado',
                    description=f'Recordatorio automático para factura {invoice.invoice_number}',
                    status='completed'
                )
                db.session.add(interaction)
            
        except Exception as e:
            logger.error(f"Error enviando recordatorio de pago: {e}")
    
    def cleanup_old_backups(self, backup_dir, keep_last=30):
        """Elimina backups antiguos"""
        import glob
        
        backups = sorted(glob.glob(os.path.join(backup_dir, 'backup_*.sql.gz')))
        
        if len(backups) > keep_last:
            for backup in backups[:-keep_last]:
                os.remove(backup)
                logger.info(f"Backup eliminado: {backup}")


# Decorador para tareas asíncronas
def async_task(f):
    """Ejecuta una tarea en background"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        thread = threading.Thread(target=f, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
        return thread
    return decorated_function


# Tareas específicas que pueden ser llamadas manualmente

@async_task
def send_bulk_email(user_id, customer_group_id, subject, content):
    """Envía emails masivos a un grupo de clientes"""
    with current_app.app_context():
        try:
            from app.models.customer import CustomerGroup
            
            group = CustomerGroup.query.get(customer_group_id)
            if not group or group.user_id != user_id:
                return
            
            mail = Mail(current_app)
            sent_count = 0
            
            for member in group.members:
                if member.customer.email and member.customer.marketing_consent:
                    try:
                        msg = Message(
                            subject=subject,
                            sender=current_app.config['MAIL_DEFAULT_SENDER'],
                            recipients=[member.customer.email]
                        )
                        
                        # Personalizar contenido
                        personalized_content = content.replace('{nombre}', member.customer.name)
                        msg.html = personalized_content
                        
                        mail.send(msg)
                        sent_count += 1
                        
                        # Pequeña pausa para no saturar
                        time.sleep(0.5)
                        
                    except Exception as e:
                        logger.error(f"Error enviando a {member.customer.email}: {e}")
            
            logger.info(f"Enviados {sent_count} emails a grupo {group.name}")
            
        except Exception as e:
            logger.error(f"Error en envío masivo: {e}")


@async_task
def generate_inventory_valuations():
    """Genera valoraciones de inventario para todos los negocios"""
    with current_app.app_context():
        try:
            from app.models.inventory import InventoryValuation
            
            businesses = User.query.filter_by(is_active=True).all()
            
            for business in businesses:
                # Calcular valoración actual
                valuation_data = InventoryValuation.calculate_current_valuation(business.id)
                
                # Crear registro
                valuation = InventoryValuation(
                    user_id=business.id,
                    valuation_date=datetime.utcnow().date(),
                    **valuation_data
                )
                
                db.session.add(valuation)
            
            db.session.commit()
            logger.info(f"Generadas {len(businesses)} valoraciones de inventario")
            
        except Exception as e:
            logger.error(f"Error generando valoraciones: {e}")
            db.session.rollback()


# Instancia global del sistema
automation_system = AutomationSystem()
