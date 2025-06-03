from flask import render_template
from app.main import bp
from app.models import User

@bp.route('/')
def index():
    """Página principal - Landing page"""
    featured_stores = User.query.filter_by(is_active=True).limit(6).all()
    return render_template('main/index.html', featured_stores=featured_stores)
