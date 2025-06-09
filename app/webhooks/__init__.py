"""
Webhooks para PedidosSaaS
Maneja notificaciones entrantes de servicios externos
"""
from flask import Blueprint

bp = Blueprint('webhooks', __name__)

from app.webhooks import routes
