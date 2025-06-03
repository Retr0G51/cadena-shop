#!/usr/bin/env python
"""Script para hacer backup de la base de datos"""

import os
import sys
import subprocess
from datetime import datetime

def backup_database():
    """Crea un backup de la base de datos"""
    # Obtener DATABASE_URL
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print('Error: DATABASE_URL no está configurada')
        sys.exit(1)
    
    # Crear directorio de backups
    backup_dir = 'backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    # Nombre del archivo
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(backup_dir, f'backup_{timestamp}.sql')
    
    # Ejecutar pg_dump
    try:
        subprocess.run([
            'pg_dump',
            database_url,
            '-f', backup_file,
            '--no-owner',
            '--no-privileges'
        ], check=True)
        
        print(f'✅ Backup creado: {backup_file}')
        
        # Comprimir el archivo
        subprocess.run(['gzip', backup_file], check=True)
        print(f'✅ Backup comprimido: {backup_file}.gz')
        
    except subprocess.CalledProcessError as e:
        print(f'Error al crear backup: {e}')
        sys.exit(1)

if __name__ == '__main__':
    backup_database()
