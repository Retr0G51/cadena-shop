#!/usr/bin/env python
"""
Punto de entrada principal para la aplicación PedidosSaaS
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
    # Solo en desarrollo
    if config_name == 'development':
        app.run(host='0.0.0.0', port=5000, debug=True)
    else:
        # En producción, usar gunicorn
        app.run()
