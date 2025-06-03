# run.py
import os
from app import create_app, db
from app.models import User, Product, Order, OrderItem

# Crear la aplicación
app = create_app(os.environ.get('FLASK_ENV', 'development'))

@app.shell_context_processor
def make_shell_context():
    """Contexto para flask shell"""
    return {
        'db': db,
        'User': User,
        'Product': Product,
        'Order': Order,
        'OrderItem': OrderItem
    }

@app.cli.command()
def init_db():
    """Inicializar la base de datos"""
    db.create_all()
    print("Base de datos inicializada!")

@app.cli.command()
def create_demo():
    """Crear datos de demostración"""
    # Verificar si ya existe un usuario demo
    if User.query.filter_by(email='demo@example.com').first():
        print("Los datos de demostración ya existen!")
        return
    
    # Crear usuario demo
    demo_user = User(
        business_name='Panadería La Esquina',
        email='demo@example.com',
        phone='+53 5555-5555',
        address='Calle 23 #456, Vedado, La Habana',
        description='La mejor panadería del barrio. Pan fresco todos los días.'
    )
    demo_user.set_password('demo123')
    db.session.add(demo_user)
    db.session.commit()
    
    # Crear productos demo
    products = [
        {
            'name': 'Pan de Flauta',
            'description': 'Pan fresco recién horneado',
            'price': 5.00,
            'stock': 50,
            'category': 'Panes',
            'is_featured': True
        },
        {
            'name': 'Cake de Chocolate',
            'description': 'Delicioso cake de chocolate con cobertura',
            'price': 25.00,
            'stock': 10,
            'category': 'Dulces',
            'is_featured': True
        },
        {
            'name': 'Croquetas (10 unidades)',
            'description': 'Croquetas caseras de jamón',
            'price': 15.00,
            'stock': 30,
            'category': 'Salados'
        },
        {
            'name': 'Pizza Personal',
            'description': 'Pizza personal con jamón y queso',
            'price': 20.00,
            'stock': 20,
            'category': 'Pizzas'
        },
        {
            'name': 'Refresco Natural',
            'description': 'Jugo natural de frutas tropicales',
            'price': 8.00,
            'stock': 25,
            'category': 'Bebidas'
        },
        {
            'name': 'Pastelitos de Guayaba',
            'description': 'Tradicionales pastelitos rellenos de guayaba',
            'price': 10.00,
            'stock': 40,
            'category': 'Dulces'
        }
    ]
    
    for product_data in products:
        product = Product(user_id=demo_user.id, **product_data)
        db.session.add(product)
    
    db.session.commit()
    
    print(f"Datos de demostración creados!")
    print(f"Email: demo@example.com")
    print(f"Contraseña: demo123")
    print(f"URL de la tienda: /tienda/{demo_user.slug}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
