from passlib.context import CryptContext
from app.db import Base,engine,SessionLocal
from app.models import Client,User,Role
pwd=CryptContext(schemes=["bcrypt"],deprecated="auto")
def seed():
    Base.metadata.create_all(engine); db=SessionLocal(); meridian=Client(name="Meridian Bank",industry="Banking"); kestrel=Client(name="Kestrel IT Services",industry="IT services"); db.add_all([meridian,kestrel]); db.flush()
    db.add_all([User(email="recruiter@companya.demo",full_name="Demo Recruiter",role=Role.recruiter,password_hash=pwd.hash("Demo@1234")),User(email="head@companya.demo",full_name="Demo Delivery Head",role=Role.delivery_head,password_hash=pwd.hash("Demo@1234")),User(email="priya@meridianbank.demo",full_name="Priya Sharma",role=Role.client,client_id=meridian.id,password_hash=pwd.hash("Demo@1234")),User(email="rahul@kestrelit.demo",full_name="Rahul Mehta",role=Role.client,client_id=kestrel.id,password_hash=pwd.hash("Demo@1234"))]); db.commit(); db.close()
if __name__=="__main__": seed()

