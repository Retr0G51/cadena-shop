#!/usr/bin/env python
"""
Script principal para ejecutar PedidosSaaS en desarrollo
Uso: python run.py
"""
import os
from app import create_app, db
from app.models import User, Product, Order, OrderItem
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.inventory import Warehouse, StockItem

# Crear aplicación con configuración de desarrollo
app = create_app(os.environ.get('FLASK_ENV', 'development'))

# Contexto de shell para debugging
@app.shell_context_processor
def make_shell_context():
    """Crea el contexto para flask shell"""
    return {
        'db': db,
        'User': User,
        'Product': Product,
        'Order': Order,
        'OrderItem': OrderItem,
        'Customer': Customer,
        'Invoice': Invoice,
        'Warehouse': Warehouse,
        'StockItem': StockItem
    }

if __name__ == '__main__':
    # Verificar si la base de datos existe
    with app.app_context():
        try:
            # Intentar conectar a la base de datos
            db.engine.execute('SELECT 1')
        except Exception as e:
            print(f"Error conectando a la base de datos: {e}")
            print("Ejecuta 'python init_db.py' para crear la base de datos")
            exit(1)
    
    # Configuración para desarrollo
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print(f"""
    ╔═══════════════════════════════════════╗
    ║        PedidosSaaS v1.0.0            ║
    ╟───────────────────────────────────────╢
    ║  Ambiente: {os.environ.get('FLASK_ENV', 'development'):26} ║
    ║  Debug: {str(debug):29} ║
    ║  URL: http://localhost:{port:<15} ║
    ╚═══════════════════════════════════════╝
    
    Presiona CTRL+C para detener el servidor
    """)
    
    # Ejecutar aplicación
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        use_reloader=debug,
        use_debugger=debug
    )
