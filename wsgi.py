#!/usr/bin/env python
from flask import Flask

# APLICACIÓN ULTRA-BÁSICA PARA TESTING
app = Flask(__name__)

@app.route('/')
def hello():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>PedidosSaaS - Test Básico</title></head>
    <body>
        <h1>🎉 ¡FUNCIONA!</h1>
        <p>Aplicación básica funcionando correctamente</p>
        <p>Request ID: test-success</p>
    </body>
    </html>
    """, 200

@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
