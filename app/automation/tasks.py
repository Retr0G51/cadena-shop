"""
Sistema de Automatización para PedidosSaaS
Tareas programadas, notificaciones y procesos automáticos
"""
from datetime import datetime, timedelta
from decimal import Decimal
from flask import current_app, render_template
from sqlalchemy import and_, or_
from app import db
from app.models import User, Order, Product
from app.models.invoice import Invoice, RecurringInvoice
from app.models.inventory import StockItem, StockAlert
from app.models.customer import Customer, MarketingCampaign, CampaignRecipient
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

logger = logging.getLogger(__name__)

class AutomationTasks:
    """Clase principal para tareas automatizadas"""
    
    @staticmethod
    def run_daily_tasks():
        """Ejecuta todas las tareas diarias"""
        logger.info("Iniciando tareas diarias...")
        
        try:
            AutomationTasks.send_daily_summaries()
            AutomationTasks.check_low_stock()
            AutomationTasks.process_recurring_invoices()
            AutomationTasks.check_overdue_invoices()
            AutomationTasks.update_customer_segments()
            AutomationTasks.clean_old_data()
            logger.info("Tareas diarias completadas")
        except Exception as e:
            logger.error(f"Error en tareas diarias: {str(e)}")
    
    @staticmethod
    def send_daily_summaries():
        """Envía resumen diario a cada negocio"""
        yesterday = datetime.utcnow() - timedelta(days=1)
        today = datetime.utcnow()
        
        active_users = User.query.filter_by(is_active=True).all()
        
        for user in active_users:
            # Obtener estadísticas del día
            daily_orders = Order.query.filter(
                Order.user_id == user.id,
                Order.created_at >= yesterday,
                Order.created_at < today
            ).all()
            
            if not daily_orders:
                continue
            
            # Calcular métricas
            total_orders = len(daily_orders)
            completed_orders = len([o for o in daily_orders if o.status == 'delivered'])
            total_revenue = sum(o.total for o in daily_orders if o.status == 'delivered')
            
            # Productos más vendidos
            product_sales = {}
            for order in daily_orders:
                for item in order.items:
                    if item.product_id not in product_sales:
                        product_sales[item.product_id] = {
                            'name': item.product.name,
                            'quantity': 0,
                            'revenue': 0
                        }
                    product_sales[item.product_id]['quantity'] += item.quantity
                    product_sales[item.product_id]['revenue'] += item.subtotal
            
            top_products = sorted(
                product_sales.values(),
                key=lambda x: x['revenue'],
                reverse=True
            )[:5]
            
            # Enviar email
            try:
                AutomationTasks._send_email(
                    to=user.email,
                    subject=f"Resumen diario - {user.business_name}",
                    template='emails/daily_summary.html',
                    context={
                        'user': user,
                        'date': yesterday.strftime('%d/%m/%Y'),
                        'total_orders': total_orders,
                        'completed_orders': completed_orders,
                        'total_revenue': total_revenue,
                        'completion_rate': (completed_orders / total_orders * 100) if total_orders > 0 else 0,
                        'top_products': top_products
                    }
                )
                logger.info(f"Resumen diario enviado a {user.email}")
            except Exception as e:
                logger.error(f"Error enviando resumen a {user.email}: {str(e)}")
    
    @staticmethod
    def check_low_stock():
        """Verifica productos con stock bajo y crea alertas"""
        stock_items = db.session.query(StockItem).join(
            Product
        ).filter(
            StockItem.quantity <= StockItem.reorder_point
        ).all()
        
        for stock_item in stock_items:
            # Verificar si ya existe alerta activa
            existing_alert = StockAlert.query.filter_by(
                product_id=stock_item.product_id,
                warehouse_id=stock_item.warehouse_id,
                alert_type='low_stock',
                is_resolved=False
            ).first()
            
            if not existing_alert:
                alert = StockAlert(
                    user_id=stock_item.product.user_id,
                    product_id=stock_item.product_id,
                    warehouse_id=stock_item.warehouse_id,
                    alert_type='low_stock',
                    threshold_value=stock_item.reorder_point,
                    current_value=stock_item.quantity,
                    message=f'Stock bajo: {stock_item.product.name} - {stock_item.quantity} unidades restantes'
                )
                db.session.add(alert)
                
                # Enviar notificación
                user = User.query.get(stock_item.product.user_id)
                if user:
                    try:
                        AutomationTasks._send_email(
                            to=user.email,
                            subject=f"Alerta de stock bajo - {stock_item.product.name}",
                            template='emails/stock_alert.html',
                            context={
                                'user': user,
                                'product': stock_item.product,
                                'current_stock': stock_item.quantity,
                                'reorder_point': stock_item.reorder_point,
                                'warehouse': stock_item.warehouse.name
                            }
                        )
                    except Exception as e:
                        logger.error(f"Error enviando alerta de stock: {str(e)}")
        
        db.session.commit()
        logger.info(f"Verificación de stock completada. {len(stock_items)} productos con stock bajo.")
    
    @staticmethod
    def process_recurring_invoices():
        """Procesa facturas recurrentes"""
        today = datetime.utcnow().date()
        
        recurring_invoices = RecurringInvoice.query.filter(
            RecurringInvoice.is_active == True,
            RecurringInvoice.next_issue_date <= today
        ).all()
        
        for recurring in recurring_invoices:
            try:
                # Crear nueva factura
                invoice = recurring.create_invoice()
                invoice.calculate_totals()
                invoice.status = 'issued'
                invoice.issued_at = datetime.utcnow()
                
                # Establecer fecha de vencimiento (30 días por defecto)
                invoice.due_date = datetime.utcnow() + timedelta(days=30)
                
                db.session.add(invoice)
                
                # Actualizar próxima fecha
                recurring.calculate_next_date()
                recurring.last_issued_date = datetime.utcnow()
                
                # Enviar factura por email
                if invoice.customer_email:
                    AutomationTasks._send_invoice_email(invoice)
                
                logger.info(f"Factura recurrente generada: {invoice.invoice_number}")
                
            except Exception as e:
                logger.error(f"Error procesando factura recurrente {recurring.id}: {str(e)}")
        
        db.session.commit()
        logger.info(f"Procesadas {len(recurring_invoices)} facturas recurrentes")
    
    @staticmethod
    def check_overdue_invoices():
        """Verifica facturas vencidas y envía recordatorios"""
        overdue_invoices = Invoice.query.filter(
            Invoice.status.in_(['issued', 'partial']),
            Invoice.due_date < datetime.utcnow()
        ).all()
        
        for invoice in overdue_invoices:
            days_overdue = (datetime.utcnow() - invoice.due_date).days
            
            # Enviar recordatorios en intervalos: 1, 7, 15, 30 días
            if days_overdue in [1, 7, 15, 30]:
                try:
                    user = User.query.get(invoice.user_id)
                    
                    # Enviar recordatorio al cliente
                    if invoice.customer_email:
                        AutomationTasks._send_email(
                            to=invoice.customer_email,
                            subject=f"Recordatorio de pago - Factura {invoice.invoice_number}",
                            template='emails/payment_reminder.html',
                            context={
                                'invoice': invoice,
                                'business': user,
                                'days_overdue': days_overdue,
                                'pending_amount': invoice.get_pending_amount()
                            }
                        )
                    
                    # Notificar al negocio
                    AutomationTasks._send_email(
                        to=user.email,
                        subject=f"Factura vencida - {invoice.invoice_number}",
                        body=f"La factura {invoice.invoice_number} de {invoice.customer_name} está vencida hace {days_overdue} días."
                    )
                    
                    logger.info(f"Recordatorio enviado para factura {invoice.invoice_number}")
                    
                except Exception as e:
                    logger.error(f"Error enviando recordatorio para factura {invoice.id}: {str(e)}")
        
        logger.info(f"Verificadas {len(overdue_invoices)} facturas vencidas")
    
    @staticmethod
    def update_customer_segments():
        """Actualiza segmentación automática de clientes"""
        customers = Customer.query.filter_by(is_active=True).all()
        
        for customer in customers:
            # Actualizar métricas
            customer.update_metrics()
            
            # Segmentación automática basada en valor
            if customer.total_spent >= 1000:
                customer.segment = 'vip'
            elif customer.total_spent >= 500:
                customer.segment = 'premium'
            elif customer.total_spent >= 100:
                customer.segment = 'regular'
            else:
                customer.segment = 'new'
            
            # Detectar clientes en riesgo
            if customer.is_at_risk:
                customer.add_tag('at_risk')
                
                # Crear campaña de retención si no existe
                existing_campaign = MarketingCampaign.query.filter_by(
                    user_id=customer.user_id,
                    campaign_type='retention',
                    status='active'
                ).first()
                
                if not existing_campaign:
                    # Aquí se podría crear una campaña automática de retención
                    pass
        
        db.session.commit()
        logger.info(f"Actualizada segmentación de {len(customers)} clientes")
    
    @staticmethod
    def process_scheduled_campaigns():
        """Procesa campañas de marketing programadas"""
        now = datetime.utcnow()
        
        scheduled_campaigns = MarketingCampaign.query.filter(
            MarketingCampaign.status == 'scheduled',
            MarketingCampaign.scheduled_at <= now
        ).all()
        
        for campaign in scheduled_campaigns:
            try:
                # Obtener destinatarios
                if campaign.target_group_id:
                    recipients = campaign.target_group.customers
                else:
                    # Aplicar criterios personalizados
                    recipients = Customer.query.filter_by(
                        user_id=campaign.user_id,
                        accepts_marketing=True
                    ).all()
                
                campaign.total_recipients = len(recipients)
                campaign.status = 'active'
                campaign.sent_at = now
                
                # Crear registros de destinatarios
                for customer in recipients:
                    recipient = CampaignRecipient(
                        campaign_id=campaign.id,
                        customer_id=customer.id
                    )
                    db.session.add(recipient)
                    
                    # Enviar campaña
                    if campaign.campaign_type == 'email' and customer.email:
                        AutomationTasks._send_campaign_email(campaign, customer)
                        recipient.status = 'sent'
                        recipient.sent_at = now
                        campaign.total_sent += 1
                
                logger.info(f"Campaña {campaign.name} enviada a {campaign.total_sent} destinatarios")
                
            except Exception as e:
                logger.error(f"Error procesando campaña {campaign.id}: {str(e)}")
                campaign.status = 'failed'
        
        db.session.commit()
    
    @staticmethod
    def clean_old_data():
        """Limpia datos antiguos según políticas de retención"""
        # Eliminar alertas resueltas de más de 90 días
        old_alerts = StockAlert.query.filter(
            StockAlert.is_resolved == True,
            StockAlert.resolved_at < datetime.utcnow() - timedelta(days=90)
        ).all()
        
        for alert in old_alerts:
            db.session.delete(alert)
        
        # Eliminar movimientos de inventario de más de 1 año
        old_movements = InventoryMovement.query.filter(
            InventoryMovement.created_at < datetime.utcnow() - timedelta(days=365)
        ).limit(1000).all()  # Procesar en lotes
        
        for movement in old_movements:
            db.session.delete(movement)
        
        db.session.commit()
        logger.info(f"Limpieza completada: {len(old_alerts)} alertas y {len(old_movements)} movimientos eliminados")
    
    @staticmethod
    def backup_database():
        """Crea backup de la base de datos"""
        # Esta función debería llamar al script backup_db.py
        import subprocess
        
        try:
            result = subprocess.run(['python', 'scripts/backup_db.py'], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info("Backup de base de datos completado")
            else:
                logger.error(f"Error en backup: {result.stderr}")
        except Exception as e:
            logger.error(f"Error ejecutando backup: {str(e)}")
    
    @staticmethod
    def _send_email(to, subject, body=None, template=None, context=None):
        """Función auxiliar para enviar emails"""
        # Configuración SMTP desde variables de entorno
        smtp_server = current_app.config.get('MAIL_SERVER', 'localhost')
        smtp_port = current_app.config.get('MAIL_PORT', 587)
        smtp_username = current_app.config.get('MAIL_USERNAME')
        smtp_password = current_app.config.get('MAIL_PASSWORD')
        from_email = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@pedidossaas.com')
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to
        
        # Contenido del email
        if template and context:
            # Renderizar template HTML
            html_body = render_template(template, **context)
            msg.attach(MIMEText(html_body, 'html'))
        elif body:
            msg.attach(MIMEText(body, 'plain'))
        
        # Enviar email
        try:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if smtp_username and smtp_password:
                    server.starttls()
                    server.login(smtp_username, smtp_password)
                server.send_message(msg)
        except Exception as e:
            logger.error(f"Error enviando email: {str(e)}")
            raise
    
    @staticmethod
    def _send_invoice_email(invoice):
        """Envía factura por email"""
        user = User.query.get(invoice.user_id)
        
        AutomationTasks._send_email(
            to=invoice.customer_email,
            subject=f"Factura {invoice.invoice_number} - {user.business_name}",
            template='emails/invoice.html',
            context={
                'invoice': invoice,
                'business': user,
                'items': invoice.items.all(),
                'payment_url': f"{current_app.config['BASE_URL']}/pay/{invoice.id}"
            }
        )
    
    @staticmethod
    def _send_campaign_email(campaign, customer):
        """Envía email de campaña"""
        user = User.query.get(campaign.user_id)
        
        # Personalizar contenido
        content = campaign.content
        if content:
            content = content.replace('{{customer_name}}', customer.name)
            content = content.replace('{{business_name}}', user.business_name)
        
        AutomationTasks._send_email(
            to=customer.email,
            subject=campaign.subject,
            body=content
        )

# Scheduler functions para usar con APScheduler o Celery
def schedule_daily_tasks():
    """Programa tareas diarias"""
    AutomationTasks.run_daily_tasks()

def schedule_hourly_tasks():
    """Programa tareas horarias"""
    AutomationTasks.process_scheduled_campaigns()

def schedule_weekly_tasks():
    """Programa tareas semanales"""
    AutomationTasks.backup_database()
