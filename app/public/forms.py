from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Email, Length, Optional

class OrderForm(FlaskForm):
    """Formulario para que los clientes realicen pedidos"""
    customer_name = StringField('Nombre Completo', 
        validators=[DataRequired(), Length(min=3, max=100)])
    
    customer_email = StringField('Email (opcional)', 
        validators=[Optional(), Email()])
    
    customer_phone = StringField('Teléfono', 
        validators=[DataRequired(), Length(min=8, max=20)])
    
    delivery_address = TextAreaField('Dirección de Entrega', 
        validators=[DataRequired(), Length(min=10, max=300)])
    
    notes = TextAreaField('Notas adicionales (opcional)', 
        validators=[Length(max=500)])
    
    # Campo oculto para productos seleccionados (se llenará con JavaScript)
    products_data = HiddenField('products_data')
    
    submit = SubmitField('Realizar Pedido')
