from pydantic import BaseModel
from typing import Optional
class Skill(BaseModel): name:str; aliases:list[str]=[]
class ExperienceRange(BaseModel): min_years:Optional[float]=None; max_years:Optional[float]=None
class NoticeLimit(BaseModel): max_days:Optional[int]=None
class CtcLimit(BaseModel): max_lpa:Optional[float]=None
class ScorecardDraft(BaseModel):
    title:str=''; location:str=''; experience:ExperienceRange=ExperienceRange(); must_have_skills:list[Skill]=[]; nice_to_have_skills:list[Skill]=[]; ctc:CtcLimit=CtcLimit(); notice:NoticeLimit=NoticeLimit(); field_confidence:dict[str,str]={}; missing_fields:list[str]=[]
class Profile(BaseModel): full_name:str=''; email:Optional[str]=None; phone:Optional[str]=None; location:str=''; current_role:str=''; total_exp_years:Optional[float]=None; skills:list[str]=[]; experience:list[dict]=[]; education:list[dict]=[]; notice_days:Optional[int]=None; current_ctc_lpa:Optional[float]=None; expected_ctc_lpa:Optional[float]=None; field_confidence:dict[str,str]={}
class CriterionVerdict(BaseModel): criterion_id:str; verdict:str; evidence:list[dict]=[]; reason:str=''
class ScoreResult(BaseModel): criteria:list[CriterionVerdict]=[]
