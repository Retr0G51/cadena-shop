from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from app.models import User

class RegistrationForm(FlaskForm):
    """Formulario de registro de nuevo negocio"""
    business_name = StringField('Nombre del Negocio', 
        validators=[DataRequired(), Length(min=3, max=100)])
    email = StringField('Email', 
        validators=[DataRequired(), Email()])
    password = PasswordField('Contraseña', 
        validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirmar Contraseña',
        validators=[DataRequired(), EqualTo('password', message='Las contraseñas deben coincidir')])
    phone = StringField('Teléfono', 
        validators=[DataRequired(), Length(min=8, max=20)])
    address = StringField('Dirección', 
        validators=[Length(max=200)])
    submit = SubmitField('Crear Cuenta')
    
    def validate_email(self, email):
        """Valida que el email no esté registrado"""
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Este email ya está registrado. Por favor usa otro.')

class LoginForm(FlaskForm):
    """Formulario de inicio de sesión"""
    email = StringField('Email', 
        validators=[DataRequired(), Email()])
    password = PasswordField('Contraseña', 
        validators=[DataRequired()])
    remember_me = BooleanField('Recordarme')
    submit = SubmitField('Iniciar Sesión')
