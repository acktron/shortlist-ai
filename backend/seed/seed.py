from passlib.context import CryptContext
from app.db import Base,engine,SessionLocal
from app.models import Client,User,Role,Requisition,Scorecard
import argparse
pwd=CryptContext(schemes=["bcrypt"],deprecated="auto")
def seed(reset:bool=False):
    if reset: Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine); db=SessionLocal(); meridian=Client(name="Meridian Bank",industry="Banking"); kestrel=Client(name="Kestrel IT Services",industry="IT services"); db.add_all([meridian,kestrel]); db.flush()
    recruiter=User(email="recruiter@companya.demo",full_name="Demo Recruiter",role=Role.recruiter,password_hash=pwd.hash("Demo@1234")); head=User(email="head@companya.demo",full_name="Demo Delivery Head",role=Role.delivery_head,password_hash=pwd.hash("Demo@1234")); priya=User(email="priya@meridianbank.demo",full_name="Priya Sharma",role=Role.client,client_id=meridian.id,password_hash=pwd.hash("Demo@1234")); rahul=User(email="rahul@kestrelit.demo",full_name="Rahul Mehta",role=Role.client,client_id=kestrel.id,password_hash=pwd.hash("Demo@1234")); db.add_all([recruiter,head,priya,rahul]); db.flush()
    java=Requisition(client_id=kestrel.id,owner_id=recruiter.id,title='Senior Java Developer',location='Noida',jd_text='Senior Java Developer, Noida, 5-8 yrs, Java, Spring Boot, microservices, notice 60 days or less',openings=1)
    kyc=Requisition(client_id=meridian.id,owner_id=recruiter.id,title='KYC Analyst',location='Noida',jd_text='KYC Analyst, Noida, 2-5 yrs, KYC, AML, Excel, notice 30 days or less',openings=1); db.add_all([java,kyc]);db.flush()
    db.add_all([Scorecard(requisition_id=java.id,version=1,is_active=True,created_by=recruiter.id,criteria=[{'id':'java','kind':'must_skill','label':'Java','weight':3,'params':{}},{'id':'spring-boot','kind':'must_skill','label':'Spring Boot','weight':3,'params':{}},{'id':'microservices','kind':'must_skill','label':'Microservices','weight':3,'params':{}},{'id':'experience','kind':'experience','label':'Experience','weight':3,'params':{'min_years':5,'max_years':8}},{'id':'notice','kind':'notice','label':'Notice period','weight':2,'params':{'max_days':60}}]),Scorecard(requisition_id=kyc.id,version=1,is_active=True,created_by=recruiter.id,criteria=[{'id':'kyc','kind':'must_skill','label':'KYC','weight':3,'params':{}},{'id':'aml','kind':'must_skill','label':'AML','weight':3,'params':{}},{'id':'excel','kind':'must_skill','label':'Excel','weight':3,'params':{}},{'id':'experience','kind':'experience','label':'Experience','weight':3,'params':{'min_years':2,'max_years':5}},{'id':'notice','kind':'notice','label':'Notice period','weight':2,'params':{'max_days':30}}])]); db.commit(); db.close()
if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument('--reset',action='store_true'); seed(parser.parse_args().reset)

