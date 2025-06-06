#!/usr/bin/env python
"""
Script de backup automático de base de datos
Soporta backups locales y en S3
"""
import os
import sys
import subprocess
import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import logging
import json

# Configurar path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseBackup:
    """Gestor de backups de base de datos"""
    
    def __init__(self):
        self.app = create_app()
        self.config = self.app.config
        self.backup_dir = Path('backups')
        self.backup_dir.mkdir(exist_ok=True)
        
    def create_backup(self, backup_type='full'):
        """Crea un backup de la base de datos"""
        logger.info(f"Iniciando backup {backup_type}...")
        
        # Generar nombre de archivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"pedidossaas_{backup_type}_{timestamp}.sql"
        filepath = self.backup_dir / filename
        
        # Obtener URL de base de datos
        db_url = self.config.get('DATABASE_URL')
        if not db_url:
            logger.error("DATABASE_URL no configurada")
            return None
        
        # Parsear URL de base de datos
        db_params = self._parse_database_url(db_url)
        
        # Ejecutar pg_dump
        try:
            env = os.environ.copy()
            env['PGPASSWORD'] = db_params['password']
            
            cmd = [
                'pg_dump',
                '-h', db_params['host'],
                '-p', str(db_params['port']),
                '-U', db_params['user'],
                '-d', db_params['database'],
                '--no-owner',
                '--no-privileges',
                '--clean',
                '--if-exists'
            ]
            
            if backup_type == 'schema':
                cmd.append('--schema-only')
            elif backup_type == 'data':
                cmd.append('--data-only')
            
            # Ejecutar comando
            with open(filepath, 'w') as f:
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    env=env,
                    text=True
                )
            
            if result.returncode != 0:
                logger.error(f"Error en pg_dump: {result.stderr}")
                return None
            
            # Comprimir archivo
            compressed_path = self._compress_file(filepath)
            logger.info(f"✓ Backup creado: {compressed_path.name}")
            
            # Subir a S3 si está configurado
            if self.config.get('AWS_S3_BUCKET'):
                self._upload_to_s3(compressed_path)
            
            # Crear metadata
            self._create_metadata(compressed_path, db_params['database'], backup_type)
            
            return compressed_path
            
        except FileNotFoundError:
            logger.error("pg_dump no encontrado. Instala PostgreSQL client tools.")
            return None
        except Exception as e:
            logger.error(f"Error creando backup: {e}")
            return None
    
    def restore_backup(self, backup_file):
        """Restaura un backup"""
        logger.info(f"Restaurando backup: {backup_file}")
        
        # Verificar archivo
        backup_path = self.backup_dir / backup_file
        if not backup_path.exists():
            logger.error(f"Archivo no encontrado: {backup_file}")
            return False
        
        # Descomprimir si es necesario
        if backup_path.suffix == '.gz':
            sql_path = self._decompress_file(backup_path)
        else:
            sql_path = backup_path
        
        # Obtener parámetros de DB
        db_url = self.config.get('DATABASE_URL')
        db_params = self._parse_database_url(db_url)
        
        try:
            env = os.environ.copy()
            env['PGPASSWORD'] = db_params['password']
            
            cmd = [
                'psql',
                '-h', db_params['host'],
                '-p', str(db_params['port']),
                '-U', db_params['user'],
                '-d', db_params['database'],
                '-f', str(sql_path)
            ]
            
            result = subprocess.run(
                cmd,
                stderr=subprocess.PIPE,
                env=env,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Error restaurando: {result.stderr}")
                return False
            
            logger.info("✓ Backup restaurado exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"Error restaurando backup: {e}")
            return False
        finally:
            # Limpiar archivo temporal
            if sql_path != backup_path and sql_path.exists():
                sql_path.unlink()
    
    def list_backups(self):
        """Lista todos los backups disponibles"""
        backups = []
        
        # Backups locales
        for file in self.backup_dir.glob('*.gz'):
            metadata_file = file.with_suffix('.json')
            metadata = {}
            
            if metadata_file.exists():
                with open(metadata_file) as f:
                    metadata = json.load(f)
            
            backups.append({
                'filename': file.name,
                'size': file.stat().st_size,
                'created': datetime.fromtimestamp(file.stat().st_mtime),
                'type': metadata.get('type', 'unknown'),
                'database': metadata.get('database', 'unknown')
            })
        
        # Ordenar por fecha
        backups.sort(key=lambda x: x['created'], reverse=True)
        return backups
    
    def cleanup_old_backups(self, retention_days=30):
        """Elimina backups antiguos"""
        logger.info(f"Limpiando backups más antiguos de {retention_days} días...")
        
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        deleted_count = 0
        
        for file in self.backup_dir.glob('*.gz'):
            file_date = datetime.fromtimestamp(file.stat().st_mtime)
            
            if file_date < cutoff_date:
                # Eliminar archivo y metadata
                file.unlink()
                metadata_file = file.with_suffix('.json')
                if metadata_file.exists():
                    metadata_file.unlink()
                
                deleted_count += 1
                logger.info(f"Eliminado: {file.name}")
        
        logger.info(f"✓ {deleted_count} backups antiguos eliminados")
    
    def verify_backup(self, backup_file):
        """Verifica integridad de un backup"""
        backup_path = self.backup_dir / backup_file
        
        if not backup_path.exists():
            logger.error(f"Archivo no encontrado: {backup_file}")
            return False
        
        try:
            # Verificar que se puede descomprimir
            with gzip.open(backup_path, 'rb') as f:
                # Leer primeros bytes para verificar
                header = f.read(100).decode('utf-8', errors='ignore')
                if 'PostgreSQL database dump' not in header:
                    logger.error("El archivo no parece ser un dump válido de PostgreSQL")
                    return False
            
            logger.info(f"✓ Backup verificado: {backup_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error verificando backup: {e}")
            return False
    
    def _parse_database_url(self, url):
        """Parsea DATABASE_URL al formato de psycopg2"""
        # postgresql://user:password@host:port/database
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        
        return {
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 5432,
            'user': parsed.username or 'postgres',
            'password': parsed.password or '',
            'database': parsed.path.lstrip('/') if parsed.path else 'pedidossaas'
        }
    
    def _compress_file(self, filepath):
        """Comprime un archivo con gzip"""
        compressed_path = filepath.with_suffix('.sql.gz')
        
        with open(filepath, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Eliminar archivo original
        filepath.unlink()
        
        return compressed_path
    
    def _decompress_file(self, filepath):
        """Descomprime un archivo gzip"""
        sql_path = filepath.with_suffix('')
        
        with gzip.open(filepath, 'rb') as f_in:
            with open(sql_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        return sql_path
    
    def _create_metadata(self, backup_path, database, backup_type):
        """Crea archivo de metadata para el backup"""
        metadata = {
            'filename': backup_path.name,
            'database': database,
            'type': backup_type,
            'created': datetime.now().isoformat(),
            'size': backup_path.stat().st_size,
            'app_version': self.config.get('APP_VERSION', '1.0.0'),
            'compressed': True
        }
        
        metadata_path = backup_path.with_suffix('.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def _upload_to_s3(self, filepath):
        """Sube backup a S3"""
        try:
            import boto3
            
            s3_client = boto3.client(
                's3',
                aws_access_key_id=self.config.get('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=self.config.get('AWS_SECRET_ACCESS_KEY'),
                region_name=self.config.get('AWS_S3_REGION', 'us-east-1')
            )
            
            bucket = self.config.get('AWS_S3_BUCKET')
            key = f"backups/{filepath.name}"
            
            s3_client.upload_file(
                str(filepath),
                bucket,
                key,
                ExtraArgs={
                    'ServerSideEncryption': 'AES256',
                    'StorageClass': 'STANDARD_IA'
                }
            )
            
            logger.info(f"✓ Backup subido a S3: s3://{bucket}/{key}")
            
        except Exception as e:
            logger.error(f"Error subiendo a S3: {e}")

def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Gestión de backups de base de datos')
    parser.add_argument('action', choices=['create', 'restore', 'list', 'cleanup', 'verify'],
                       help='Acción a realizar')
    parser.add_argument('--type', choices=['full', 'schema', 'data'], default='full',
                       help='Tipo de backup (solo para create)')
    parser.add_argument('--file', help='Archivo de backup (para restore/verify)')
    parser.add_argument('--days', type=int, default=30,
                       help='Días de retención (para cleanup)')
    
    args = parser.parse_args()
    
    backup = DatabaseBackup()
    
    if args.action == 'create':
        result = backup.create_backup(args.type)
        if result:
            logger.info(f"Backup completado: {result}")
        else:
            sys.exit(1)
    
    elif args.action == 'restore':
        if not args.file:
            logger.error("Especifica el archivo con --file")
            sys.exit(1)
        
        if backup.restore_backup(args.file):
            logger.info("Restauración completada")
        else:
            sys.exit(1)
    
    elif args.action == 'list':
        backups = backup.list_backups()
        
        if not backups:
            logger.info("No hay backups disponibles")
        else:
            logger.info(f"\nBackups disponibles ({len(backups)}):")
            logger.info("-" * 80)
            
            for b in backups:
                size_mb = b['size'] / (1024 * 1024)
                logger.info(
                    f"{b['filename']:<40} "
                    f"{b['type']:<10} "
                    f"{size_mb:>8.2f} MB  "
                    f"{b['created'].strftime('%Y-%m-%d %H:%M')}"
                )
    
    elif args.action == 'cleanup':
        backup.cleanup_old_backups(args.days)
    
    elif args.action == 'verify':
        if not args.file:
            logger.error("Especifica el archivo con --file")
            sys.exit(1)
        
        if backup.verify_backup(args.file):
            logger.info("Backup válido")
        else:
            sys.exit(1)

if __name__ == '__main__':
    main()
