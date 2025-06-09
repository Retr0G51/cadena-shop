#!/usr/bin/env python
"""
WSGI entry point para despliegue en producción
Usado por Gunicorn, uWSGI, etc.
"""
import os
from app import create_app, db

# Obtener configuración del entorno
config_name = os.environ.get('FLASK_ENV', 'production')

# Crear aplicación
app = create_app(config_name)

# Crear tablas automáticamente en producción
if os.environ.get('FLASK_ENV') == 'production':
   with app.app_context():
       try:
           db.create_all()
           print("✅ Tables created successfully")
       except Exception as e:
           print(f"⚠️  Warning creating tables: {e}")

# Exponer la aplicación para WSGI
application = app

if __name__ == '__main__':
   # Solo para desarrollo/debugging
   # En producción usar: gunicorn wsgi:app
   port = int(os.environ.get('PORT', 5000))
   app.run(host='0.0.0.0', port=port, debug=False)
