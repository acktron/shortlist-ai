from io import BytesIO
from pathlib import Path
from app.db import SessionLocal
from app.models import Requisition, Candidate, CvFile, UploadBatch
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
def test_redacted_endpoint_returns_candidate_text(client):
    rid,headers=auth(client)
    db=SessionLocal(); user_id=db.query(Requisition).filter_by(id=rid).first().owner_id
    batch=UploadBatch(requisition_id=rid,uploaded_by=user_id,total=1,processed=1,failed=0,duplicates=0,status='done'); db.add(batch); db.flush()
    candidate=Candidate(candidate_code='CND-TEST',full_name='Test Candidate',redacted_text='Java experience',raw_text='Test Candidate Java experience',skills=['Java'],consent_status='pending'); db.add(candidate); db.flush()
    row=CvFile(batch_id=batch.id,candidate_id=candidate.id,filename='candidate.pdf',mime='application/pdf',size_bytes=10,status='done'); db.add(row); db.commit()
    response=client.get(f'/api/cv-files/{row.id}/redacted',headers=headers)
    assert response.status_code == 200
    assert response.json()['redacted_text'] == 'Java experience'
    db.close()

def test_requisitions_visible_and_scorecard_extract(client):
    token=client.post('/api/auth/login',json={'email':'recruiter@companya.demo','password':'Demo@1234'}).json()['access_token']; h={'Authorization':f'Bearer {token}'}
    rows=client.get('/api/requisitions',headers=h).json(); assert any(r['title']=='Senior Java Developer' for r in rows)
    rid=next(r['id'] for r in rows if r['title']=='Senior Java Developer'); draft=client.post(f'/api/requisitions/{rid}/scorecard/extract',headers=h).json()['draft']; assert draft['must_have_skills']
    previous=client.get(f'/api/requisitions/{rid}/scorecard',headers=h).json()
    criteria=[{'id':f'skill-{i}','kind':'must_skill','label':skill['name'],'weight':3,'params':{'aliases':skill.get('aliases',[])}} for i,skill in enumerate(draft['must_have_skills'])]
    saved=client.put(f'/api/requisitions/{rid}/scorecard',headers=h,json={'criteria':criteria}).json(); assert saved['version'] == previous['version'] + 1
