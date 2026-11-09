from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import get_current_user,require_role
from ..models import User,Role,Requisition,Scorecard
from ..schemas.requisitions import *
from ..ai.provider import get_provider
router=APIRouter(prefix='/requisitions',tags=['requisitions'])
@router.get('',response_model=list[RequisitionOut])
def listing(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    q=db.query(Requisition)
    if user.role==Role.client:q=q.filter(Requisition.client_id==user.client_id)
    return q.order_by(Requisition.created_at.desc()).all()
@router.post('',response_model=RequisitionOut)
def create(data:RequisitionCreate,db:Session=Depends(get_db),user:User=Depends(require_role(Role.recruiter,Role.delivery_head))):
    row=Requisition(**data.model_dump(),owner_id=user.id);db.add(row);db.commit();db.refresh(row);return row
@router.get('/{rid}',response_model=RequisitionOut)
def get(rid:UUID,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=db.get(Requisition,rid)
    if not row or (user.role==Role.client and row.client_id!=user.client_id):raise HTTPException(404,'Requisition not found')
    return row
@router.post('/{rid}/scorecard/extract')
async def extract(rid:UUID,db:Session=Depends(get_db),user:User=Depends(require_role(Role.recruiter,Role.delivery_head))):
    row=db.get(Requisition,rid)
    if not row:raise HTTPException(404,'Requisition not found')
    try:
        draft=await get_provider().extract_scorecard(row.jd_text); return {'draft':draft,'warning':None}
    except Exception as e:return {'draft':{'title':row.title,'location':row.location,'experience':{},'must_have_skills':[],'nice_to_have_skills':[],'ctc':{},'notice':{},'field_confidence':{},'missing_fields':[]},'warning':str(e)}
@router.get('/{rid}/scorecard',response_model=ScorecardOut)
def active_scorecard(rid:UUID,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=db.query(Scorecard).filter_by(requisition_id=rid,is_active=True).first()
    if not row:raise HTTPException(404,'Scorecard not found')
    return row
@router.put('/{rid}/scorecard',response_model=ScorecardOut)
def save_scorecard(rid:UUID,data:ScorecardSave,db:Session=Depends(get_db),user:User=Depends(require_role(Role.recruiter,Role.delivery_head))):
    current=db.query(Scorecard).filter_by(requisition_id=rid,is_active=True).first()
    version=(current.version+1 if current else 1)
    if current:current.is_active=False
    row=Scorecard(requisition_id=rid,version=version,is_active=True,created_by=user.id,**data.model_dump());db.add(row);db.commit();db.refresh(row);return row
