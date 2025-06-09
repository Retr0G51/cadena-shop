"""
Funciones de ayuda para PedidosSaaS
Utilidades comunes usadas en toda la aplicación
"""
import os
import re
import unicodedata
from datetime import datetime, timedelta
from decimal import Decimal
import csv
import io
import xlsxwriter
from flask import current_app, send_file
import phonenumbers
from typing import Optional, Dict, List, Tuple, Any
import requests
import hashlib
import string
import random

def format_currency(amount: Decimal, currency: str = 'MXN', locale: str = 'es_MX') -> str:
    """
    Formatea un monto como moneda
    
    Args:
        amount: Monto a formatear
        currency: Código de moneda (MXN, USD, EUR, etc.)
        locale: Locale para formato
    
    Returns:
        String formateado como moneda
    """
    if currency == 'MXN':
        return f"${amount:,.2f}"
    elif currency == 'USD':
        return f"US${amount:,.2f}"
    elif currency == 'EUR':
        return f"€{amount:,.2f}"
    else:
        return f"{currency} {amount:,.2f}"

def format_phone(phone: str, country: str = 'MX') -> str:
    """
    Formatea un número de teléfono según el país
    
    Args:
        phone: Número de teléfono
        country: Código de país ISO
    
    Returns:
        Número formateado o el original si no se puede parsear
    """
    try:
        parsed = phonenumbers.parse(phone, country)
        if country == 'MX':
            # Formato mexicano: +52 55 1234 5678
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        else:
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except:
        return phone

def generate_slug(text: str) -> str:
    """
    Genera un slug URL-friendly desde un texto
    
    Args:
        text: Texto a convertir
    
    Returns:
        Slug generado
    """
    # Normalizar texto
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    
    # Convertir a minúsculas y reemplazar espacios
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    
    # Eliminar guiones al inicio y final
    text = text.strip('-')
    
    return text

def sanitize_filename(filename: str) -> str:
    """
    Sanitiza un nombre de archivo para hacerlo seguro
    
    Args:
        filename: Nombre de archivo original
    
    Returns:
        Nombre de archivo sanitizado
    """
    # Obtener nombre y extensión
    name, ext = os.path.splitext(filename)
    
    # Sanitizar nombre
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'[-\s]+', '-', name)
    
    # Limitar longitud
    name = name[:50]
    
    # Agregar timestamp para unicidad
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    
    return f"{name}_{timestamp}{ext}"

def paginate_query(query, page: int = 1, per_page: int = 20, max_per_page: int = 100):
    """
    Pagina una query de SQLAlchemy
    
    Args:
        query: Query de SQLAlchemy
        page: Número de página
        per_page: Items por página
        max_per_page: Máximo de items permitidos
    
    Returns:
        Objeto de paginación
    """
    # Validar parámetros
    page = max(1, page)
    per_page = min(max(1, per_page), max_per_page)
    
    return query.paginate(page=page, per_page=per_page, error_out=False)

def export_to_csv(data: List[Dict], filename: str = 'export.csv', 
                  columns: Optional[List[str]] = None) -> io.BytesIO:
    """
    Exporta datos a CSV
    
    Args:
        data: Lista de diccionarios con los datos
        filename: Nombre del archivo
        columns: Columnas a incluir (None = todas)
    
    Returns:
        BytesIO con el archivo CSV
    """
    output = io.StringIO()
    
    if not data:
        return io.BytesIO()
    
    # Determinar columnas
    if not columns:
        columns = list(data[0].keys())
    
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(data)
    
    # Convertir a bytes
    output.seek(0)
    return io.BytesIO(output.getvalue().encode('utf-8-sig'))

def export_to_excel(data: List[Dict], filename: str = 'export.xlsx',
                    sheets: Optional[Dict[str, List[Dict]]] = None) -> io.BytesIO:
    """
    Exporta datos a Excel
    
    Args:
        data: Lista de diccionarios para una hoja
        filename: Nombre del archivo
        sheets: Diccionario con múltiples hojas {nombre: datos}
    
    Returns:
        BytesIO con el archivo Excel
    """
    output = io.BytesIO()
    
    with xlsxwriter.Workbook(output, {'in_memory': True}) as workbook:
        # Formato para encabezados
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4e73df',
            'font_color': 'white',
            'border': 1
        })
        
        # Formato para moneda
        currency_format = workbook.add_format({'num_format': '$#,##0.00'})
        
        # Si se proporcionan múltiples hojas
        if sheets:
            for sheet_name, sheet_data in sheets.items():
                _write_excel_sheet(workbook, sheet_name, sheet_data, 
                                 header_format, currency_format)
        else:
            # Una sola hoja
            _write_excel_sheet(workbook, 'Datos', data, 
                             header_format, currency_format)
    
    output.seek(0)
    return output

