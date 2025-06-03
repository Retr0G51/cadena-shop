from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, DecimalField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

class ProductForm(FlaskForm):
    """Formulario para crear/editar productos"""
    name = StringField('Nombre del Producto', 
        validators=[DataRequired(), Length(min=3, max=100)])
    description = TextAreaField('Descripción', 
        validators=[Length(max=500)])
    price = DecimalField('Precio', 
        validators=[DataRequired(), NumberRange(min=0)], places=2)
    stock = IntegerField('Stock', 
        validators=[DataRequired(), NumberRange(min=0)])
    category = StringField('Categoría', 
        validators=[Length(max=50)])
    image = FileField('Imagen del Producto', 
        validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'], 'Solo imágenes permitidas')])
    is_active = SelectField('Estado', 
        choices=[('1', 'Activo'), ('0', 'Inactivo')], default='1')
    is_featured = SelectField('Destacado', 
        choices=[('1', 'Sí'), ('0', 'No')], default='0')
    submit = SubmitField('Guardar Producto')

class BusinessSettingsForm(FlaskForm):
    """Formulario para configuración del negocio"""
    business_name = StringField('Nombre del Negocio', 
        validators=[DataRequired(), Length(min=3, max=100)])
    description = TextAreaField('Descripción del Negocio', 
        validators=[Length(max=500)])
    phone = StringField('Teléfono', 
        validators=[DataRequired(), Length(min=8, max=20)])
    address = StringField('Dirección', 
        validators=[Length(max=200)])
    logo = FileField('Logo del Negocio', 
        validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'], 'Solo imágenes permitidas')])
    accept_orders = SelectField('Aceptar Pedidos', 
        choices=[('1', 'Sí'), ('0', 'No')], default='1')
    currency = SelectField('Moneda', 
        choices=[('CUP', 'Peso Cubano (CUP)'), ('USD', 'Dólar (USD)')], default='CUP')
    submit = SubmitField('Guardar Cambios')
