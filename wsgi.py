#!/usr/bin/env python
"""
WSGI entry point para despliegue en producción
Usado por Gunicorn, uWSGI, etc.
"""
import os
from app import create_app

# Obtener configuración del entorno
config_name = os.environ.get('FLASK_ENV', 'production')

# Crear aplicación
app = create_app(config_name)

# Exponer la aplicación para WSGI
application = app

if __name__ == '__main__':
    # Solo para desarrollo/debugging
    # En producción usar: gunicorn wsgi:app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
