# 🚀 PedidosSaaS - Sistema de Pedidos Multiusuario

Sistema SaaS completo para que cualquier negocio pueda crear su tienda online y recibir pedidos. Desarrollado con Flask, PostgreSQL y Tailwind CSS.

## 🌟 Características Principales

- **Multi-tenant**: Cada negocio tiene su propia tienda con URL única
- **Panel de administración**: Gestión completa de productos y pedidos
- **Tienda pública responsive**: Diseño moderno y adaptable
- **Carrito de compras**: Con persistencia local
- **Seguridad**: Autenticación segura y protección CSRF
- **Listo para producción**: Configurado para Railway/Render

## 📋 Requisitos Previos

- Python 3.8 o superior
- PostgreSQL 12 o superior
- Git

## 🛠️ Instalación Local

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/pedidos-saas.git
cd pedidos-saas
```

### 2. Crear entorno virtual

```bash
python -m venv venv

# En Windows:
venv\Scripts\activate

# En Linux/Mac:
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Crear archivo `.env` en la raíz del proyecto:

```env
FLASK_ENV=development
SECRET_KEY=tu-clave-secreta-super-segura
DATABASE_URL=postgresql://usuario:password@localhost/pedidos_saas
```

### 5. Crear base de datos

```bash
# Acceder a PostgreSQL
psql -U postgres

# Crear base de datos
CREATE DATABASE pedidos_saas;
\q
```

### 6. Inicializar base de datos

```bash
# Inicializar migraciones
flask db init

# Crear primera migración
flask db migrate -m "Initial migration"

# Aplicar migraciones
flask db upgrade
```

### 7. Ejecutar aplicación

```bash
python run.py
```

La aplicación estará disponible en `http://localhost:5000`

## 🚀 Despliegue en Railway

### 1. Preparar el proyecto

Crear archivo `Procfile` en la raíz:

```
web: gunicorn run:app
```

Crear archivo `runtime.txt`:

```
python-3.11.0
```

### 2. Configurar en Railway

1. Crear cuenta en [Railway](https://railway.app)
2. Nuevo proyecto → Deploy from GitHub repo
3. Agregar servicio PostgreSQL
4. Configurar variables de entorno:
   - `SECRET_KEY`: Generar clave segura
   - `FLASK_ENV`: production
   - `DATABASE_URL`: Se configura automáticamente

### 3. Desplegar

Railway desplegará automáticamente al hacer push a GitHub.

## 🚀 Despliegue en Render

### 1. Preparar el proyecto

Crear archivo `render.yaml` en la raíz:

```yaml
services:
  - type: web
    name: pedidos-saas
    env: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "gunicorn run:app"
    envVars:
      - key: FLASK_ENV
        value: production
      - key: SECRET_KEY
        generateValue: true
      - key: DATABASE_URL
        fromDatabase:
          name: pedidos-db
          property: connectionString

databases:
  - name: pedidos-db
    databaseName: pedidos_saas
    user: pedidos_user
```

### 2. Configurar en Render

1. Crear cuenta en [Render](https://render.com)
2. New → Web Service → Connect GitHub repo
3. Configurar según `render.yaml`
4. Deploy

## 📱 Uso del Sistema

### Para Dueños de Negocios

1. **Registrarse**: Crear cuenta con datos del negocio
2. **Agregar productos**: Subir catálogo con imágenes
3. **Compartir tienda**: URL única `tupagina.com/tienda/tu-negocio`
4. **Gestionar pedidos**: Ver y actualizar estados

### Para Clientes

1. **Visitar tienda**: Acceder a la URL del negocio
2. **Agregar al carrito**: Seleccionar productos
3. **Realizar pedido**: Completar formulario
4. **Recibir confirmación**: Número de orden

## 🔒 Seguridad

- Contraseñas hasheadas con bcrypt
- Protección CSRF en todos los formularios
- Sesiones seguras con Flask-Login
- Validación de entrada en backend y frontend
- Sanitización de nombres de archivo

## 📂 Estructura del Proyecto

```
pedidos-saas/
├── app/
│   ├── __init__.py          # Factory app
│   ├── models.py            # Modelos de datos
│   ├── auth/                # Autenticación
│   ├── dashboard/           # Panel privado
│   ├── public/              # Tiendas públicas
│   └── templates/           # Plantillas HTML
├── migrations/              # Migraciones DB
├── config.py                # Configuración
├── requirements.txt         # Dependencias
└── run.py                   # Punto de entrada
```

## 🔧 Comandos Útiles

```bash
# Crear migración
flask db migrate -m "Descripción"

# Aplicar migraciones
flask db upgrade

# Rollback migración
flask db downgrade

# Shell interactivo
flask shell

# Ver rutas disponibles
flask routes
```

## 🐛 Solución de Problemas

### Error de conexión a PostgreSQL

```bash
# Verificar que PostgreSQL esté corriendo
sudo service postgresql status

# En Windows
pg_ctl status
```

### Error de migraciones

```bash
# Resetear migraciones
rm -rf migrations/
flask db init
flask db migrate -m "Initial"
flask db upgrade
```

### Error de permisos en uploads

```bash
# Crear carpeta y dar permisos
mkdir -p app/static/uploads
chmod 755 app/static/uploads
```

## 📈 Próximas Mejoras

- [ ] Sistema de notificaciones por email
- [ ] Integración con pasarelas de pago
- [ ] Dashboard con gráficas
- [ ] API REST para apps móviles
- [ ] Sistema de cupones
- [ ] Multi-idioma
- [ ] Exportar pedidos a Excel
- [ ] Chat en tiempo real

## 📝 Licencia

Este proyecto está bajo la Licencia MIT. Ver archivo `LICENSE` para más detalles.

## 👥 Contribuir

1. Fork el proyecto
2. Crear rama (`git checkout -b feature/AmazingFeature`)
3. Commit cambios (`git commit -m 'Add AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abrir Pull Request

## 💡 Soporte

Para soporte, enviar email a soporte@pedidossaas.com o abrir un issue en GitHub.

---

Desarrollado con ❤️ para emprendedores
