import httpx,re
from .schemas import ScorecardDraft,Profile,ScoreResult
from .prompts import SCORECARD_SYSTEM,PROFILE_SYSTEM,SCORE_SYSTEM,TRANSCRIBE_SYSTEM
from ..config import settings
class OllamaProvider:
    model=settings.ollama_model
    async def _call(self,system:str,user:str,schema:type):
        payload={'model':self.model,'messages':[{'role':'system','content':system},{'role':'user','content':user}],'format':schema.model_json_schema(),'options':{'temperature':0},'stream':False}
        async with httpx.AsyncClient(timeout=120) as c:
            for attempt in range(2):
                r=await c.post(f'{settings.ollama_base_url}/api/chat',json=payload); r.raise_for_status()
                raw=r.json().get('message',{}).get('content','')
                try:return schema.model_validate_json(raw)
                except Exception as e:
                    payload['messages'].append({'role':'user','content':f'Validation error: {e}. Return corrected JSON only.'})
            return schema.model_validate_json(raw)
    async def extract_scorecard(self,jd:str):
        result=await self._call(SCORECARD_SYSTEM,jd,ScorecardDraft); low=jd.lower()
        years=re.search(r'(\d+)\s*[-–]\s*(\d+)\s*(?:yrs?|years?)',low); notice=re.search(r'notice[^\d]*(\d+)',low); ctc=re.search(r'(?:up to|budget)[^\d]*(\d+)\s*lpa',low)
        if years: result.experience.min_years=float(years.group(1));result.experience.max_years=float(years.group(2))
        if notice: result.notice.max_days=int(notice.group(1))
        if ctc: result.ctc.max_lpa=float(ctc.group(1))
        return result
    async def transcribe_scan(self,data:bytes):return (await self._call(TRANSCRIBE_SYSTEM,'Document bytes are provided separately.',Profile)).model_dump_json()
    async def extract_profile(self,text:str):return await self._call(PROFILE_SYSTEM,text,Profile)
    async def score_cv(self,text:str,scorecard:dict):return await self._call(SCORE_SYSTEM,f'<cv>{text}</cv>\n{scorecard}',ScoreResult)
