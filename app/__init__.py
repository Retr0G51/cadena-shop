"""
PedidosSaaS - Sistema de Pedidos Online Multiusuario
"""

__version__ = '1.0.0'
__author__ = 'Bruno Bernal'

import os
from flask import Flask
from flask_login import current_user
from config import config
from app.extensions import db, login_manager, bcrypt, migrate

def create_app(config_name=None):
    """Factory Pattern para crear la aplicación Flask"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Inicializar extensiones
    init_extensions(app)
    
    # Registrar blueprints
    register_blueprints(app)
    
    # Crear directorios necesarios
    create_directories(app)
    
    # Configurar login manager
    configure_login_manager(app)
    
    # Registrar context processors
    register_context_processors(app)
    
    return app

def init_extensions(app):
    """Inicializa las extensiones Flask"""
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)

def register_blueprints(app):
    """Registra todos los blueprints"""
    from app.main import bp as main_bp
    from app.auth import bp as auth_bp
    from app.dashboard import bp as dashboard_bp
    from app.public import bp as public_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(public_bp, url_prefix='/tienda')

def create_directories(app):
    """Crea los directorios necesarios"""
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs('logs', exist_ok=True)

def configure_login_manager(app):
    """Configura Flask-Login"""
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))

def register_context_processors(app):
    """Registra variables globales para templates"""
    @app.context_processor
    def inject_globals():
        return {
            'current_user': current_user,
            'site_name': 'PedidosSaaS'
        }
