from typing import Any

VERDICTS={'met':1.0,'partial':0.5,'not_met':0.0,'unverified':0.0,'unknown':None}


def experience_verdict(years: float, minimum: float, maximum: float) -> str:
    """Return the SPEC experience verdict for a candidate's years of experience."""
    if minimum <= years <= maximum:
        return 'met'
    if years >= minimum - 1 or years > maximum:
        return 'partial'
    return 'not_met'


def build_score_summary(total: int | None, band: str | None, criteria: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Summarize stored verdicts for display without reclassifying criteria."""
    if total is None or band is None:
        return None
    counts = {'met': 0, 'partial': 0, 'not_met': 0, 'not_stated': 0}
    for item in criteria:
        verdict = item.get('verdict')
        if verdict in ('met', 'partial', 'not_met'):
            counts[verdict] += 1
        else:
            counts['not_stated'] += 1
    return {'score': total, 'band': band, **counts}

def compute_score(criteria: list[dict[str,Any]], weights: dict[str,float]|None=None) -> dict[str,Any]:
    weights=weights or {}
    earned=known=all_weight=0.0; details=[]; must_have_met=0
    for item in criteria:
        weight=float(weights.get(item.get('criterion_id'),item.get('weight',1)))
        verdict=item.get('verdict','unknown'); points=VERDICTS.get(verdict,0.0)
        if verdict != 'unknown':
            known += weight; earned += points*weight
        all_weight += weight
        detail={**item,'points':(points or 0.0)*weight,'max_points':weight}
        details.append(detail)
        if item.get('kind')=='must_skill' and verdict=='met': must_have_met += 1
    total=round(100*earned/known) if known else 0
    coverage=round(known/all_weight,4) if all_weight else 0.0
    band='strong' if total>=75 else 'possible' if total>=50 else 'low'
    confidence='low' if any(i.get('verdict')=='unverified' for i in details) or coverage<0.7 else 'medium' if any(i.get('verdict')=='partial' and i.get('kind')=='must_skill' for i in details) else 'high'
    reasons=[]
    if confidence=='low': reasons.append('Low scoring confidence')
    return {'total':total,'coverage':coverage,'band':band,'confidence':confidence,'needs_review':confidence=='low','review_reasons':reasons,'criteria':details,'must_have_met':must_have_met}

def score_criteria(criteria: list[dict[str,Any]]) -> dict[str,Any]: return compute_score(criteria)

def sort_scores(rows: list[dict[str,Any]]) -> list[dict[str,Any]]:
    return sorted(rows,key=lambda row:(-row.get('total',0),-row.get('coverage',0),-row.get('must_have_met',0)))
