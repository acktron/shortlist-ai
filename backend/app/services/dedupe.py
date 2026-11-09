from dataclasses import dataclass
import re
from rapidfuzz.fuzz import token_set_ratio
from sqlalchemy.orm import Session
from ..models import Candidate,CvFile
@dataclass
class DedupeResult:
    kind:str='none'; existing_candidate:Candidate|None=None; duplicate_of:Candidate|None=None
def normalize_email(value:str|None)->str|None:return value.strip().lower() if value else None
def normalize_phone(value:str|None)->str|None:
    digits=re.sub(r'\D','',value or '');return digits[-10:] if len(digits)>=10 else None
def _candidate_name(profile:object)->str:return str(getattr(profile,'full_name','') or '').strip()
def find_duplicate(db:Session,sha256:str,profile:object,raw_text:str,exclude_file_id=None)->DedupeResult:
    exact=db.query(CvFile).filter(CvFile.sha256==sha256).first()
    if exact and exact.id!=exclude_file_id:
        return DedupeResult('exact',db.get(Candidate,exact.candidate_id))
    email=normalize_email(getattr(profile,'email',None));phone=normalize_phone(getattr(profile,'phone',None))
    for candidate in db.query(Candidate).all():
        if email and normalize_email(candidate.email)==email:return DedupeResult('contact',candidate)
        if phone and normalize_phone(candidate.phone)==phone:return DedupeResult('contact',candidate)
    name=_candidate_name(profile)
    if name:
        for candidate in db.query(Candidate).all():
            if candidate.full_name and candidate.full_name.casefold()==name.casefold() and token_set_ratio(candidate.raw_text or '',raw_text or '')>=85:
                return DedupeResult('possible',candidate, candidate)
    return DedupeResult()
