import re
from .schemas import ScorecardDraft,Skill,Profile,ScoreResult,CriterionVerdict
class MockProvider:
    model='mock'
    async def extract_scorecard(self,jd:str)->ScorecardDraft:
        low=jd.lower(); skills=[]
        for s in ['java','spring boot','microservices','kyc','aml','excel','kafka','aws','docker']:
            if s in low: skills.append(Skill(name=s.title()))
        yrs=re.search(r'(\d+)\s*[-–]\s*(\d+)\s*(?:yrs?|years?)',low); notice=re.search(r'notice[^\d]*(\d+)',low); ctc=re.search(r'(?:up to|budget)[^\d]*(\d+)\s*lpa',low); loc='Noida' if 'noida' in low else ('Gurugram' if 'gurugram' in low else '')
        return ScorecardDraft(title=jd.split(',')[0][:100],location=loc,experience={'min_years':float(yrs.group(1)) if yrs else None,'max_years':float(yrs.group(2)) if yrs else None},must_have_skills=skills[:3],nice_to_have_skills=skills[3:],ctc={'max_lpa':float(ctc.group(1)) if ctc else None},notice={'max_days':int(notice.group(1)) if notice else None},field_confidence={'experience':'high' if yrs else 'low','location':'high' if loc else 'low','ctc':'high' if ctc else 'low'},missing_fields=[] if yrs and loc else ['experience','location'])
    async def transcribe_scan(self,data:bytes)->str:return ''
    async def extract_profile(self,text:str)->Profile:return Profile()
    async def score_cv(self,text:str,scorecard:dict)->ScoreResult:return ScoreResult()
