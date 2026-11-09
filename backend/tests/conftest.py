import os
os.environ['AI_MODE']='mock'
os.environ['DATABASE_URL']=os.getenv('TEST_DATABASE_URL','postgresql+psycopg://shortlist:shortlist@localhost:5432/shortlist_test')
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db import Base,engine,get_db
from app.models import Client,User,Role,Requisition,Scorecard
from passlib.context import CryptContext
pwd=CryptContext(schemes=['bcrypt'],deprecated='auto')
@pytest.fixture(scope='session',autouse=True)
def schema():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
    with Session(engine) as db:
        meridian=Client(name='Meridian Bank',industry='Banking');kestrel=Client(name='Kestrel IT Services',industry='IT');db.add_all([meridian,kestrel]);db.flush()
        recruiter=User(email='recruiter@companya.demo',full_name='Recruiter',role=Role.recruiter,password_hash=pwd.hash('Demo@1234'));client_user=User(email='priya@meridianbank.demo',full_name='Priya',role=Role.client,client_id=meridian.id,password_hash=pwd.hash('Demo@1234'));db.add_all([recruiter,client_user]);db.flush()
        req=Requisition(client_id=kestrel.id,owner_id=recruiter.id,title='Senior Java Developer',location='Noida',jd_text='Senior Java Developer, Noida, 5-8 yrs, Java, Spring Boot, microservices, notice 60 days or less',openings=1);db.add(req);db.flush();db.add(Scorecard(requisition_id=req.id,version=1,is_active=True,created_by=recruiter.id,criteria=[{'id':'java','kind':'must_skill','label':'Java','weight':3,'params':{}}]));db.commit()
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
