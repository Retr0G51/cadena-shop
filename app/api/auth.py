"""
API de autenticación para PedidosSaaS
Maneja tokens JWT y autenticación de API
"""
from flask import jsonify, request, current_app
from flask_login import current_user, login_user, logout_user
from datetime import datetime, timedelta
import jwt
from functools import wraps
from app.api import bp
from app.models import User
from app.extensions import db, limiter

# Decorador para requerir token API
def token_required(f):
    """Decorador que requiere un token JWT válido"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Buscar token en headers
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]  # Bearer <token>
            except IndexError:
                return jsonify({'message': 'Token format invalid'}), 401
        
        # Buscar token en query params (menos seguro)
        if not token and 'api_token' in request.args:
            token = request.args.get('api_token')
        
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        try:
            # Decodificar token
            data = jwt.decode(
                token, 
                current_app.config['SECRET_KEY'],
                algorithms=['HS256']
            )
            
            # Buscar usuario
            current_api_user = User.query.get(data['user_id'])
            
            if not current_api_user:
                return jsonify({'message': 'User not found'}), 401
            
            if not current_api_user.is_active:
                return jsonify({'message': 'User account is disabled'}), 401
            
            # Verificar expiración adicional
            if 'exp' in data:
                if datetime.utcnow() > datetime.fromtimestamp(data['exp']):
                    return jsonify({'message': 'Token has expired'}), 401
            
            # Pasar usuario a la función
            request.current_api_user = current_api_user
            
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token is invalid'}), 401
        except Exception as e:
            return jsonify({'message': 'Token error', 'error': str(e)}), 401
        
        return f(*args, **kwargs)
    
    return decorated

@bp.route('/auth/login', methods=['POST'])
@limiter.limit("5 per minute")
def api_login():
    """
    Endpoint para obtener token de API
    
    Body:
        {
            "email": "user@example.com",
            "password": "password123"
        }
    
    Returns:
        {
            "success": true,
            "token": "jwt_token",
            "expires_in": 3600,
            "user": {
                "id": 1,
                "email": "user@example.com",
                "business_name": "Mi Negocio"
            }
        }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password required'}), 400
    
    # Buscar usuario
    user = User.query.filter_by(email=email).first()
    
    if not user or not user.check_password(password):
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
    
    if not user.is_active:
        return jsonify({'success': False, 'message': 'Account is disabled'}), 401
    
    # Generar token JWT
    token_data = {
        'user_id': user.id,
        'email': user.email,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    
    token = jwt.encode(
        token_data,
        current_app.config['SECRET_KEY'],
        algorithm='HS256'
    )
    
    # Registrar último acceso API
    user.last_api_access = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'token': token,
        'expires_in': 86400,  # 24 horas en segundos
        'user': {
            'id': user.id,
            'email': user.email,
            'business_name': user.business_name,
            'plan': user.plan
        }
    })

@bp.route('/auth/refresh', methods=['POST'])
@token_required
def api_refresh_token():
    """
    Refresca un token existente
    
    Returns:
        Nuevo token con fecha de expiración extendida
    """
    user = request.current_api_user
    
    # Generar nuevo token
    token_data = {
        'user_id': user.id,
        'email': user.email,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    
    new_token = jwt.encode(
        token_data,
        current_app.config['SECRET_KEY'],
        algorithm='HS256'
    )
    
    return jsonify({
        'success': True,
        'token': new_token,
        'expires_in': 86400
    })

@bp.route('/auth/verify', methods=['GET'])
@token_required
def api_verify_token():
    """
    Verifica si un token es válido
    
    Returns:
        Información del usuario si el token es válido
    """
    user = request.current_api_user
    
    return jsonify({
        'success': True,
        'valid': True,
        'user': {
            'id': user.id,
            'email': user.email,
            'business_name': user.business_name,
            'plan': user.plan
        }
    })

@bp.route('/auth/api-keys', methods=['GET'])
@token_required
def get_api_keys():
    """
    Obtiene las API keys del usuario
    
    Returns:
        Lista de API keys activas
    """
    user = request.current_api_user
    
    # Aquí podrías implementar un sistema de API keys persistentes
    # Por ahora retornamos información básica
    
    return jsonify({
        'success': True,
        'api_keys': [
            {
                'id': 1,
                'name': 'Default API Key',
                'key': 'sk_live_' + user.api_key if hasattr(user, 'api_key') else None,
                'created_at': user.created_at.isoformat(),
                'last_used': user.last_api_access.isoformat() if user.last_api_access else None,
                'permissions': ['read', 'write']
            }
        ]
    })

@bp.route('/auth/api-keys', methods=['POST'])
@token_required
def create_api_key():
    """
    Crea una nueva API key
    
    Body:
        {
            "name": "My API Key",
            "permissions": ["read", "write"]
        }
    
    Returns:
        Nueva API key creada
    """
    user = request.current_api_user
    data = request.get_json()
    
    name = data.get('name', 'API Key')
    permissions = data.get('permissions', ['read'])
    
    # Generar API key
    import secrets
    api_key = 'sk_live_' + secrets.token_urlsafe(32)
    
    # Aquí guardarías la API key en la base de datos
    # Por ahora retornamos una respuesta simulada
    
    return jsonify({
        'success': True,
        'api_key': {
            'id': 2,
            'name': name,
            'key': api_key,
            'permissions': permissions,
            'created_at': datetime.utcnow().isoformat()
        }
    })

@bp.route('/auth/api-keys/<int:key_id>', methods=['DELETE'])
@token_required
def delete_api_key(key_id):
    """
    Elimina una API key
    
    Args:
        key_id: ID de la API key a eliminar
    
    Returns:
        Confirmación de eliminación
    """
    user = request.current_api_user
    
    # Aquí implementarías la lógica de eliminación
    
    return jsonify({
        'success': True,
        'message': 'API key deleted successfully'
    })

# Namespace para documentación
api_auth = {
    'name': 'Authentication',
    'description': 'API authentication endpoints',
    'endpoints': [
        {
            'path': '/auth/login',
            'method': 'POST',
            'description': 'Login and get JWT token',
            'auth_required': False
        },
        {
            'path': '/auth/refresh',
            'method': 'POST',
            'description': 'Refresh JWT token',
            'auth_required': True
        },
        {
            'path': '/auth/verify',
            'method': 'GET',
            'description': 'Verify token validity',
            'auth_required': True
        },
        {
            'path': '/auth/api-keys',
            'method': 'GET',
            'description': 'List API keys',
            'auth_required': True
        },
        {
            'path': '/auth/api-keys',
            'method': 'POST',
            'description': 'Create new API key',
            'auth_required': True
        },
        {
            'path': '/auth/api-keys/{key_id}',
            'method': 'DELETE',
            'description': 'Delete API key',
            'auth_required': True
        }
    ]
}
