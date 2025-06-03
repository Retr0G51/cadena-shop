#!/usr/bin/env python
"""Script para crear un usuario administrador"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User

def create_admin():
    """Crea un usuario administrador"""
    app = create_app()
    
    with app.app_context():
        email = input('Email del administrador: ')
        
        # Verificar si ya existe
        if User.query.filter_by(email=email).first():
            print(f'Error: Ya existe un usuario con el email {email}')
            return
        
        business_name = input('Nombre del negocio: ')
        phone = input('Teléfono: ')
        password = input('Contraseña: ')
        
        # Crear usuario
        admin = User(
            business_name=business_name,
            email=email,
            phone=phone
        )
        admin.set_password(password)
        
        db.session.add(admin)
        db.session.commit()
        
        print(f'\n✅ Administrador creado exitosamente!')
        print(f'Email: {email}')
        print(f'URL de la tienda: /tienda/{admin.slug}')

if __name__ == '__main__':
    create_admin()
