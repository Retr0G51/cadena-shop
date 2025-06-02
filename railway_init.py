"""
Script de inicialización para Railway
Crea las tablas y prepara la base de datos
"""
import os
import sys
import time

print("🚂 Iniciando configuración para Railway...")

# Esperar a que la base de datos esté lista
print("⏳ Esperando conexión a la base de datos...")
time.sleep(3)

try:
    from app import create_app, db
    from app.models import User, Product, Order
    
    # Crear aplicación con contexto
    app = create_app('production')
    
    with app.app_context():
        # Intentar conectar a la DB
        try:
            # Probar conexión
            db.engine.connect()
            print("✅ Conexión a base de datos exitosa")
            
            # Crear tablas
            print("🔨 Creando tablas...")
            db.create_all()
            print("✅ Tablas creadas correctamente")
            
            # Verificar tablas
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"📊 Tablas en la base de datos: {tables}")
            
        except Exception as e:
            print(f"❌ Error con la base de datos: {e}")
            print("⚠️  La aplicación iniciará de todos modos...")
            
except Exception as e:
    print(f"❌ Error general: {e}")
    print("⚠️  Continuando con el inicio...")

print("🚀 Inicialización completa!")
