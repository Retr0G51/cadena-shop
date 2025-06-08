"""
Blueprint del Dashboard
Maneja todas las funcionalidades del panel de administración
"""
from flask import Blueprint

bp = Blueprint('dashboard', __name__)

# Importar rutas después de crear el blueprint para evitar importaciones circulares
from app.dashboard import routes, forms, routes_extended

# Registrar rutas adicionales
from app.dashboard.routes_extended import *

__all__ = ['bp']
