from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

# Instancias de las extensiones
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

# Configuración del login manager
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
login_manager.login_message_category = 'info'
