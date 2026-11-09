"""Exercise the configured provider with one scorecard and one CV score."""

import asyncio
import json
import sys
from time import perf_counter

from .errors import AIProviderError
from .provider import get_provider
from ..config import settings

SAMPLE_JD = (
    "Senior Java Developer, Noida, 5-8 years. Required: Java and Spring Boot. "
    "Nice to have: Microservices. Notice period up to 60 days."
)
SAMPLE_CV = (
    "Senior backend engineer\nExperience: 6.5 years\n"
    "Skills: Java, Spring Boot, Microservices\n"
    "Built Spring Boot services for a payments platform."
)


async def run_check() -> dict:
    provider = get_provider()
    started = perf_counter()
    scorecard_started = perf_counter()
    draft = await provider.extract_scorecard(SAMPLE_JD)
    scorecard_latency_ms = round((perf_counter() - scorecard_started) * 1000)

    skills = [*draft.must_have_skills, *draft.nice_to_have_skills]
    criteria = [
        {
            "id": f"check-skill-{index}",
            "kind": "must_skill" if index <= len(draft.must_have_skills) else "nice_skill",
            "label": skill.name,
            "weight": 3 if index <= len(draft.must_have_skills) else 1,
            "params": {"aliases": skill.aliases},
        }
        for index, skill in enumerate(skills, start=1)
    ]
    score_started = perf_counter()
    score = await provider.score_cv(SAMPLE_CV, {"criteria": criteria})
    score_latency_ms = round((perf_counter() - score_started) * 1000)

    return {
        "ai_mode": settings.ai_mode,
        "model": provider.model,
        "scorecard": draft.model_dump(mode="json"),
        "score": score.model_dump(mode="json"),
        "scorecard_latency_ms": scorecard_latency_ms,
        "score_latency_ms": score_latency_ms,
        "total_latency_ms": round((perf_counter() - started) * 1000),
    }


def main() -> int:
    try:
        result = asyncio.run(run_check())
    except AIProviderError as error:
        print(f"AI check failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
