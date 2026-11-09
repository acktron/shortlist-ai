def test_me_requires_token(client):
    response=client.get('/api/auth/me')
    assert response.status_code==401

def test_login_and_client_id(client):
    response=client.post('/api/auth/login',json={'email':'recruiter@companya.demo','password':'Demo@1234'})
    assert response.status_code==200 and response.json()['user']['role']=='recruiter'
    client_response=client.post('/api/auth/login',json={'email':'priya@meridianbank.demo','password':'Demo@1234'})
    assert client_response.status_code==200 and client_response.json()['user']['client_id']

def test_wrong_password_is_401(client):
    assert client.post('/api/auth/login',json={'email':'recruiter@companya.demo','password':'wrong'}).status_code==401

def test_require_role_blocks_wrong_role(client):
    token=client.post('/api/auth/login',json={'email':'priya@meridianbank.demo','password':'Demo@1234'}).json()['access_token']
    assert client.get('/api/auth/recruiter-check',headers={'Authorization':f'Bearer {token}'}).status_code==403

