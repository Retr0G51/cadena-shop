#!/usr/bin/env python
"""
Script de inicialización para configurar la base de datos
y crear datos de ejemplo para desarrollo
"""
import os
import sys
from app import create_app, db
from app.models import User, Product, Order

def init_database():
    """Inicializar la base de datos con estructura y datos de ejemplo"""
    
    # Crear aplicación
    app = create_app('development')
    
    with app.app_context():
        # Eliminar todas las tablas existentes
        print("🗑️  Eliminando tablas existentes...")
        db.drop_all()
        
        # Crear todas las tablas
        print("🔨 Creando tablas...")
        db.create_all()
        
        # Verificar si queremos datos de ejemplo
        if len(sys.argv) > 1 and sys.argv[1] == '--sample-data':
            print("📦 Creando datos de ejemplo...")
            
            # Crear usuario de ejemplo
            user = User(
                business_name="Panadería La Esquina",
                email="demo@example.com",
                phone="555-1234",
                address="Calle Principal 123",
                description="La mejor panadería artesanal de la ciudad"
            )
            user.set_password("demo123")
            db.session.add(user)
            db.session.commit()
            
            # Crear productos de ejemplo
            products = [
                Product(
                    name="Pan Francés",
                    description="Pan recién horneado cada mañana",
                    price=2.50,
                    stock=50,
                    user_id=user.id
                ),
                Product(
                    name="Croissant",
                    description="Delicioso croissant de mantequilla",
                    price=3.00,
                    stock=30,
                    user_id=user.id
                ),
                Product(
                    name="Empanada de Carne",
                    description="Empanada casera rellena de carne",
                    price=4.50,
                    stock=25,
                    user_id=user.id
                ),
                Product(
                    name="Torta de Chocolate",
                    description="Torta de chocolate con cobertura",
                    price=35.00,
                    stock=5,
                    user_id=user.id
                ),
                Product(
                    name="Galletas de Avena",
                    description="Paquete de 12 galletas de avena",
                    price=8.00,
                    stock=20,
                    user_id=user.id
                )
            ]
            
            for product in products:
                db.session.add(product)
            
            db.session.commit()
            
            print(f"✅ Usuario de ejemplo creado:")
            print(f"   Email: demo@example.com")
            print(f"   Contraseña: demo123")
            print(f"   URL de tienda: /tienda/{user.slug}")
            print(f"   Productos creados: {len(products)}")
        
        print("\n✨ Base de datos inicializada correctamente!")
        print("\n📝 Próximos pasos:")
        print("   1. Ejecuta 'python run.py' para iniciar el servidor")
        print("   2. Visita http://localhost:5000")
        print("   3. Regístrate o usa la cuenta demo si agregaste datos de ejemplo")

if __name__ == "__main__":
    print("🚀 Inicializando base de datos para PedidosSaaS...")
    print("-" * 50)
    
    # Verificar que existe el archivo .env
    if not os.path.exists('.env'):
        print("⚠️  No se encontró archivo .env")
        print("   Copia .env.example a .env y configura tus variables")
        sys.exit(1)
    
    try:
        init_database()
    except Exception as e:
        print(f"\n❌ Error al inicializar la base de datos: {str(e)}")
        print("\n💡 Asegúrate de que:")
        print("   - PostgreSQL esté corriendo")
        print("   - La base de datos exista")
        print("   - Las credenciales en .env sean correctas")
        sys.exit(1)
