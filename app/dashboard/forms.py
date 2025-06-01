from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, DecimalField, IntegerField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

class ProductForm(FlaskForm):
    """Formulario para crear/editar productos"""
    name = StringField('Nombre del Producto', 
        validators=[DataRequired(), Length(min=2, max=100)])
    
    description = TextAreaField('Descripción', 
        validators=[Length(max=500)])
    
    price = DecimalField('Precio', 
        validators=[DataRequired(), NumberRange(min=0.01)],
        places=2)
    
    stock = IntegerField('Stock', 
        validators=[DataRequired(), NumberRange(min=0)],
        default=0)
    
    image = FileField('Imagen del Producto', 
        validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'], 
                                          'Solo se permiten imágenes')])
    
    submit = SubmitField('Guardar Producto')

class OrderStatusForm(FlaskForm):
    """Formulario para actualizar el estado de un pedido"""
    status = SelectField('Estado del Pedido', 
        choices=[
            ('pending', 'Pendiente'),
            ('confirmed', 'Confirmado'),
            ('preparing', 'En preparación'),
            ('ready', 'Listo'),
            ('delivered', 'Entregado'),
            ('cancelled', 'Cancelado')
        ])
    
    submit = SubmitField('Actualizar Estado')
