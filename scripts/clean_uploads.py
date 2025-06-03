#!/usr/bin/env python
"""Script para limpiar archivos huérfanos en uploads"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Product

def clean_orphaned_files():
    """Elimina archivos de upload que no están referenciados en la BD"""
    app = create_app()
    
    with app.app_context():
        upload_dir = app.config['UPLOAD_FOLDER']
        
        # Obtener todos los archivos referenciados
        referenced_files = set()
        
        # Logos de usuarios
        for user in User.query.filter(User.logo.isnot(None)).all():
            referenced_files.add(user.logo)
        
        # Imágenes de productos
        for product in Product.query.filter(Product.image.isnot(None)).all():
            referenced_files.add(product.image)
        
        # Buscar archivos huérfanos
        orphaned_files = []
        for root, dirs, files in os.walk(upload_dir):
            for file in files:
                if file == '.gitkeep':
                    continue
                
                relative_path = os.path.relpath(
                    os.path.join(root, file), 
                    'app/static/uploads'
                )
                
                if relative_path not in referenced_files:
                    orphaned_files.append(os.path.join(root, file))
        
        if orphaned_files:
            print(f'Encontrados {len(orphaned_files)} archivos huérfanos:')
            for file in orphaned_files:
                print(f'  - {file}')
            
            if input('\n¿Eliminar estos archivos? (s/n): ').lower() == 's':
                for file in orphaned_files:
                    os.remove(file)
                    print(f'Eliminado: {file}')
                print(f'\n✅ {len(orphaned_files)} archivos eliminados')
        else:
            print('✅ No se encontraron archivos huérfanos')

if __name__ == '__main__':
    clean_orphaned_files()
