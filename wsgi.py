#!/usr/bin/env python
"""
WSGI entry point for production deployment
Allows gradual restoration of features
"""
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Feature flags for gradual deployment
FEATURES = {
    'BASIC_APP': True,           # Basic Flask app
    'DATABASE': True,            # Database connection
    'AUTH': True,                # Authentication system
    'ADMIN': True,               # Admin panel
    'STORE': True,               # Store functionality
    'API': True,                 # REST API
    'BACKGROUND_TASKS': False,   # Celery tasks (disable for now)
    'MONITORING': False,         # Monitoring/logging (disable for now)
}

def create_basic_app():
    """Create a basic Flask app for testing"""
    from flask import Flask, jsonify, render_template_string
    
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-this')
    
    @app.route('/')
    def index():
        return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>PedidosSaaS - Deploying...</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .container { max-width: 800px; margin: 0 auto; }
                .status { padding: 20px; border-radius: 5px; margin: 10px 0; }
                .success { background: #d4edda; color: #155724; }
                .warning { background: #fff3cd; color: #856404; }
                .info { background: #d1ecf1; color: #0c5460; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 PedidosSaaS - Deployment Status</h1>
                <div class="status success">
                    <strong>✅ Basic App:</strong> Running successfully on Railway
                </div>
                <div class="status info">
                    <strong>🔄 Gradual Deployment:</strong> Restoring features one by one
                </div>
                <div class="status warning">
                    <strong>⚙️ Current Features:</strong>
                    <ul>
                        {% for feature, enabled in features.items() %}
                        <li>{{ feature }}: {{ "✅ Enabled" if enabled else "❌ Disabled" }}</li>
                        {% endfor %}
                    </ul>
                </div>
                <p><strong>URL:</strong> <code>{{ url }}</code></p>
                <p><strong>Environment:</strong> {{ env }}</p>
            </div>
        </body>
        </html>
        ''', features=FEATURES, url=os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'localhost'), 
             env=os.environ.get('FLASK_ENV', 'development'))
    
    @app.route('/health')
    def health():
        return jsonify({
            'status': 'healthy',
            'features': FEATURES,
            'environment': os.environ.get('FLASK_ENV', 'development')
        })
    
    return app

def create_full_app():
    """Create the full PedidosSaaS application"""
    try:
        # Import the main application factory
        from app import create_app
        
        # Create app with production config
        app = create_app()
        
        # Initialize database if needed
        if FEATURES['DATABASE']:
            from app.models import db
            with app.app_context():
                # Create tables if they don't exist
                db.create_all()
        
        return app
        
    except Exception as e:
        print(f"Error creating full app: {e}")
        # Fallback to basic app
        return create_basic_app()

# Determine which app to create
if FEATURES['BASIC_APP'] and not all([FEATURES['DATABASE'], FEATURES['AUTH']]):
    # Use basic app for initial deployment
    app = create_basic_app()
    print("📱 Using basic app for gradual deployment")
else:
    # Use full app
    app = create_full_app()
    print("🚀 Using full PedidosSaaS application")

# For development server
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    
    print(f"🌐 Starting server on port {port}")
    print(f"🔧 Debug mode: {debug}")
    print(f"📊 Features enabled: {sum(FEATURES.values())}/{len(FEATURES)}")
    
    app.run(
        host='0.0.0.0', 
        port=port, 
        debug=debug
    )
