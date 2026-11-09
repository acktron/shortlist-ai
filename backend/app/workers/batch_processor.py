import asyncio,hashlib,logging,re,uuid
from typing import Any
from pathlib import Path
from ..ai.provider import get_provider
from ..ai.errors import AIProviderError
from ..db import SessionLocal
from ..models import Application,Candidate,CvBlob,CvFile,UploadBatch,Scorecard,Score,StageEvent,Requisition
from ..services.dedupe import find_duplicate
from ..services.parsing import ParseError,parse_file
from ..services.redaction import redact
from ..services.evidence import has_prompt_injection,verify_evidence
from ..services.scoring import compute_score,experience_verdict
from ..config import settings
log=logging.getLogger(__name__)
queue:asyncio.Queue[uuid.UUID]=asyncio.Queue();worker_tasks:list[asyncio.Task]=[]
def enqueue(file_id:uuid.UUID)->None:queue.put_nowait(file_id)

def _source_line(text:str, pattern:str)->str:
    return next((line.strip()[:200] for line in text.splitlines() if re.search(pattern,line,re.I)), '')

def _numeric_verdict(item:dict[str,Any],candidate:Candidate,requisition:Any,raw_text:str)->dict[str,Any]|None:
    kind=item.get('kind');params=item.get('params') or {};value=None;quote='';verdict='unknown';reason='The CV does not include this information.'
    if kind=='experience':
        value=candidate.total_exp_years;quote=_source_line(raw_text,r'\b(?:total\s+)?experience\s*:')
        low=params.get('min_years');high=params.get('max_years')
        if value is not None and low is not None and high is not None:
            years=float(value)
            verdict=experience_verdict(years,float(low),float(high))
            if verdict=='met':reason=f'{years:g} years is within the requested range.'
            elif verdict=='partial':reason='Experience is close to or above the requested range.'
            else:reason='Experience is below the requested range.'
    elif kind=='notice':
        value=candidate.notice_days;quote=_source_line(raw_text,r'notice(?:\s+period)?\s*:');maximum=params.get('max_days')
        if value is not None and maximum is not None:
            if value<=int(maximum):verdict='met';reason=f'{value} days is within the notice limit.'
            elif value<=int(maximum)+30:verdict='partial';reason='Notice period is up to 30 days above the limit.'
            else:verdict='not_met';reason='Notice period is more than 30 days above the limit.'
    elif kind=='ctc':
        value=candidate.expected_ctc_lpa;quote=_source_line(raw_text,r'expected\s+ctc\s*:');maximum=params.get('max_lpa')
        if value is not None and maximum is not None:
            if float(value)<=float(maximum):verdict='met';reason='Expected CTC is within the budget.'
            elif float(value)<=float(maximum)*1.1:verdict='partial';reason='Expected CTC is within 10% of the budget.'
            else:verdict='not_met';reason='Expected CTC is more than 10% above the budget.'
    elif kind=='location':
        value=candidate.location;quote=_source_line(raw_text,r'^\s*location\s*:') or _source_line(raw_text,r'open to relocat')
        if value:
            same_city=bool(requisition and requisition.location and value.casefold()==requisition.location.casefold())
            can_relocate=bool(re.search(r'open to relocat',raw_text,re.I))
            verdict='met' if same_city or can_relocate else 'partial'
            reason='Location matches the role.' if same_city else 'Relocation can be discussed.'
    else:return None
    evidence=[{'quote':quote}] if quote else []
    return {'criterion_id':item.get('id'),'kind':kind,'label':item.get('label',''),'weight':item.get('weight',1),'verdict':verdict,'evidence':evidence,'reason':reason}

def _verify_scoring_evidence(verdict:dict[str,Any],raw_text:str)->dict[str,Any]:
    evidence=verify_evidence(verdict.get('evidence',[]),raw_text)
    result={**verdict,'evidence':evidence}
    if result.get('verdict') in ('met','partial') and not any(item['verified'] for item in evidence):
        result['verdict']='unverified'
    return result

