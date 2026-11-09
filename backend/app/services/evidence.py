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
        source_line = next((line.strip() for line in text.splitlines() if line.strip() and verify_quote(quote,line)[0]), '') if verified else ''
        if source_line:
            if len(source_line) > 200:
                match = re.search(re.escape(quote), source_line, re.I)
                anchor = match.start() if match else 0
                start = max(0, min(anchor - 80, len(source_line) - 200))
                source_line = source_line[start:start + 200].strip()
            quote = source_line
        else:
            verified = False
        result.append({**item,'quote':quote,'verified':verified,'match_score':round(match_score,2)})
    return result


def normalize_criteria_evidence(criteria: list[dict], text: str) -> list[dict]:
    """Expand old short quotes to verified CV lines while preserving stored verdicts."""
    return [
        {**criterion, 'evidence': verify_evidence(criterion.get('evidence', []), text)}
        for criterion in criteria
    ]

def has_prompt_injection(text: str) -> bool:
    return bool(re.search(r'\b(ignore (?:all|any|the) (?:previous|prior) instructions|score this candidate|instructions? to the ai)\b', text, re.I))
