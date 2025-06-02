#!/usr/bin/env bash
# Build script para Render
# Este script se ejecuta antes de iniciar la aplicación

set -o errexit

echo "🚀 Starting build process..."

# Instalar dependencias
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Actualizar pip
echo "🔄 Updating pip..."
pip install --upgrade pip

# Debug información
echo "🔍 Running debug script..."
python debug_render.py

# Crear tablas si no existen
echo "🗄️ Creating database tables..."
python create_tables.py

echo "✅ Build completed successfully!"
