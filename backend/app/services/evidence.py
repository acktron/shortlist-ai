import re
import string
from rapidfuzz.fuzz import partial_ratio, token_set_ratio

def _normalise(value: str) -> str:
    value = value.lower().translate(str.maketrans('', '', string.punctuation))
    return ' '.join(value.split())

def verify_quote(quote: str, text: str) -> tuple[bool, float]:
    if not quote or not text: return False, 0.0
    q, t = _normalise(quote), _normalise(text)
    if q in t: return True, 100.0
    score = max(float(partial_ratio(q, t)), float(token_set_ratio(q, t)))
    return score >= 90.0, score

def verify_evidence(evidence: list[dict], text: str) -> list[dict]:
    result=[]
    for item in evidence or []:
        quote=str(item.get('quote','')); verified, match_score=verify_quote(quote,text)
        result.append({**item,'quote':quote,'verified':verified,'match_score':round(match_score,2)})
    return result

def has_prompt_injection(text: str) -> bool:
    return bool(re.search(r'\b(ignore (?:all|any|the) (?:previous|prior) instructions|score this candidate|instructions? to the ai)\b', text, re.I))
