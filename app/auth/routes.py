from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from app.auth import auth_bp
from app.auth.forms import RegistrationForm, LoginForm
from app.models import User
from app.extensions import db

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registro de nuevos negocios"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        # Crear nuevo usuario
        user = User(
            business_name=form.business_name.data,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            description=form.description.data
        )
        user.set_password(form.password.data)
        
        try:
            db.session.add(user)
            db.session.commit()
            flash('¡Cuenta creada exitosamente! Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash('Error al crear la cuenta. Por favor intenta nuevamente.', 'danger')
    
    return render_template('auth/register.html', form=form)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Inicio de sesión"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user and user.check_password(form.password.data):
            if user.is_active:
                login_user(user, remember=True)
                next_page = request.args.get('next')
                flash(f'¡Bienvenido {user.business_name}!', 'success')
                return redirect(next_page) if next_page else redirect(url_for('dashboard.index'))
            else:
                flash('Tu cuenta está desactivada. Contacta al soporte.', 'warning')
        else:
            flash('Email o contraseña incorrectos.', 'danger')
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
def logout():
    """Cerrar sesión"""
    logout_user()
    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('index'))
