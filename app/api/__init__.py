"""
API RESTful para PedidosSaaS
Proporciona endpoints para integración externa
"""
from flask import Blueprint

bp = Blueprint('api', __name__)

# Importar rutas después de crear el blueprint para evitar importaciones circulares
from app.api import auth, products, orders, customers, analytics, webhooks

# Registrar namespaces
from app.api.auth import api_auth
from app.api.products import api_products
from app.api.orders import api_orders
from app.api.customers import api_customers
from app.api.analytics import api_analytics

__all__ = ['bp', 'api_auth', 'api_products', 'api_orders', 'api_customers', 'api_analytics']
