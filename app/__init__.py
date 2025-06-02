import os
from flask import Flask
from config import config
from app.extensions import db, login_manager, migrate

def create_app(config_name=None):
    """Factory pattern para crear la aplicación Flask"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    
    # Crear carpeta de uploads si no existe
    upload_folder = app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    
    # Registrar Blueprints
    from app.auth import auth_bp
    from app.dashboard import dashboard_bp
    from app.public import public_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(public_bp, url_prefix='/tienda')
    
    # Ruta principal
    @app.route('/')
    def index():
        from flask import render_template
        return render_template('index.html')
    
    # Ruta de health check para Render
    @app.route('/health')
    def health():
        return 'OK', 200
    
    # Manejadores de errores
    @app.errorhandler(404)
    def not_found_error(error):
        from flask import render_template
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    # Contexto de plantillas
    @app.context_processor
    def inject_globals():
        return {
            'site_name': 'PedidosSaaS',
            'current_year': 2024
        }
    
    return app
