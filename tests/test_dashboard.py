def test_dashboard_requires_login(client):
    """Test that dashboard requires authentication"""
    response = client.get('/dashboard/')
    assert response.status_code == 302  # Redirect to login

def test_dashboard_access(auth_client):
    """Test authenticated access to dashboard"""
    response = auth_client.get('/dashboard/')
    assert response.status_code == 200
    assert b'Dashboard' in response.data

def test_create_product(auth_client):
    """Test product creation"""
    response = auth_client.post('/dashboard/products/new', data={
        'name': 'Nuevo Producto',
        'description': 'Descripción del producto',
        'price': '15.50',
        'stock': '20',
        'category': 'Panadería',
        'is_active': '1',
        'is_featured': '0'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Nuevo Producto' in response.data
