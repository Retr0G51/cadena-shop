"""
Script para probar que el deployment funciona correctamente
"""
import requests
import sys

def test_deployment(base_url):
    """Prueba las rutas principales de la aplicación"""
    
    print(f"🧪 Probando deployment en: {base_url}")
    print("-" * 50)
    
    tests = [
        ("Página principal", f"{base_url}/", 200),
        ("Health check", f"{base_url}/health", 200),
        ("Login", f"{base_url}/auth/login", 200),
        ("Registro", f"{base_url}/auth/register", 200),
        ("404 page", f"{base_url}/esta-pagina-no-existe", 404),
    ]
    
    passed = 0
    failed = 0
    
    for name, url, expected_status in tests:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == expected_status:
                print(f"✅ {name}: OK (Status {response.status_code})")
                passed += 1
            else:
                print(f"❌ {name}: FAILED (Expected {expected_status}, got {response.status_code})")
                failed += 1
        except Exception as e:
            print(f"❌ {name}: ERROR - {str(e)}")
            failed += 1
    
    print("-" * 50)
    print(f"📊 Resultados: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 ¡Todas las pruebas pasaron! El deployment funciona correctamente.")
    else:
        print("⚠️  Algunas pruebas fallaron. Revisa los logs en Render.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("Ingresa la URL de tu app en Render (ej: https://tu-app.onrender.com): ")
    
    # Quitar trailing slash si existe
    url = url.rstrip('/')
    
    test_deployment(url)
