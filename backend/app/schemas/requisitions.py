from uuid import UUID
from typing import Literal
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
class RequisitionCreate(BaseModel): client_id:UUID; title:str=Field(min_length=2,max_length=200); location:str=Field(min_length=2,max_length=120); jd_text:str=Field(min_length=20); openings:int=Field(default=1,ge=1,le=100)
class RequisitionOut(RequisitionCreate): id:UUID; owner_id:UUID; status:str; client_name:str=''; created_at:datetime|None=None
class Criterion(BaseModel):
    id:str=Field(min_length=1,max_length=80)
    kind:Literal['must_skill','nice_skill','experience','notice','ctc','location']
    label:str=Field(min_length=1,max_length=160)
    weight:int=Field(ge=1,le=5)
    params:dict=Field(default_factory=dict)
class ScorecardSave(BaseModel):
    criteria:list[Criterion]
    ai_draft:dict=Field(default_factory=dict)
    ai_confidence:dict=Field(default_factory=dict)
    @field_validator('criteria')
    @classmethod
    def unique_criterion_ids(cls,items):
        ids=[item.id for item in items]
        if len(ids)!=len(set(ids)):raise ValueError('Criterion ids must be unique.')
        return items
class ScorecardOut(ScorecardSave): id:UUID; requisition_id:UUID; version:int; is_active:bool
