from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import require_role
from ..models import User, Role, Application, Candidate, Score, CvBlob, CvFile, AccessLog, StageEvent

router=APIRouter(tags=['applications'])
def _app(db:Session, aid:UUID):
    row=db.get(Application,aid)
    if not row: raise HTTPException(404,'Application not found')
    return row

@router.get('/applications/{aid}')
def detail(aid:UUID,db:Session=Depends(get_db),user:User=Depends(require_role(Role.recruiter,Role.delivery_head))):
    row=_app(db,aid); candidate=db.get(Candidate,row.candidate_id); score=db.query(Score).filter_by(application_id=row.id).order_by(Score.created_at.desc()).first()
    db.add(AccessLog(user_id=user.id,candidate_id=candidate.id,action='view_profile'));db.commit()
    return {'id':str(row.id),'candidate_code':candidate.candidate_code,'name':candidate.full_name,'current_role':candidate.current_role,'experience':float(candidate.total_exp_years) if candidate.total_exp_years is not None else None,'skills':candidate.skills or [],'notice_days':candidate.notice_days,'stage':row.stage,'recruiter_opened_at':row.recruiter_opened_at,'raw_text':candidate.raw_text,'redacted_text':candidate.redacted_text,'scoring_input':score.scoring_input if score else None,'criteria':score.criteria if score else [],'score':score.total if score else None,'band':score.band if score else None,'review_reasons':score.review_reasons if score else []}

@router.get('/applications/{aid}/cv')
def cv(aid:UUID,db:Session=Depends(get_db),user:User=Depends(require_role(Role.recruiter,Role.delivery_head))):
    row=_app(db,aid); blob=db.query(CvBlob).filter_by(cv_file_id=row.cv_file_id).first()
    if not blob: raise HTTPException(404,'CV not found')
    row.recruiter_opened_at=datetime.now(timezone.utc); row.stage='screened'; db.add(AccessLog(user_id=user.id,candidate_id=row.candidate_id,action='view_cv')); db.commit()
    file=db.get(CvFile,row.cv_file_id)
    return Response(content=blob.data,media_type=file.mime if file else 'application/octet-stream')

@router.post('/applications/{aid}/submit')
def submit(aid:UUID,db:Session=Depends(get_db),user:User=Depends(require_role(Role.recruiter,Role.delivery_head))):
    row=_app(db,aid)
    if not row.recruiter_opened_at: raise HTTPException(409,detail={'code':'cv_not_opened','message':'Open the candidate CV before submitting to the client.'})
    previous=row.stage;row.stage='submitted';row.submitted_at=datetime.now(timezone.utc);row.submitted_by=user.id;db.add(StageEvent(application_id=row.id,from_stage=previous,to_stage='submitted',actor_id=user.id));db.commit();return {'id':str(row.id),'stage':row.stage}

@router.post('/applications/{aid}/withdraw')
def withdraw(aid:UUID,db:Session=Depends(get_db),user:User=Depends(require_role(Role.recruiter,Role.delivery_head))):
    row=_app(db,aid);previous=row.stage;row.stage='withdrawn';db.add(StageEvent(application_id=row.id,from_stage=previous,to_stage='withdrawn',actor_id=user.id));db.commit();return {'id':str(row.id),'stage':row.stage}

