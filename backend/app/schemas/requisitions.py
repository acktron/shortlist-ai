from uuid import UUID
from pydantic import BaseModel, Field
class RequisitionCreate(BaseModel): client_id:UUID; title:str; location:str; jd_text:str; openings:int=1
class RequisitionOut(RequisitionCreate): id:UUID; owner_id:UUID; status:str; client_name:str=''
class ScorecardSave(BaseModel): criteria:list[dict]; ai_draft:dict={}; ai_confidence:dict={}
class ScorecardOut(ScorecardSave): id:UUID; requisition_id:UUID; version:int; is_active:bool
