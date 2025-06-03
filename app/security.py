"""Configuraciones y utilidades de seguridad"""

from flask import current_app
from functools import wraps
import re

# Configuración de headers de seguridad
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'Content-Security-Policy': "default-src 'self' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https:; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com;"
}

def init_security(app):
    """Inicializa configuraciones de seguridad"""
    
    @app.after_request
    def set_security_headers(response):
        """Agrega headers de seguridad a cada respuesta"""
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response
    
    @app.before_request
    def limit_content_length():
        """Limita el tamaño del contenido de las solicitudes"""
        max_length = app.config.get('MAX_CONTENT_LENGTH')
        if max_length and request.content_length and request.content_length > max_length:
            abort(413)

def validate_email(email):
    """Valida formato de email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Valida formato de teléfono"""
    # Acepta formatos como: +53 5555-5555, 5555-5555, etc.
    pattern = r'^[\+]?[(]?[0-9]{2,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{3,4}[-\s\.]?[0-9]{3,4}$'
    return re.match(pattern, phone) is not None

def sanitize_filename(filename):
    """Sanitiza nombres de archivo"""
    # Remueve caracteres peligrosos
    filename = re.sub(r'[^\w\s.-]', '', filename)
    # Remueve espacios múltiples
    filename = re.sub(r'\s+', '-', filename)
    return filename.lower()
