def test_register(client):
    """Test user registration"""
    response = client.post('/auth/register', data={
        'business_name': 'Nueva Panadería',
        'email': 'nueva@panaderia.com',
        'password': 'testpass123',
        'confirm_password': 'testpass123',
        'phone': '+53 5555-5555',
        'address': 'Calle 23'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Dashboard' in response.data

def test_login_logout(client):
    """Test login and logout"""
    # First register a user
    client.post('/auth/register', data={
        'business_name': 'Test Business',
        'email': 'test@example.com',
        'password': 'testpass123',
        'confirm_password': 'testpass123',
        'phone': '+53 5555-5555'
    })
    
    # Logout
    client.get('/auth/logout')
    
    # Login
    response = client.post('/auth/login', data={
        'email': 'test@example.com',
        'password': 'testpass123'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Dashboard' in response.data

def test_login_invalid_credentials(client):
    """Test login with invalid credentials"""
    response = client.post('/auth/login', data={
        'email': 'nonexistent@example.com',
        'password': 'wrongpass'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Email o contraseña incorrectos' in response.data
