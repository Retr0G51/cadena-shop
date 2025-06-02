"""
Script para crear las tablas en producción
Ejecutar solo la primera vez
"""
from app import create_app, db

app = create_app('production')

with app.app_context():
    # Crear todas las tablas
    db.create_all()
    print("✅ Tablas creadas exitosamente!")
