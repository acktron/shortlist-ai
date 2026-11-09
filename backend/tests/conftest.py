import os
os.environ['AI_MODE']='mock'
os.environ['DATABASE_URL']=os.getenv('TEST_DATABASE_URL','postgresql+psycopg://shortlist:shortlist@localhost:5432/shortlist_test')
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db import Base,engine,get_db
from app.models import Application, Candidate, Client, CvBlob, CvFile, Role, Score, Scorecard, Requisition, UploadBatch, User
from passlib.context import CryptContext
pwd=CryptContext(schemes=['bcrypt'],deprecated='auto')
@pytest.fixture(scope='session',autouse=True)
def schema():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
    with Session(engine) as db:
        meridian=Client(name='Meridian Bank',industry='Banking');kestrel=Client(name='Kestrel IT Services',industry='IT');db.add_all([meridian,kestrel]);db.flush()
        recruiter=User(email='recruiter@companya.demo',full_name='Recruiter',role=Role.recruiter,password_hash=pwd.hash('Demo@1234'));head=User(email='head@companya.demo',full_name='Delivery Head',role=Role.delivery_head,password_hash=pwd.hash('Demo@1234'));client_user=User(email='priya@meridianbank.demo',full_name='Priya',role=Role.client,client_id=meridian.id,password_hash=pwd.hash('Demo@1234'));db.add_all([recruiter,head,client_user]);db.flush()
        req=Requisition(client_id=kestrel.id,owner_id=recruiter.id,title='Senior Java Developer',location='Noida',jd_text='Senior Java Developer, Noida, 5-8 yrs, Java, Spring Boot, microservices, notice 60 days or less',openings=1);db.add(req);db.flush();db.add(Scorecard(requisition_id=req.id,version=1,is_active=True,created_by=recruiter.id,criteria=[{'id':'java','kind':'must_skill','label':'Java','weight':3,'params':{}}]));db.commit()
        candidate=Candidate(candidate_code='CND-SMOKE',full_name='Smoke Candidate',email='smoke@example.demo',phone='+919876543210',current_role='Java Developer',total_exp_years=6.5,skills=['Java'],notice_days=30,location='Noida',raw_text='Smoke Candidate\nJava Developer\nJava, Spring Boot\n6.5 years',redacted_text='Java Developer\nJava, Spring Boot\n6.5 years',consent_status='granted');db.add(candidate);db.flush()
        batch=UploadBatch(requisition_id=req.id,uploaded_by=recruiter.id,total=1,processed=1,failed=0,duplicates=0,status='done');db.add(batch);db.flush()
        cv=CvFile(batch_id=batch.id,candidate_id=candidate.id,filename='smoke.pdf',mime='application/pdf',size_bytes=4,sha256='smoke-hash',status='done',attempts=0);db.add(cv);db.flush()
        db.add(CvBlob(cv_file_id=cv.id,data=b'%PDF'))
        application=Application(requisition_id=req.id,candidate_id=candidate.id,cv_file_id=cv.id,stage='submitted',recruiter_opened_at=datetime.now(timezone.utc),submitted_at=datetime.now(timezone.utc),submitted_by=recruiter.id);db.add(application);db.flush()
        db.add(Score(application_id=application.id,scorecard_id=db.query(Scorecard).filter_by(requisition_id=req.id,is_active=True).one().id,total=100,coverage=1,band='strong',confidence='high',needs_review=False,review_reasons=[],criteria=[{'criterion_id':'java','label':'Java','verdict':'met','points':3,'max_points':3,'evidence':[{'quote':'Java','verified':True,'match_score':100}]}],scoring_input='<cv>Java Developer</cv>',model='mock',prompt_version='test',latency_ms=0))
        db.commit()
    yield
    Base.metadata.drop_all(engine)
@pytest.fixture
def client(schema):
    connection=engine.connect();transaction=connection.begin();session=Session(bind=connection)
    def override():
        yield session
    app.dependency_overrides[get_db]=override
    with TestClient(app) as test_client: yield test_client
    app.dependency_overrides.clear();session.close();transaction.rollback();connection.close()
