from types import SimpleNamespace
from app.db import SessionLocal
from app.models import Candidate,CvFile
from app.services.dedupe import find_duplicate,normalize_email,normalize_phone
def test_normalize_contacts():
    assert normalize_email(' Person@Example.COM ')=='person@example.com'
    assert normalize_phone('+91 98765-43210')=='9876543210'
def test_exact_hash_duplicate(schema):
    db=SessionLocal();candidate=Candidate(full_name='Ritika Bansal',raw_text='Java Spring Boot');db.add(candidate);db.flush();db.add(CvFile(candidate_id=candidate.id,sha256='hash-exact',filename='ritika.pdf'));db.commit()
    result=find_duplicate(db,'hash-exact',SimpleNamespace(),'',None);assert result.kind=='exact';assert result.existing_candidate.id==candidate.id;db.close()
def test_email_and_phone_deduplicate(schema):
    db=SessionLocal();candidate=Candidate(full_name='Arjun Rawat',email='arjun@example.demo',phone='+91 9876543210',raw_text='KYC AML');db.add(candidate);db.commit()
    assert find_duplicate(db,'new',SimpleNamespace(email='ARJUN@example.demo',phone=None,full_name=''),'',None).kind=='contact'
    assert find_duplicate(db,'newer',SimpleNamespace(email=None,phone='9876543210',full_name=''),'',None).kind=='contact';db.close()
def test_possible_duplicate_uses_name_and_text_similarity(schema):
    db=SessionLocal();candidate=Candidate(full_name='Pooja Nair',raw_text='Java Developer Spring Boot Microservices');db.add(candidate);db.commit()
    result=find_duplicate(db,'other',SimpleNamespace(email=None,phone=None,full_name='Pooja Nair'),'Java Developer Spring Boot Microservices',None);assert result.kind=='possible';assert result.duplicate_of.id==candidate.id;db.close()