async def process_file(file_id:uuid.UUID)->None:
    db=SessionLocal()
    try:
        file=db.get(CvFile,file_id);blob=db.query(CvBlob).filter_by(cv_file_id=file_id).first()
        if not file or not blob:return
        file.status='parsing';file.sha256=hashlib.sha256(blob.data).hexdigest();db.commit()
        parsed=parse_file(Path(file.filename),blob.data);file.parse_method=parsed.parse_method
        if re.search(r'\binvoice\b',parsed.text,re.I) and not re.search(r'\b(?:skills|experience|employment|education)\s*:',parsed.text,re.I):
            raise ParseError('empty','No CV content was found in this document.')
        duplicate=find_duplicate(db,file.sha256,None,'',file.id)
        if duplicate.kind=='exact':file.candidate_id=duplicate.existing_candidate.id if duplicate.existing_candidate else None;file.status='duplicate';db.commit();return
        source_text=parsed.text
        if parsed.parse_method=='ocr_ai':
            source_text=await get_provider().transcribe_scan(blob.data)
            if not source_text.strip():raise ParseError('empty','No readable text could be transcribed from this CV.')
            parsed.text=source_text
            profile=await get_provider().extract_profile(source_text)
        else: profile=await get_provider().extract_profile(source_text)
        duplicate=find_duplicate(db,file.sha256,profile,parsed.text,file.id)
        if duplicate.kind=='exact':
            file.candidate_id=duplicate.existing_candidate.id if duplicate.existing_candidate else None;file.status='duplicate';db.commit();return
        if duplicate.kind=='contact' and duplicate.existing_candidate:
            candidate=duplicate.existing_candidate
        else:
            redacted=redact(parsed.text,profile.full_name)
            code_match=re.search(r'\bCND-\d{5}\b',parsed.text,re.I)
            code=code_match.group(0).upper() if code_match else f'CND-{int(file.sha256[:10],16)%100000:05d}'
            suffix=0
            while db.query(Candidate).filter_by(candidate_code=code).first():
                suffix+=1
                code=f'CND-{(int(file.sha256[:10],16)+suffix)%100000:05d}'
            candidate=Candidate(candidate_code=code,full_name=profile.full_name,email=profile.email,phone=profile.phone,current_role=profile.current_role,total_exp_years=profile.total_exp_years,skills=profile.skills,notice_days=profile.notice_days,current_ctc_lpa=profile.current_ctc_lpa,expected_ctc_lpa=profile.expected_ctc_lpa,location=profile.location,experience=[item.model_dump() for item in profile.experience],education=[item.model_dump() for item in profile.education],raw_text=parsed.text,redacted_text=redacted,parse_confidence=parsed.parse_confidence,duplicate_of_id=duplicate.duplicate_of.id if duplicate.kind=='possible' else None,consent_status='pending')
            db.add(candidate);db.flush()
        file.candidate_id=candidate.id;file.status='needs_review' if duplicate.kind=='possible' or parsed.parse_confidence=='low' else 'done'
        batch=db.get(UploadBatch,file.batch_id)
        app=db.query(Application).filter_by(requisition_id=batch.requisition_id,candidate_id=candidate.id).first() if batch else None
        if batch and not app:
            app=Application(requisition_id=batch.requisition_id,candidate_id=candidate.id,cv_file_id=file.id,stage='sourced');db.add(app);db.flush()
            db.add(StageEvent(application_id=app.id,from_stage='created',to_stage='sourced',actor_id=batch.uploaded_by,note='CV uploaded'))
        scorecard=db.query(Scorecard).filter_by(requisition_id=batch.requisition_id,is_active=True).first() if batch else None
        if app and scorecard:
            scoring_text=candidate.redacted_text or ''
            scoring_input=f'<cv>{scoring_text}</cv>'
            skill_criteria=[item for item in scorecard.criteria if item.get('kind') in ('must_skill','nice_skill')]
            model_result=await get_provider().score_cv(scoring_text,{'criteria':skill_criteria})
            by_id={item.criterion_id:item for item in model_result.criteria}
            verdicts=[];missing_criteria=False
            for item in scorecard.criteria:
                model_verdict=by_id.get(item.get('id'))
                if item.get('kind') in ('must_skill','nice_skill'):
                    if model_verdict is None:
                        current='unknown';evidence=[];reason='The AI did not return a verdict for this criterion.';missing_criteria=True
                    else:
                        current=model_verdict.verdict;evidence=[item.model_dump() for item in model_verdict.evidence];reason=model_verdict.reason
                    verdicts.append(_verify_scoring_evidence({'criterion_id':item.get('id'),'kind':item.get('kind'),'label':item.get('label',''),'weight':item.get('weight',1),'verdict':current,'evidence':evidence,'reason':reason},scoring_text))
                else:
                    verdict=_numeric_verdict(item,candidate,db.get(Requisition,batch.requisition_id),parsed.text)
                    if verdict is not None:
                        verdicts.append(_verify_scoring_evidence(verdict,scoring_text))
            result=compute_score(verdicts)
            if any(item.get('verdict')=='unverified' for item in verdicts):
                result['review_reasons'].append("AI evidence couldn't be found in the CV")
            if missing_criteria:
                result['needs_review']=True;result['confidence']='low';result['review_reasons'].append('AI returned an incomplete scorecard response')
            if parsed.parse_confidence=='low':
                result['needs_review']=True;result['confidence']='low'
                result['review_reasons'].extend(reason for reason in parsed.review_reasons if reason not in result['review_reasons'])
            if has_prompt_injection(parsed.text): result['needs_review']=True;result['confidence']='low';result['review_reasons'].append('CV contains instructions aimed at the AI')
            db.add(Score(application_id=app.id,scorecard_id=scorecard.id,total=result['total'],coverage=result['coverage'],band=result['band'],confidence=result['confidence'],needs_review=result['needs_review'],review_reasons=result['review_reasons'],criteria=result['criteria'],scoring_input=scoring_input,model=get_provider().model,prompt_version='phase3-v1'))
        db.commit()
    except ParseError as exc:
        db.rollback();file=db.get(CvFile,file_id)
        if file:file.status='failed';file.error_code=exc.code;file.error_message=str(exc);db.commit()
    except AIProviderError as exc:
        db.rollback();file=db.get(CvFile,file_id)
        if file:file.status='failed';file.error_code='ai_unavailable';file.error_message=str(exc);db.commit()
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
