"""
Módulo de automatización para PedidosSaaS
Gestiona tareas programadas y procesos automáticos
"""

from app.automation.tasks import AutomationTasks

__all__ = ['AutomationTasks']

# Registrar tareas de Celery
def register_tasks(celery):
    """Registra todas las tareas de Celery"""
    from app.automation import tasks
    
    # Las tareas se registran automáticamente al importar el módulo
    return tasks
