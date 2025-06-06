#!/usr/bin/env python
"""
Script para diagnosticar y arreglar problemas comunes de despliegue
Útil para Railway, Render y otros servicios PaaS
"""
import os
import sys
import subprocess
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DeploymentFixer:
    """Clase para arreglar problemas de despliegue"""
    
    def __init__(self):
        self.root_path = Path(__file__).parent
        self.issues_found = []
        self.fixes_applied = []
    
    def check_all(self):
        """Ejecuta todas las verificaciones"""
        logger.info("="*50)
        logger.info("Verificando configuración de despliegue...")
        logger.info("="*50)
        
        self.check_environment()
        self.check_dependencies()
        self.check_database()
        self.check_file_permissions()
        self.check_static_files()
        self.check_migrations()
        self.check_config_files()
        self.check_runtime()
        
        self.show_summary()
    
    def check_environment(self):
        """Verifica variables de entorno"""
        logger.info("\n1. Verificando variables de entorno...")
        
        required_vars = [
            'DATABASE_URL',
            'SECRET_KEY',
            'FLASK_ENV'
        ]
        
        optional_vars = [
            'REDIS_URL',
            'MAIL_SERVER',
            'SENTRY_DSN',
            'AWS_ACCESS_KEY_ID'
        ]
        
        missing_required = []
        missing_optional = []
        
        for var in required_vars:
            if not os.environ.get(var):
                missing_required.append(var)
                self.issues_found.append(f"Variable requerida faltante: {var}")
        
        for var in optional_vars:
            if not os.environ.get(var):
                missing_optional.append(var)
        
        if missing_required:
            logger.error(f"✗ Variables requeridas faltantes: {', '.join(missing_required)}")
            self.create_env_template(missing_required + missing_optional)
        else:
            logger.info("✓ Todas las variables requeridas están configuradas")
        
        if missing_optional:
            logger.warning(f"⚠ Variables opcionales faltantes: {', '.join(missing_optional)}")
    
    def check_dependencies(self):
        """Verifica dependencias de Python"""
        logger.info("\n2. Verificando dependencias...")
        
        # Verificar requirements.txt
        req_file = self.root_path / 'requirements.txt'
        if not req_file.exists():
            logger.error("✗ requirements.txt no encontrado")
            self.issues_found.append("requirements.txt faltante")
            self.create_requirements()
        else:
            # Verificar dependencias instaladas
            try:
                result = subprocess.run(
                    ['pip', 'check'],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    logger.warning("⚠ Hay conflictos en las dependencias")
                    logger.warning(result.stdout)
                else:
                    logger.info("✓ Dependencias verificadas correctamente")
            except Exception as e:
                logger.error(f"✗ Error verificando dependencias: {e}")
    
    def check_database(self):
        """Verifica configuración de base de datos"""
        logger.info("\n3. Verificando base de datos...")
        
        db_url = os.environ.get('DATABASE_URL', '')
        
        if not db_url:
            logger.error("✗ DATABASE_URL no configurada")
            self.issues_found.append("DATABASE_URL no configurada")
            return
        
        # Arreglar URL de Heroku/Railway postgres
        if db_url.startswith('postgres://'):
            fixed_url = db_url.replace('postgres://', 'postgresql://', 1)
            os.environ['DATABASE_URL'] = fixed_url
            logger.info("✓ URL de base de datos corregida (postgres:// -> postgresql://)")
            self.fixes_applied.append("URL de base de datos corregida")
        
        # Verificar conexión
        try:
            from app import create_app, db
            app = create_app()
            with app.app_context():
                db.engine.execute("SELECT 1")
                logger.info("✓ Conexión a base de datos exitosa")
        except Exception as e:
            logger.error(f"✗ Error conectando a base de datos: {e}")
            self.issues_found.append(f"Error de conexión DB: {str(e)}")
    
    def check_file_permissions(self):
        """Verifica permisos de archivos"""
        logger.info("\n4. Verificando permisos de archivos...")
        
        directories_to_check = [
            'app/static/uploads',
            'app/static/uploads/products',
            'app/static/uploads/logos',
            'backups',
            'exports',
            'logs'
        ]
        
        for dir_path in directories_to_check:
            full_path = self.root_path / dir_path
            if not full_path.exists():
                full_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"✓ Directorio creado: {dir_path}")
                self.fixes_applied.append(f"Directorio creado: {dir_path}")
            
            # Crear .gitkeep si no existe
            gitkeep = full_path / '.gitkeep'
            if not gitkeep.exists():
                gitkeep.touch()
    
    def check_static_files(self):
        """Verifica archivos estáticos"""
        logger.info("\n5. Verificando archivos estáticos...")
        
        static_dirs = ['css', 'js', 'img']
        static_path = self.root_path / 'app' / 'static'
        
        for dir_name in static_dirs:
            dir_path = static_path / dir_name
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"✓ Directorio estático creado: {dir_name}")
        
        # Verificar archivos principales
        css_file = static_path / 'css' / 'style.css'
        if not css_file.exists():
            css_file.write_text("/* PedidosSaaS Styles */\n")
            logger.info("✓ Archivo style.css creado")
        
        js_file = static_path / 'js' / 'main.js'
        if not js_file.exists():
            js_file.write_text("// PedidosSaaS JavaScript\n")
            logger.info("✓ Archivo main.js creado")
    
    def check_migrations(self):
        """Verifica migraciones de base de datos"""
        logger.info("\n6. Verificando migraciones...")
        
        migrations_path = self.root_path / 'migrations'
        
        if not migrations_path.exists():
            logger.warning("⚠ Carpeta de migraciones no encontrada")
            # Inicializar migraciones
            try:
                subprocess.run(['flask', 'db', 'init'], check=True)
                logger.info("✓ Migraciones inicializadas")
                self.fixes_applied.append("Migraciones inicializadas")
            except Exception as e:
                logger.error(f"✗ Error inicializando migraciones: {e}")
    
    def check_config_files(self):
        """Verifica archivos de configuración"""
        logger.info("\n7. Verificando archivos de configuración...")
        
        config_files = {
            'Procfile': 'web: gunicorn wsgi:app',
            'runtime.txt': 'python-3.11.0',
            '.gitignore': self.get_gitignore_content(),
            'wsgi.py': self.get_wsgi_content()
        }
        
        for filename, content in config_files.items():
            file_path = self.root_path / filename
            if not file_path.exists():
                file_path.write_text(content)
                logger.info(f"✓ {filename} creado")
                self.fixes_applied.append(f"{filename} creado")
            else:
                logger.info(f"✓ {filename} existe")
    
    def check_runtime(self):
        """Verifica versión de Python"""
        logger.info("\n8. Verificando runtime...")
        
        runtime_file = self.root_path / 'runtime.txt'
        if runtime_file.exists():
            version = runtime_file.read_text().strip()
            logger.info(f"Runtime configurado: {version}")
            
            # Verificar versión actual
            current_version = f"python-{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            if version != current_version:
                logger.warning(f"⚠ Versión de runtime ({version}) difiere de la actual ({current_version})")
    
    def create_env_template(self, missing_vars):
        """Crea plantilla de variables de entorno"""
        env_example = self.root_path / '.env.example'
        
        content = """# PedidosSaaS Environment Variables
# Copy this file to .env and fill in your values

# Required
FLASK_ENV=production
SECRET_KEY=your-secret-key-here-change-this
DATABASE_URL=postgresql://user:password@localhost/dbname

# Optional but recommended
REDIS_URL=redis://localhost:6379/0
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=noreply@yourdomain.com

# Monitoring
SENTRY_DSN=

# AWS (for backups)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_S3_BUCKET=

# SMS (Twilio)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=

# Payments (Stripe)
STRIPE_PUBLIC_KEY=
STRIPE_SECRET_KEY=
"""
        
        env_example.write_text(content)
        logger.info("✓ .env.example creado con variables faltantes")
        self.fixes_applied.append(".env.example creado")
    
    def create_requirements(self):
        """Crea requirements.txt básico"""
        content = """Flask==2.3.3
Flask-SQLAlchemy==3.0.5
Flask-Login==0.6.2
Flask-WTF==1.1.1
Flask-Migrate==4.0.5
psycopg2-binary==2.9.7
gunicorn==21.2.0
python-dotenv==1.0.0
Pillow==10.0.1
redis==5.0.1
"""
        
        req_file = self.root_path / 'requirements.txt'
        req_file.write_text(content)
        logger.info("✓ requirements.txt creado")
        self.fixes_applied.append("requirements.txt creado")
    
    def get_gitignore_content(self):
        """Contenido para .gitignore"""
        return """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
.venv/

# Flask
instance/
.webassets-cache

# Database
*.db
*.sqlite

# Environment
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Project specific
app/static/uploads/*
!app/static/uploads/.gitkeep
backups/*
!backups/.gitkeep
exports/*
!exports/.gitkeep
logs/*
!logs/.gitkeep

# Testing
.coverage
htmlcov/
.pytest_cache/

# Production
*.log
"""
    
    def get_wsgi_content(self):
        """Contenido para wsgi.py"""
        return """#!/usr/bin/env python
\"\"\"
WSGI entry point for production deployment
\"\"\"
import os
from app import create_app

# Create application
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
"""
    
    def show_summary(self):
        """Muestra resumen de verificaciones"""
        logger.info("\n" + "="*50)
        logger.info("RESUMEN DE VERIFICACIÓN")
        logger.info("="*50)
        
        if self.issues_found:
            logger.warning(f"\n⚠ Problemas encontrados: {len(self.issues_found)}")
            for issue in self.issues_found:
                logger.warning(f"  - {issue}")
        else:
            logger.info("\n✓ No se encontraron problemas")
        
        if self.fixes_applied:
            logger.info(f"\n✓ Correcciones aplicadas: {len(self.fixes_applied)}")
            for fix in self.fixes_applied:
                logger.info(f"  - {fix}")
        
        logger.info("\n" + "="*50)
        
        # Recomendaciones finales
        if self.issues_found:
            logger.info("\nRECOMENDACIONES:")
            logger.info("1. Revisa y configura las variables de entorno faltantes")
            logger.info("2. Ejecuta 'python init_db.py' para inicializar la base de datos")
            logger.info("3. Ejecuta 'pip install -r requirements.txt' para instalar dependencias")
            logger.info("4. Verifica la configuración de tu servicio de hosting (Railway/Render)")

def main():
    """Función principal"""
    fixer = DeploymentFixer()
    
    # Verificar si estamos en producción
    if os.environ.get('FLASK_ENV') == 'production':
        logger.info("Ejecutando en modo PRODUCCIÓN")
    else:
        logger.info("Ejecutando en modo DESARROLLO")
    
    # Ejecutar verificaciones
    fixer.check_all()
    
    # Si hay problemas críticos, salir con código de error
    critical_issues = [
        issue for issue in fixer.issues_found 
        if 'DATABASE_URL' in issue or 'requirements.txt' in issue
    ]
    
    if critical_issues:
        logger.error("\n✗ Hay problemas críticos que deben resolverse")
        sys.exit(1)
    else:
        logger.info("\n✓ Sistema listo para despliegue")
        sys.exit(0)

if __name__ == '__main__':
    main()
