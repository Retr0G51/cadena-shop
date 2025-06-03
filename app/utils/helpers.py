"""
Funciones auxiliares y utilidades
"""
import os
import secrets
from PIL import Image
from flask import current_app
from werkzeug.utils import secure_filename

def save_picture(form_picture, folder):
    """Guarda una imagen subida y retorna el nombre del archivo"""
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(current_app.config['UPLOAD_FOLDER'], folder, picture_fn)
    
    # Crear el directorio si no existe
    os.makedirs(os.path.dirname(picture_path), exist_ok=True)
    
    # Redimensionar imagen
    output_size = (800, 800)
    img = Image.open(form_picture)
    
    # Convertir a RGB si es necesario
    if img.mode in ('RGBA', 'LA'):
        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
        rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = rgb_img
    
    img.thumbnail(output_size)
    img.save(picture_path, quality=85, optimize=True)
    
    return os.path.join(folder, picture_fn)

def delete_picture(filename, folder):
    """Elimina una imagen del servidor"""
    if filename:
        picture_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(picture_path):
            os.remove(picture_path)

def format_currency(amount, currency='CUP'):
    """Formatea un monto según la moneda"""
    if currency == 'CUP':
        return f"${amount:,.2f} CUP"
    elif currency == 'USD':
        return f"${amount:,.2f} USD"
    else:
        return f"{amount:,.2f}"
