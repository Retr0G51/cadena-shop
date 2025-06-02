#!/bin/bash
# Script para inicializar migraciones (ejecutar solo una vez)

# Eliminar migraciones anteriores si existen
rm -rf migrations/

# Inicializar Flask-Migrate
flask db init

# Crear primera migración
flask db migrate -m "Initial migration"

# Aplicar migración
flask db upgrade

echo "✅ Migraciones inicializadas correctamente"
