# tests/test_public.py
def test_public_store(client, app):
    """Test public store page"""
    with app.app_context():
        # Create a user
        user = User(
            business_name='Test Store',
            email='store@example.com',
            phone='+53 5555-5555'
        )
        user.set_password('testpass')
        db.session.add(user)
        db.session.commit()
        
        # Access public store
        response = client.get(f'/tienda/{user.slug}')
        assert response.status_code == 200
        assert b'Test Store' in response.data

def test_store_not_found(client):
    """Test accessing non-existent store"""
    response = client.get('/tienda/non-existent-store')
    assert response.status_code == 404
