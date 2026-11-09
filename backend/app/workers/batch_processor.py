import asyncio,hashlib,logging,uuid
from pathlib import Path
from sqlalchemy.orm import Session
from ..ai.provider import get_provider
from ..db import SessionLocal
from ..models import Application,Candidate,CvBlob,CvFile,Requisition,UploadBatch
from ..services.dedupe import find_duplicate
from ..services.parsing import ParseError,parse_file
from ..services.redaction import redact
from ..config import settings
log=logging.getLogger(__name__)
queue:asyncio.Queue[uuid.UUID]=asyncio.Queue();worker_tasks:list[asyncio.Task]=[]
def enqueue(file_id:uuid.UUID)->None:queue.put_nowait(file_id)
async def process_file(file_id:uuid.UUID)->None:
    db=SessionLocal()
    try:
        file=db.get(CvFile,file_id);blob=db.query(CvBlob).filter_by(cv_file_id=file_id).first()
        if not file or not blob:return
        file.status='parsing';file.sha256=hashlib.sha256(blob.data).hexdigest();db.commit()
        parsed=parse_file(Path(file.filename),blob.data);file.parse_method=parsed.parse_method
        duplicate=find_duplicate(db,file.sha256,None,'',file.id)
        if duplicate.kind=='exact':file.candidate_id=duplicate.existing_candidate.id if duplicate.existing_candidate else None;file.status='duplicate';db.commit();return
        if parsed.parse_method=='ocr_ai':
            profile=await get_provider().extract_profile(await get_provider().transcribe_scan(blob.data))
        else: profile=await get_provider().extract_profile(parsed.text)
        duplicate=find_duplicate(db,file.sha256,profile,parsed.text,file.id)
        if duplicate.kind in ('exact','contact'):
            file.candidate_id=duplicate.existing_candidate.id if duplicate.existing_candidate else None;file.status='duplicate' if duplicate.kind=='exact' else 'done';db.commit();return
        redacted=redact(parsed.text,profile.full_name);candidate=Candidate(candidate_code=f'CND-{uuid.uuid4().int%100000:05d}',full_name=profile.full_name,email=profile.email,phone=profile.phone,current_role=profile.current_role,total_exp_years=profile.total_exp_years,skills=profile.skills,notice_days=profile.notice_days,current_ctc_lpa=profile.current_ctc_lpa,expected_ctc_lpa=profile.expected_ctc_lpa,location=profile.location,experience=profile.experience,education=profile.education,raw_text=parsed.text,redacted_text=redacted,parse_confidence=parsed.parse_confidence,duplicate_of_id=duplicate.duplicate_of.id if duplicate.kind=='possible' else None,consent_status='pending')
        db.add(candidate);db.flush();file.candidate_id=candidate.id;file.status='needs_review' if duplicate.kind=='possible' or parsed.parse_confidence=='low' else 'done'
        batch=db.get(UploadBatch,file.batch_id)
        if batch and batch.requisition_id and not db.query(Application).filter_by(requisition_id=batch.requisition_id,candidate_id=candidate.id).first():
            db.add(Application(requisition_id=batch.requisition_id,candidate_id=candidate.id,cv_file_id=file.id,stage='sourced'))
        # PHASE 4: scoring goes here
        db.commit()
    except ParseError as exc:
        db.rollback();file=db.get(CvFile,file_id)
        if file:file.status='failed';file.error_code=exc.code;file.error_message=str(exc);db.commit()
    except Exception as exc:
        db.rollback();file=db.get(CvFile,file_id)
        if file:file.status='failed';file.error_code='processing_error';file.error_message=str(exc);db.commit()
    finally:db.close()
async def _worker()->None:
    while True:
        file_id=await queue.get()
        try:await process_file(file_id)
        finally:queue.task_done()
async def start_workers()->None:
    db=SessionLocal()
    try:
        for row in db.query(CvFile).filter(CvFile.status.in_(['queued','parsing','scoring'])).all():enqueue(row.id)
    finally:db.close()
    worker_tasks.extend(asyncio.create_task(_worker()) for _ in range(max(1,settings.ai_concurrency)))
async def stop_workers()->None:
    for task in worker_tasks:task.cancel()
    if worker_tasks:await asyncio.gather(*worker_tasks,return_exceptions=True)
    worker_tasks.clear()
