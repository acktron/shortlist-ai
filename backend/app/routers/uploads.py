from pathlib import Path
from uuid import UUID
from fastapi import APIRouter,Depends,File,HTTPException,UploadFile
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import require_role
from ..models import User,Role,Requisition,UploadBatch,CvFile,CvBlob,Candidate
from ..services.parsing import ParseError,validate_file
from ..workers.batch_processor import enqueue
from ..config import settings
router=APIRouter(tags=['uploads'])
def _file(row:CvFile,candidate:Candidate|None=None,db:Session|None=None):
    duplicate_of = None
    if row.status == 'duplicate' and candidate and db:
        original = db.query(CvFile).filter(CvFile.candidate_id == candidate.id, CvFile.id != row.id, CvFile.status != 'duplicate').order_by(CvFile.created_at.asc()).first()
        duplicate_of = {'filename': original.filename if original else None, 'candidate_code': candidate.candidate_code}
    return {'id':str(row.id),'filename':row.filename,'status':row.status,'error_code':row.error_code,'error_message':row.error_message,'parse_method':row.parse_method,'candidate_id':str(row.candidate_id) if row.candidate_id else None,'redacted_text':candidate.redacted_text if candidate else None,'duplicate_of':duplicate_of}
@router.post('/requisitions/{rid}/uploads')
async def upload(rid:UUID,files:list[UploadFile]=File(...),db:Session=Depends(get_db),user:User=Depends(require_role(Role.recruiter,Role.delivery_head))):
    if len(files)>settings.max_batch_files: raise HTTPException(422,detail={'code':'too_many_files','message':f'Maximum {settings.max_batch_files} files per batch.'})
    if not db.get(Requisition,rid): raise HTTPException(404,'Requisition not found')
    batch=UploadBatch(requisition_id=rid,uploaded_by=user.id,total=len(files),processed=0,failed=0,duplicates=0,status='processing');db.add(batch);db.flush();created=[];queued_ids=[]
    for uploaded in files:
        data=await uploaded.read();row=CvFile(batch_id=batch.id,filename=uploaded.filename or 'unnamed',mime=uploaded.content_type or 'application/octet-stream',size_bytes=len(data),status='queued',attempts=0);db.add(row);db.flush()
        try: validate_file(Path(row.filename),data);db.add(CvBlob(cv_file_id=row.id,data=data));created.append(row);queued_ids.append(row.id)
        except ParseError as exc: row.status='failed';row.error_code=exc.code;row.error_message=str(exc)
    db.commit()
    for file_id in queued_ids: enqueue(file_id)
    return {'batch_id':str(batch.id),'total':batch.total,'files':[_file(row,db=db) for row in db.query(CvFile).filter_by(batch_id=batch.id).all()]}
@router.get('/uploads/latest')
def latest_first(db:Session=Depends(get_db),user:User=Depends(require_role(Role.recruiter,Role.delivery_head))):
    batch=db.query(UploadBatch).order_by(UploadBatch.created_at.desc()).first()
    return progress(batch.id,db,user) if batch else None
@router.get('/uploads/{batch_id}')
def progress(batch_id:UUID,db:Session=Depends(get_db),user:User=Depends(require_role(Role.recruiter,Role.delivery_head))):
    batch=db.get(UploadBatch,batch_id)
    if not batch:raise HTTPException(404,'Upload batch not found')
    rows=db.query(CvFile).filter_by(batch_id=batch_id).all();done=sum(r.status in ('done','duplicate','needs_review','failed') for r in rows);batch.processed=done;batch.failed=sum(r.status=='failed' for r in rows);batch.duplicates=sum(r.status=='duplicate' for r in rows);batch.status='done' if done==batch.total else 'processing';db.commit()
    return {'batch_id':str(batch.id),'status':batch.status,'total':batch.total,'processed':done,'failed':batch.failed,'duplicates':batch.duplicates,'needs_review':sum(r.status=='needs_review' for r in rows),'parsed':sum(r.status=='done' for r in rows),'files':[_file(r,db.get(Candidate,r.candidate_id) if r.candidate_id else None,db) for r in rows]}
@router.post('/cv-files/{file_id}/retry')
def retry(file_id:UUID,db:Session=Depends(get_db),user:User=Depends(require_role(Role.recruiter,Role.delivery_head))):
    row=db.get(CvFile,file_id)
    if not row:raise HTTPException(404,'CV file not found')
    row.status='queued';row.error_code=None;row.error_message=None;row.attempts=(row.attempts or 0)+1;db.commit();enqueue(row.id);return {'id':str(row.id),'status':row.status}
@router.post('/uploads/{batch_id}/retry-failed')
def retry_failed(batch_id:UUID,db:Session=Depends(get_db),user:User=Depends(require_role(Role.recruiter,Role.delivery_head))):
    rows=db.query(CvFile).filter_by(batch_id=batch_id,status='failed').all()
    for row in rows:row.status='queued';row.error_code=None;row.error_message=None;row.attempts=(row.attempts or 0)+1;enqueue(row.id)
    db.commit();return {'retried':len(rows)}
@router.get('/cv-files/{file_id}/redacted')
def redacted(file_id:UUID,db:Session=Depends(get_db),user:User=Depends(require_role(Role.recruiter,Role.delivery_head))):
    row=db.get(CvFile,file_id);candidate=db.get(Candidate,row.candidate_id) if row and row.candidate_id else None
    if not row:raise HTTPException(404,'CV file not found')
    if not candidate or not candidate.redacted_text: raise HTTPException(404,detail={'code':'redacted_text_unavailable','message':'Redacted text is not available until this file has parsed successfully.'})
    return {'id':str(row.id),'filename':row.filename,'redacted_text':candidate.redacted_text}
