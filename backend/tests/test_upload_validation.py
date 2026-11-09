from io import BytesIO
from pathlib import Path
from app.db import SessionLocal
from app.models import Requisition
def auth(client):
    token=client.post('/api/auth/login',json={'email':'recruiter@companya.demo','password':'Demo@1234'}).json()['access_token']
    rid=SessionLocal().query(Requisition).first().id
    return rid,{'Authorization':f'Bearer {token}'}
def test_upload_rejects_bad_magic_and_keeps_failed_row(client):
    rid,headers=auth(client); response=client.post(f'/api/requisitions/{rid}/uploads',headers=headers,files={'files':('bad.pdf',BytesIO(b'not a pdf'),'application/pdf')})
    assert response.status_code==200; batch=response.json(); assert batch['files'][0]['status']=='failed'; assert batch['files'][0]['error_code']=='corrupt'
def test_upload_rejects_more_than_batch_limit(client):
    rid,headers=auth(client); files=[('files',(f'{i}.pdf',BytesIO(b'%PDF-1.4'), 'application/pdf')) for i in range(501)]
    response=client.post(f'/api/requisitions/{rid}/uploads',headers=headers,files=files)
    assert response.status_code==422; assert response.json()['error']['code']=='too_many_files'
