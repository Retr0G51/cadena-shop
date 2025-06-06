"""
Configuración de Celery para tareas asíncronas
Maneja tareas en background como envío de emails, reportes, etc.
"""
from celery import Celery
from celery.schedules import crontab
from datetime import timedelta
import os

def make_celery(app=None):
    """
    Crea y configura una instancia de Celery
    """
    # Configuración de Celery
    celery = Celery(
        'pedidossaas',
        broker=os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
        backend=os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
        include=['app.automation.tasks']
    )
    
    # Configuración adicional
    celery.conf.update(
        # Serialización
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        
        # Timezone
        timezone='UTC',
        enable_utc=True,
        
        # Resultados
        result_expires=3600,  # 1 hora
        
        # Concurrencia
        worker_pool='gevent',
        worker_concurrency=4,
        
        # Límites de tasa
        task_default_rate_limit='10/s',
        
        # Reintentos
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        
        # Logs
        worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
        worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
        
        # Beat Schedule (tareas programadas)
        beat_schedule={
            # Tareas diarias
            'daily-summary': {
                'task': 'app.automation.tasks.send_daily_summaries',
                'schedule': crontab(hour=9, minute=0),  # 9 AM UTC
                'options': {'queue': 'emails'}
            },
            'check-low-stock': {
                'task': 'app.automation.tasks.check_low_stock',
                'schedule': crontab(hour=8, minute=0),  # 8 AM UTC
                'options': {'queue': 'maintenance'}
            },
            'process-recurring-invoices': {
                'task': 'app.automation.tasks.process_recurring_invoices',
                'schedule': crontab(hour=1, minute=0),  # 1 AM UTC
                'options': {'queue': 'invoicing'}
            },
            'check-overdue-invoices': {
                'task': 'app.automation.tasks.check_overdue_invoices',
                'schedule': crontab(hour=10, minute=0),  # 10 AM UTC
                'options': {'queue': 'invoicing'}
            },
            'update-customer-segments': {
                'task': 'app.automation.tasks.update_customer_segments',
                'schedule': crontab(hour=2, minute=0),  # 2 AM UTC
                'options': {'queue': 'analytics'}
            },
            
            # Tareas horarias
            'process-scheduled-campaigns': {
                'task': 'app.automation.tasks.process_scheduled_campaigns',
                'schedule': crontab(minute=0),  # Cada hora
                'options': {'queue': 'marketing'}
            },
            
            # Tareas semanales
            'backup-database': {
                'task': 'app.automation.tasks.backup_database',
                'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Domingos 3 AM
                'options': {'queue': 'maintenance'}
            },
            'clean-old-data': {
                'task': 'app.automation.tasks.clean_old_data',
                'schedule': crontab(hour=4, minute=0, day_of_week=0),  # Domingos 4 AM
                'options': {'queue': 'maintenance'}
            },
            
            # Tareas mensuales
            'generate-monthly-reports': {
                'task': 'app.automation.tasks.generate_monthly_reports',
                'schedule': crontab(hour=0, minute=30, day_of_month=1),  # 1ro de cada mes
                'options': {'queue': 'reports'}
            },
        }
    )
    
    # Configuración de colas
    celery.conf.task_routes = {
        'app.automation.tasks.send_*': {'queue': 'emails'},
        'app.automation.tasks.*invoice*': {'queue': 'invoicing'},
        'app.automation.tasks.*customer*': {'queue': 'analytics'},
        'app.automation.tasks.*campaign*': {'queue': 'marketing'},
        'app.automation.tasks.*backup*': {'queue': 'maintenance'},
        'app.automation.tasks.*report*': {'queue': 'reports'},
    }
    
    # Si hay una app Flask, actualizar configuración
    if app:
        celery.conf.update(app.config)
        
        # Contexto de aplicación para tareas
        class ContextTask(celery.Task):
            """Hace que las tareas de Celery funcionen con el contexto de Flask"""
            abstract = True
            
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        
        celery.Task = ContextTask
    
    return celery

# Crear instancia de Celery
celery = make_celery()

# Importar tareas para que Celery las reconozca
from app.automation import tasks

# Tareas de ejemplo
@celery.task(bind=True, max_retries=3)
def send_async_email(self, email_data):
    """
    Envía un email de forma asíncrona
    """
    try:
        from flask_mail import Message
        from app.extensions import mail
        
        msg = Message(
            subject=email_data['subject'],
            sender=email_data.get('sender'),
            recipients=email_data['recipients']
        )
        
        if 'body' in email_data:
            msg.body = email_data['body']
        if 'html' in email_data:
            msg.html = email_data['html']
        
        mail.send(msg)
        return {'status': 'sent', 'recipients': email_data['recipients']}
        
    except Exception as exc:
        # Reintentar en caso de error
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

@celery.task
def generate_report_async(user_id, report_type, params):
    """
    Genera un reporte de forma asíncrona
    """
    from app.dashboard.analytics import Analytics
    from app.utils.reports import ReportGenerator
    
    try:
        analytics = Analytics(user_id)
        data = analytics.export_analytics_data(report_type)
        
        generator = ReportGenerator()
        file_path = generator.create_report(data, params.get('format', 'pdf'))
        
        # Enviar notificación o email con el reporte
        return {
            'status': 'completed',
            'file_path': file_path,
            'generated_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e)
        }

@celery.task
def process_bulk_import(user_id, file_path, import_type):
    """
    Procesa importación masiva de datos
    """
    from app.utils.importers import BulkImporter
    
    try:
        importer = BulkImporter(user_id)
        
        if import_type == 'products':
            result = importer.import_products(file_path)
        elif import_type == 'customers':
            result = importer.import_customers(file_path)
        elif import_type == 'inventory':
            result = importer.import_inventory(file_path)
        else:
            raise ValueError(f"Tipo de importación no válido: {import_type}")
        
        return {
            'status': 'completed',
            'imported': result['success'],
            'errors': result['errors'],
            'total': result['total']
        }
        
    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e)
        }

@celery.task
def optimize_images_async(user_id):
    """
    Optimiza todas las imágenes de un usuario
    """
    from app.utils.image_optimizer import ImageOptimizer
    
    try:
        optimizer = ImageOptimizer()
        result = optimizer.optimize_user_images(user_id)
        
        return {
            'status': 'completed',
            'optimized': result['optimized'],
            'space_saved': result['space_saved'],
            'errors': result['errors']
        }
        
    except Exception as e:
        return {
            'status': 'failed',
            'error': str(e)
        }

# Comandos de Celery para el CLI
if __name__ == '__main__':
    celery.start()
