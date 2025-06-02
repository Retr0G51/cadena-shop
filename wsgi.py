"""
Punto de entrada WSGI para producción
Render busca este archivo específicamente
"""
import os
from app import create_app

# Crear la aplicación con configuración de producción
app = create_app(os.environ.get('FLASK_ENV', 'production'))

if __name__ == "__main__":
    app.run()
