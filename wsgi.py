"""
Punto de entrada WSGI para Railway/Producción
"""
from app import create_app
import os

# Crear aplicación Flask
app = create_app(os.environ.get('FLASK_ENV', 'production'))

if __name__ == "__main__":
    app.run()
