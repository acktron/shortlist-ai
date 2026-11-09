from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import get_current_user,require_role
from ..models import User,Role,Requisition,Scorecard,Client,Application,Candidate,Score,CvFile,UploadBatch
from ..schemas.requisitions import RequisitionCreate,RequisitionOut,ScorecardSave,ScorecardOut
from ..ai.provider import get_provider
from ..workers.batch_processor import process_file
from ..services.scoring import build_score_summary
router=APIRouter(prefix='/requisitions',tags=['requisitions'])
@router.get('',response_model=list[RequisitionOut])
def listing(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    q=db.query(Requisition)
    if user.role==Role.client:q=q.filter(Requisition.client_id==user.client_id)
    rows=q.order_by(Requisition.created_at.desc()).all(); names={c.id:c.name for c in db.query(Client).all()}
    return [{**r.__dict__,'client_name':names.get(r.client_id,'')} for r in rows]
@router.get('/clients')
def clients(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    query=db.query(Client)
    if user.role==Role.client:query=query.filter(Client.id==user.client_id)
    return [{'id':str(row.id),'name':row.name} for row in query.order_by(Client.name).all()]
@router.post('',response_model=RequisitionOut)
def create(data:RequisitionCreate,db:Session=Depends(get_db),user:User=Depends(require_role(Role.recruiter))):
    row=Requisition(**data.model_dump(),owner_id=user.id);db.add(row);db.commit();db.refresh(row);return {**row.__dict__,'client_name':db.get(Client,row.client_id).name}
@router.get('/{rid}',response_model=RequisitionOut)
def get(rid:UUID,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=db.get(Requisition,rid)
    if not row or (user.role==Role.client and row.client_id!=user.client_id):raise HTTPException(404,'Requisition not found')
    return {**row.__dict__,'client_name':db.get(Client,row.client_id).name}
@router.post('/{rid}/scorecard/extract')
async def extract(rid:UUID,db:Session=Depends(get_db),user:User=Depends(require_role(Role.recruiter))):
    row=db.get(Requisition,rid)
    if not row:raise HTTPException(404,'Requisition not found')
    try:
        draft=await get_provider().extract_scorecard(row.jd_text); return {'draft':draft.model_dump(exclude_none=True),'warning':None}
    except Exception as e:return {'draft':{'title':row.title,'location':row.location,'experience':{},'must_have_skills':[],'nice_to_have_skills':[],'ctc':{},'notice':{},'field_confidence':{},'missing_fields':[]},'warning':str(e)}
@router.get('/{rid}/scorecard',response_model=ScorecardOut)
def active_scorecard(rid:UUID,db:Session=Depends(get_db),user:User=Depends(require_role(Role.recruiter,Role.delivery_head))):
    row=db.query(Scorecard).filter_by(requisition_id=rid,is_active=True).first()
    if not row:raise HTTPException(404,'Scorecard not found')
    return row
@router.put('/{rid}/scorecard',response_model=ScorecardOut)
def save_scorecard(rid:UUID,data:ScorecardSave,db:Session=Depends(get_db),user:User=Depends(require_role(Role.recruiter))):
    current=db.query(Scorecard).filter_by(requisition_id=rid,is_active=True).first()
    version=(current.version+1 if current else 1)
    if current:current.is_active=False
    row=Scorecard(requisition_id=rid,version=version,is_active=True,created_by=user.id,**data.model_dump());db.add(row);db.commit();db.refresh(row);return row
@router.post('/{rid}/rescore')
async def rescore(rid:UUID,db:Session=Depends(get_db),user:User=Depends(require_role(Role.recruiter))):
    if not db.get(Requisition,rid): raise HTTPException(404,'Requisition not found')
    files=[row.cv_file_id for row in db.query(Application).filter(Application.requisition_id==rid).all()]
    for file_id in files:
        if file_id: await process_file(file_id)
    return {'reprocessed':len(files)}
@router.get('/{rid}/summary')
def summary(rid:UUID,db:Session=Depends(get_db),user:User=Depends(require_role(Role.recruiter,Role.delivery_head))):
    if not db.get(Requisition,rid):raise HTTPException(404,'Requisition not found')
    applications=db.query(Application).filter_by(requisition_id=rid).all()
    scorecard=db.query(Scorecard).filter_by(requisition_id=rid,is_active=True).first()
    strong=0
    if scorecard:
        for application in applications:
            score=db.query(Score).filter_by(application_id=application.id,scorecard_id=scorecard.id).order_by(Score.created_at.desc()).first()
            strong+=int(bool(score and score.band=='strong'))
    return {
        'candidates':len(applications),
        'strong_matches':strong,
        'submitted':sum(application.submitted_at is not None for application in applications),
        'uploads':db.query(CvFile).join(UploadBatch,CvFile.batch_id==UploadBatch.id).filter(UploadBatch.requisition_id==rid).count(),
    }

@router.get('/{rid}/applications')
def applications(rid:UUID,q:str|None=None,band:str|None=None,needs_review:bool|None=None,stage:str|None=None,sort:str='score',page:int=Query(default=1,ge=1),db:Session=Depends(get_db),user:User=Depends(require_role(Role.recruiter,Role.delivery_head))):
    if not db.get(Requisition,rid):raise HTTPException(404,'Requisition not found')
    scorecard=db.query(Scorecard).filter_by(requisition_id=rid,is_active=True).first()
    rows=db.query(Application,Candidate).join(Candidate,Application.candidate_id==Candidate.id).filter(Application.requisition_id==rid).all()
    result=[];seen=set()
    for app,candidate in rows:
        if candidate.id in seen:continue
        seen.add(candidate.id)
        score=db.query(Score).filter_by(application_id=app.id,scorecard_id=scorecard.id).order_by(Score.created_at.desc()).first() if scorecard else None
        haystack=f'{candidate.candidate_code} {candidate.full_name} {candidate.current_role} {" ".join(candidate.skills or [])}'.casefold()
        if q and q.casefold() not in haystack:continue
        if band and (not score or score.band!=band):continue
        if needs_review is not None and bool(score and score.needs_review)!=needs_review:continue
        if stage and app.stage!=stage:continue
        must_have_met=sum(item.get('kind')=='must_skill' and item.get('verdict')=='met' for item in (score.criteria or [])) if score else 0
        result.append({'id':str(app.id),'candidate_id':str(candidate.id),'candidate_code':candidate.candidate_code,'name':candidate.full_name,'current_role':candidate.current_role,'experience':float(candidate.total_exp_years) if candidate.total_exp_years is not None else None,'skills':candidate.skills or [],'notice_days':candidate.notice_days,'score':score.total if score else None,'coverage':float(score.coverage) if score and score.coverage is not None else None,'must_have_met':must_have_met,'band':score.band if score else None,'score_summary':build_score_summary(score.total if score else None,score.band if score else None,score.criteria or [] if score else []),'needs_review':bool(score and score.needs_review),'review_reasons':score.review_reasons or [] if score else [],'stage':app.stage,'recruiter_opened_at':app.recruiter_opened_at,'duplicate_of_id':str(candidate.duplicate_of_id) if candidate.duplicate_of_id else None,'criteria':score.criteria if score else []})
    if sort=='name':result.sort(key=lambda x:(x['name'] or '').casefold())
    elif sort=='stage':result.sort(key=lambda x:x['stage'])
    else:result.sort(key=lambda x:(-(x['score'] if x['score'] is not None else -1),-(x['coverage'] or 0),-x['must_have_met'],x['candidate_code'] or ''))
    total=len(result)
    return {'items':result[(page-1)*50:page*50],'total':total,'page':page,'page_size':50}
