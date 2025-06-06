#!/usr/bin/env python
"""
Script para limpiar archivos huérfanos y temporales
Mantiene el sistema limpio y optimizado
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import logging
import shutil

# Configurar path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Product, User
from app.models.invoice import Invoice
from app.models.customer import Customer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileCleanup:
    """Gestor de limpieza de archivos"""
    
    def __init__(self):
        self.app = create_app()
        self.base_path = Path('app/static/uploads')
        self.temp_path = Path('temp')
        self.export_path = Path('exports')
        self.log_path = Path('logs')
        
        self.stats = {
            'files_checked': 0,
            'files_deleted': 0,
            'space_freed': 0,
            'orphaned_files': 0,
            'temp_files': 0,
            'old_exports': 0,
            'old_logs': 0
        }
    
    def run_cleanup(self, dry_run=False):
        """Ejecuta limpieza completa"""
        logger.info("="*50)
        logger.info(f"Iniciando limpieza de archivos {'(DRY RUN)' if dry_run else ''}")
        logger.info("="*50)
        
        with self.app.app_context():
            # 1. Limpiar imágenes huérfanas
            self.clean_orphaned_images(dry_run)
            
            # 2. Limpiar archivos temporales
            self.clean_temp_files(dry_run)
            
            # 3. Limpiar exportaciones antiguas
            self.clean_old_exports(dry_run)
            
            # 4. Limpiar logs antiguos
            self.clean_old_logs(dry_run)
            
            # 5. Limpiar miniaturas no usadas
            self.clean_unused_thumbnails(dry_run)
            
            # 6. Optimizar almacenamiento
            self.optimize_storage(dry_run)
        
        self.show_summary()
    
    def clean_orphaned_images(self, dry_run=False):
        """Elimina imágenes que no están asociadas a ningún producto"""
        logger.info("\n1. Limpiando imágenes huérfanas...")
        
        # Obtener todas las imágenes de productos activos
        active_images = set()
        products = Product.query.filter(Product.image_url.isnot(None)).all()
        
        for product in products:
            if product.image_url:
                # Extraer nombre de archivo de la URL
                filename = os.path.basename(product.image_url)
                active_images.add(filename)
        
        # Verificar archivos en disco
        product_dirs = ['products/thumb', 'products/small', 'products/medium', 'products']
        
        for dir_name in product_dirs:
            dir_path = self.base_path / dir_name
            if not dir_path.exists():
                continue
            
            for file_path in dir_path.glob('*'):
                if file_path.is_file() and file_path.name != '.gitkeep':
                    self.stats['files_checked'] += 1
                    
                    if file_path.name not in active_images:
                        self.stats['orphaned_files'] += 1
                        file_size = file_path.stat().st_size
                        
                        if not dry_run:
                            file_path.unlink()
                            self.stats['files_deleted'] += 1
                            self.stats['space_freed'] += file_size
                            logger.debug(f"Eliminado: {file_path}")
                        else:
                            logger.debug(f"[DRY RUN] Eliminaría: {file_path}")
        
        logger.info(f"✓ {self.stats['orphaned_files']} imágenes huérfanas encontradas")
    
    def clean_temp_files(self, dry_run=False):
        """Elimina archivos temporales antiguos"""
        logger.info("\n2. Limpiando archivos temporales...")
        
        if not self.temp_path.exists():
            return
        
        cutoff_date = datetime.now() - timedelta(hours=24)
        
        for file_path in self.temp_path.rglob('*'):
            if file_path.is_file():
                self.stats['files_checked'] += 1
                
                file_date = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                if file_date < cutoff_date:
                    self.stats['temp_files'] += 1
                    file_size = file_path.stat().st_size
                    
                    if not dry_run:
                        file_path.unlink()
                        self.stats['files_deleted'] += 1
                        self.stats['space_freed'] += file_size
                        logger.debug(f"Eliminado temp: {file_path}")
                    else:
                        logger.debug(f"[DRY RUN] Eliminaría temp: {file_path}")
        
        logger.info(f"✓ {self.stats['temp_files']} archivos temporales encontrados")
    
    def clean_old_exports(self, dry_run=False):
        """Elimina exportaciones antiguas"""
        logger.info("\n3. Limpiando exportaciones antiguas...")
        
        if not self.export_path.exists():
            return
        
        # Mantener exportaciones de los últimos 7 días
        cutoff_date = datetime.now() - timedelta(days=7)
        
        for file_path in self.export_path.glob('*'):
            if file_path.is_file() and file_path.name != '.gitkeep':
                self.stats['files_checked'] += 1
                
                file_date = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                if file_date < cutoff_date:
                    self.stats['old_exports'] += 1
                    file_size = file_path.stat().st_size
                    
                    if not dry_run:
                        file_path.unlink()
                        self.stats['files_deleted'] += 1
                        self.stats['space_freed'] += file_size
                        logger.debug(f"Eliminado export: {file_path}")
                    else:
                        logger.debug(f"[DRY RUN] Eliminaría export: {file_path}")
        
        logger.info(f"✓ {self.stats['old_exports']} exportaciones antiguas encontradas")
    
    def clean_old_logs(self, dry_run=False):
        """Limpia logs antiguos manteniendo los recientes"""
        logger.info("\n4. Limpiando logs antiguos...")
        
        if not self.log_path.exists():
            return
        
        # Mantener logs de los últimos 30 días
        cutoff_date = datetime.now() - timedelta(days=30)
        
        for file_path in self.log_path.glob('*.log*'):
            if file_path.is_file():
                self.stats['files_checked'] += 1
                
                file_date = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                if file_date < cutoff_date and '.log.' in file_path.name:
                    self.stats['old_logs'] += 1
                    file_size = file_path.stat().st_size
                    
                    if not dry_run:
                        file_path.unlink()
                        self.stats['files_deleted'] += 1
                        self.stats['space_freed'] += file_size
                        logger.debug(f"Eliminado log: {file_path}")
                    else:
                        logger.debug(f"[DRY RUN] Eliminaría log: {file_path}")
        
        logger.info(f"✓ {self.stats['old_logs']} logs antiguos encontrados")
    
    def clean_unused_thumbnails(self, dry_run=False):
        """Elimina miniaturas sin imagen original"""
        logger.info("\n5. Limpiando miniaturas no usadas...")
        
        original_images = set()
        original_path = self.base_path / 'products'
        
        if original_path.exists():
            for file_path in original_path.glob('*'):
                if file_path.is_file() and file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']:
                    original_images.add(file_path.stem)
        
        # Verificar miniaturas
        thumb_dirs = ['products/thumb', 'products/small', 'products/medium']
        orphaned_thumbs = 0
        
        for dir_name in thumb_dirs:
            dir_path = self.base_path / dir_name
            if not dir_path.exists():
                continue
            
            for file_path in dir_path.glob('*'):
                if file_path.is_file() and file_path.name != '.gitkeep':
                    if file_path.stem not in original_images:
                        orphaned_thumbs += 1
                        file_size = file_path.stat().st_size
                        
                        if not dry_run:
                            file_path.unlink()
                            self.stats['files_deleted'] += 1
                            self.stats['space_freed'] += file_size
                            logger.debug(f"Eliminada miniatura: {file_path}")
                        else:
                            logger.debug(f"[DRY RUN] Eliminaría miniatura: {file_path}")
        
        logger.info(f"✓ {orphaned_thumbs} miniaturas huérfanas encontradas")
    
    def optimize_storage(self, dry_run=False):
        """Optimiza el almacenamiento comprimiendo imágenes grandes"""
        logger.info("\n6. Optimizando almacenamiento...")
        
        from PIL import Image
        
        optimized_count = 0
        space_saved = 0
        
        # Solo optimizar imágenes originales
        original_path = self.base_path / 'products'
        
        if original_path.exists():
            for file_path in original_path.glob('*'):
                if file_path.is_file() and file_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                    try:
                        # Verificar tamaño
                        file_size = file_path.stat().st_size
                        
                        # Si es mayor a 1MB, optimizar
                        if file_size > 1024 * 1024:
                            if not dry_run:
                                # Abrir y recomprimir
                                img = Image.open(file_path)
                                
                                # Convertir a RGB si es necesario
                                if img.mode in ('RGBA', 'LA'):
                                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                                    rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                                    img = rgb_img
                                
                                # Guardar con compresión optimizada
                                img.save(file_path, 'JPEG', quality=85, optimize=True)
                                
                                new_size = file_path.stat().st_size
                                saved = file_size - new_size
                                
                                if saved > 0:
                                    space_saved += saved
                                    optimized_count += 1
                                    logger.debug(f"Optimizada: {file_path} ({saved/1024:.1f} KB ahorrados)")
                            else:
                                logger.debug(f"[DRY RUN] Optimizaría: {file_path}")
                                optimized_count += 1
                    
                    except Exception as e:
                        logger.warning(f"Error optimizando {file_path}: {e}")
        
        self.stats['space_freed'] += space_saved
        logger.info(f"✓ {optimized_count} imágenes optimizadas")
    
    def check_disk_usage(self):
        """Verifica el uso de disco"""
        total_size = 0
        file_count = 0
        
        paths_to_check = [
            self.base_path,
            self.temp_path,
            self.export_path,
            self.log_path,
            Path('backups')
        ]
        
        for path in paths_to_check:
            if path.exists():
                for file_path in path.rglob('*'):
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
                        file_count += 1
        
        return {
            'total_files': file_count,
            'total_size': total_size,
            'total_size_mb': total_size / (1024 * 1024)
        }
    
    def show_summary(self):
        """Muestra resumen de la limpieza"""
        logger.info("\n" + "="*50)
        logger.info("RESUMEN DE LIMPIEZA")
        logger.info("="*50)
        
        logger.info(f"Archivos verificados: {self.stats['files_checked']}")
        logger.info(f"Archivos eliminados: {self.stats['files_deleted']}")
        logger.info(f"Espacio liberado: {self.stats['space_freed'] / (1024*1024):.2f} MB")
        
        logger.info("\nDetalles:")
        logger.info(f"- Imágenes huérfanas: {self.stats['orphaned_files']}")
        logger.info(f"- Archivos temporales: {self.stats['temp_files']}")
        logger.info(f"- Exportaciones antiguas: {self.stats['old_exports']}")
        logger.info(f"- Logs antiguos: {self.stats['old_logs']}")
        
        # Mostrar uso actual
        disk_usage = self.check_disk_usage()
        logger.info(f"\nUso de disco actual:")
        logger.info(f"- Total de archivos: {disk_usage['total_files']}")
        logger.info(f"- Espacio usado: {disk_usage['total_size_mb']:.2f} MB")

def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Limpieza de archivos del sistema')
    parser.add_argument('--dry-run', action='store_true',
                       help='Simula la limpieza sin eliminar archivos')
    parser.add_argument('--check-only', action='store_true',
                       help='Solo verificar uso de disco')
    
    args = parser.parse_args()
    
    cleanup = FileCleanup()
    
    if args.check_only:
        disk_usage = cleanup.check_disk_usage()
        logger.info("Uso de disco actual:")
        logger.info(f"- Total de archivos: {disk_usage['total_files']}")
        logger.info(f"- Espacio usado: {disk_usage['total_size_mb']:.2f} MB")
    else:
        cleanup.run_cleanup(dry_run=args.dry_run)

if __name__ == '__main__':
    main()
