from app.db import SessionLocal
from app.models import Requisition, Application, Candidate, CvFile, CvBlob, UploadBatch

def test_submit_requires_cv_opened(client):
    token=client.post('/api/auth/login',json={'email':'recruiter@companya.demo','password':'Demo@1234'}).json()['access_token']; h={'Authorization':f'Bearer {token}'}
    db=SessionLocal(); req=db.query(Requisition).first(); candidate=Candidate(candidate_code='CND-SUBMIT',full_name='Submit Candidate',raw_text='CV',redacted_text='CV',skills=[],consent_status='pending');db.add(candidate);db.flush();batch=UploadBatch(requisition_id=req.id,uploaded_by=req.owner_id,total=1,processed=1,failed=0,duplicates=0,status='done');db.add(batch);db.flush();file=CvFile(batch_id=batch.id,candidate_id=candidate.id,filename='x.pdf',mime='application/pdf',size_bytes=1,status='done');db.add(file);db.flush();db.add(CvBlob(cv_file_id=file.id,data=b'%PDF'));app=Application(requisition_id=req.id,candidate_id=candidate.id,cv_file_id=file.id,stage='sourced');db.add(app);db.commit();aid=app.id;db.close()
    response=client.post(f'/api/applications/{aid}/submit',headers=h)
    assert response.status_code==409 and response.json()['error']['code']=='cv_not_opened'

