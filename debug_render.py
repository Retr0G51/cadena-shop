"""
Script de depuración para Render
Ayuda a identificar problemas de configuración
"""
import os
import sys

print("=== DEBUG RENDER ===")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Directory contents: {os.listdir('.')}")
print(f"\nEnvironment variables:")
print(f"FLASK_ENV: {os.environ.get('FLASK_ENV', 'NOT SET')}")
print(f"DATABASE_URL exists: {'DATABASE_URL' in os.environ}")
print(f"SECRET_KEY exists: {'SECRET_KEY' in os.environ}")
print(f"PORT: {os.environ.get('PORT', 'NOT SET')}")

try:
    from app import create_app
    print("\n✅ App imports correctly")
    
    app = create_app()
    print("✅ App creates successfully")
    
    with app.app_context():
        from app.extensions import db
        from app.models import User
        
        # Intentar conectar a la base de datos
        try:
            db.engine.connect()
            print("✅ Database connection successful")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
