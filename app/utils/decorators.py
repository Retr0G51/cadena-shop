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