def _write_excel_sheet(workbook, sheet_name: str, data: List[Dict],
                      header_format, currency_format):
    """Helper para escribir una hoja de Excel"""
    if not data:
        return
    
    worksheet = workbook.add_worksheet(sheet_name)
    
    # Escribir encabezados
    columns = list(data[0].keys())
    for col, header in enumerate(columns):
        worksheet.write(0, col, header, header_format)
    
    # Escribir datos
    for row, item in enumerate(data, 1):
        for col, key in enumerate(columns):
            value = item.get(key, '')
            
            # Aplicar formato según tipo
            if isinstance(value, (int, float, Decimal)):
                if 'price' in key or 'total' in key or 'amount' in key:
                    worksheet.write(row, col, float(value), currency_format)
                else:
                    worksheet.write(row, col, float(value))
            elif isinstance(value, datetime):
                worksheet.write(row, col, value.strftime('%d/%m/%Y %H:%M'))
            else:
                worksheet.write(row, col, str(value))
    
    # Ajustar ancho de columnas
    for col in range(len(columns)):
        worksheet.set_column(col, col, 15)

def send_sms(phone: str, message: str) -> bool:
    """
    Envía un SMS usando Twilio
    
    Args:
        phone: Número de teléfono
        message: Mensaje a enviar
    
    Returns:
        True si se envió exitosamente
    """
    try:
        # Verificar si Twilio está configurado
        account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
        auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
        from_number = current_app.config.get('TWILIO_PHONE_NUMBER')
        
        if not all([account_sid, auth_token, from_number]):
            current_app.logger.warning("Twilio no configurado")
            return False
        
        from twilio.rest import Client
        
        client = Client(account_sid, auth_token)
        
        message = client.messages.create(
            body=message,
            from_=from_number,
            to=phone
        )
        
        current_app.logger.info(f"SMS enviado: {message.sid}")
        return True
        
    except Exception as e:
        current_app.logger.error(f"Error enviando SMS: {e}")
        return False

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula la distancia entre dos coordenadas usando la fórmula de Haversine
    
    Args:
        lat1, lon1: Coordenadas del punto 1
        lat2, lon2: Coordenadas del punto 2
    
    Returns:
        Distancia en kilómetros
    """
    from math import radians, sin, cos, sqrt, atan2
    
    # Radio de la Tierra en kilómetros
    R = 6371.0
    
    # Convertir a radianes
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Diferencias
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    # Fórmula de Haversine
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c

def parse_date_range(date_range: str) -> Tuple[datetime, datetime]:
    """
    Parsea un string de rango de fechas
    
    Args:
        date_range: String como 'today', 'week', 'month', 'custom:2024-01-01,2024-01-31'
    
    Returns:
        Tupla (fecha_inicio, fecha_fin)
    """
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if date_range == 'today':
        return today, now
    
    elif date_range == 'yesterday':
        yesterday = today - timedelta(days=1)
        return yesterday, today
    
    elif date_range == 'week':
        week_start = today - timedelta(days=today.weekday())
        return week_start, now
    
    elif date_range == 'month':
        month_start = today.replace(day=1)
        return month_start, now
    
    elif date_range == 'quarter':
        quarter = (now.month - 1) // 3
        quarter_start = datetime(now.year, quarter * 3 + 1, 1)
        return quarter_start, now
    
    elif date_range == 'year':
        year_start = today.replace(month=1, day=1)
        return year_start, now
    
    elif date_range.startswith('last_'):
        # last_7_days, last_30_days, etc.
        days = int(date_range.split('_')[1])
        return today - timedelta(days=days), now
    
    elif date_range.startswith('custom:'):
        # custom:2024-01-01,2024-01-31
        dates = date_range.replace('custom:', '').split(',')
        start = datetime.strptime(dates[0], '%Y-%m-%d')
        end = datetime.strptime(dates[1], '%Y-%m-%d')
        return start, end.replace(hour=23, minute=59, second=59)
    
    else:
        # Por defecto, últimos 30 días
        return today - timedelta(days=30), now

def generate_order_number(prefix: str = 'ORD') -> str:
    """
    Genera un número de orden único
    
    Args:
        prefix: Prefijo del número
    
    Returns:
        Número de orden generado
    """
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    random_suffix = ''.join(random.choices(string.digits, k=4))
    return f"{prefix}-{timestamp}-{random_suffix}"

def generate_invoice_number(series: str = 'A', current: int = 0) -> str:
    """
    Genera un número de factura
    
    Args:
        series: Serie de facturación
        current: Número actual
    
    Returns:
        Número de factura
    """
    year = datetime.utcnow().year
    number = current + 1
    return f"{series}{year}/{number:06d}"

def calculate_tax(amount: Decimal, tax_rate: Decimal) -> Dict[str, Decimal]:
    """
    Calcula impuestos
    
    Args:
        amount: Monto base
        tax_rate: Tasa de impuesto (porcentaje)
    
    Returns:
        Diccionario con base, impuesto y total
    """
    tax_amount = amount * (tax_rate / 100)
    total = amount + tax_amount
    
    return {
        'base': amount,
        'tax': tax_amount,
        'total': total,
        'rate': tax_rate
    }

def get_client_ip(request) -> str:
    """
    Obtiene la IP real del cliente
    
    Args:
        request: Objeto request de Flask
    
    Returns:
        IP del cliente
    """
    # Verificar headers de proxy
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        return request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0]
    elif request.environ.get('HTTP_X_REAL_IP'):
        return request.environ['HTTP_X_REAL_IP']
    else:
        return request.environ.get('REMOTE_ADDR', '0.0.0.0')

def hash_password(password: str) -> str:
    """
    Hashea una contraseña de forma segura
    
    Args:
        password: Contraseña en texto plano
    
    Returns:
        Hash de la contraseña
    """
    from app.extensions import bcrypt
    return bcrypt.generate_password_hash(password).decode('utf-8')

def check_password(password_hash: str, password: str) -> bool:
    """
    Verifica una contraseña contra su hash
    
    Args:
        password_hash: Hash almacenado
        password: Contraseña a verificar
    
    Returns:
        True si coincide
    """
    from app.extensions import bcrypt
    return bcrypt.check_password_hash(password_hash, password)

def generate_token(length: int = 32) -> str:
    """
    Genera un token aleatorio seguro
    
    Args:
        length: Longitud del token
    
    Returns:
        Token generado
    """
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def send_notification(user_id: int, title: str, message: str, 
                     notification_type: str = 'info') -> bool:
    """
    Envía una notificación al usuario
    
    Args:
        user_id: ID del usuario
        title: Título de la notificación
        message: Mensaje
        notification_type: Tipo (info, warning, error, success)
    
    Returns:
        True si se envió exitosamente
    """
    # Aquí iría la lógica para enviar notificaciones
    # Por ahora solo log
    current_app.logger.info(f"Notificación para usuario {user_id}: {title}")
    return True

def validate_business_hours(hour: int, minute: int = 0) -> bool:
    """
    Valida si una hora está dentro del horario comercial
    
    Args:
        hour: Hora (0-23)
        minute: Minuto (0-59)
    
    Returns:
        True si está en horario comercial
    """
    # Por defecto 8 AM a 10 PM
    start_hour = current_app.config.get('BUSINESS_START_HOUR', 8)
    end_hour = current_app.config.get('BUSINESS_END_HOUR', 22)
    
    return start_hour <= hour < end_hour

def format_file_size(size_bytes: int) -> str:
    """
    Formatea un tamaño de archivo en formato legible
    
    Args:
        size_bytes: Tamaño en bytes
    
    Returns:
        Tamaño formateado (KB, MB, GB)
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"

def save_picture(form_picture, folder='products'):
    """Guarda imagen subida optimizada"""
    try:
        random_hex = secrets.token_hex(8)
        _, f_ext = os.path.splitext(form_picture.filename)
        picture_filename = random_hex + f_ext
        picture_path = os.path.join(current_app.root_path, 'static/uploads', folder, picture_filename)
        
        os.makedirs(os.path.dirname(picture_path), exist_ok=True)
        
        # Optimizar imagen
        img = Image.open(form_picture)
        img.thumbnail((800, 600))
        img.save(picture_path, optimize=True, quality=85)
        
        return picture_filename
    except Exception:
        return None

def delete_picture(filename, folder='products'):
    """Elimina imagen del servidor"""
    try:
        if filename:
            picture_path = os.path.join(current_app.root_path, 'static/uploads', folder, filename)
            if os.path.exists(picture_path):
                os.remove(picture_path)
        return True
    except Exception:
        return False
