#!/usr/bin/env python
"""
Punto de entrada principal para la aplicación PedidosSaaS
Este archivo es para desarrollo local. En producción se usa wsgi.py
"""
import os
from app import create_app, db
from app.models import User, Product, Order

# Obtener configuración del entorno
config_name = os.environ.get('FLASK_ENV', 'development')

# Crear aplicación
app = create_app(config_name)

# Contexto de shell para depuración
@app.shell_context_processor
def make_shell_context():
    """Agregar modelos al contexto de shell para facilitar depuración"""
    return {
        'db': db,
        'User': User,
        'Product': Product,
        'Order': Order
    }

if __name__ == '__main__':
    # Configuración para desarrollo local
    port = int(os.environ.get('PORT', 5000))
    debug = config_name == 'development'
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
