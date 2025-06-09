"""
Decoradores personalizados para la aplicación
"""
from functools import wraps
from flask import redirect, url_for, flash, abort
from flask_login import current_user

def business_required(f):
    """Decorador para verificar que el usuario es dueño del negocio"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Debes iniciar sesión para acceder a esta página.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def active_business_required(f):
    """Decorador para verificar que el negocio está activo"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not current_user.is_active:
            flash('Tu cuenta está desactivada. Contacta al soporte.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorador para verificar que el usuario es administrador"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Debes iniciar sesión para acceder a esta página.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Verificar si el usuario tiene permisos de admin
        if not getattr(current_user, 'is_admin', False):
            flash('No tienes permisos para acceder a esta página.', 'error')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function

def async_task(f):
    """Decorador para ejecutar tareas asíncronas con Celery"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            from app.celery import celery
            return celery.delay(f, *args, **kwargs)
        except ImportError:
            # Si Celery no está disponible, ejecutar sincrónicamente
            return f(*args, **kwargs)
    return decorated_function

def rate_limit(limit="100 per hour"):
    """Decorador para limitar tasa de peticiones"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                from app.extensions import limiter
                limiter.limit(limit)(f)
            except ImportError:
                pass  # Si limiter no está disponible, ignorar
            return f(*args, **kwargs)
        return decorated_function
    return decorator
