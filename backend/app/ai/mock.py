import re
from io import BytesIO

from pypdf import PdfReader
from .schemas import CriterionVerdict, Profile, ScoreResult, ScorecardDraft, Skill


class MockProvider:
    """Deterministic local provider used for tests and demo data."""

    @staticmethod
    def _evidence_line(text: str, term: str) -> str:
        """Return the CV line containing a matched skill, capped at 200 chars."""
        for source_line in text.splitlines():
            line = source_line.strip()
            position = line.lower().find(term.lower())
            if position < 0:
                continue
            if len(line) <= 200:
                return line
            sentence = next((part.strip() for part in re.split(r"(?<=[.!?])\s+", line) if term.lower() in part.lower()), "")
            if sentence and len(sentence) <= 200:
                return sentence
            start = max(0, min(position - 80, len(line) - 200))
            return line[start:start + 200].strip()
        return ""

    model = "mock"

    async def extract_scorecard(self, jd: str) -> ScorecardDraft:
        low = jd.lower()
        skills = []
        for name in (
            "java", "spring boot", "microservices", "kyc", "aml", "excel",
            "kafka", "aws", "docker", "react", "typescript", "javascript",
        ):
            if name in low:
                skills.append(Skill(name=name.title()))
        years = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*(?:yrs?|years?)", low)
        notice = re.search(r"notice[^\d]*(\d+)", low)
        ctc = re.search(r"(?:up to|budget)[^\d]*(\d+)\s*lpa", low)
        location = next((name for name in ("Noida", "Gurugram", "Pune", "Bengaluru") if name.lower() in low), "")
        return ScorecardDraft(
            title=jd.split(",")[0][:100],
            location=location,
            experience={
                "min_years": float(years.group(1)) if years else None,
                "max_years": float(years.group(2)) if years else None,
            },
            must_have_skills=skills[:3],
            nice_to_have_skills=skills[3:],
            ctc={"max_lpa": float(ctc.group(1)) if ctc else None},
            notice={"max_days": int(notice.group(1)) if notice else None},
            field_confidence={"experience": "high" if years else "low", "location": "high" if location else "low"},
            missing_fields=[] if years and location else [name for name, value in (("experience", years), ("location", location)) if not value],
        )

    async def transcribe_scan(self, data: bytes) -> str:
        # Text-backed short PDFs can be transcribed exactly from their PDF text layer.
        try:
            text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages).strip()
            if text:
                return text
        except Exception:
            pass
        # The image-only seed scan is fixed; keep mock runs deterministic without OCR.
        return "Ritika Bansal\nSr Java Developer\nExperience: 6.5 years\nSkills: Java, Spring Boot, Microservices\nNotice period: 60 days\nLocation: Noida"

    async def extract_profile(self, text: str) -> Profile:
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        def value(pattern: str) -> str | None:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            return match.group(1).strip() if match else None

        name = value(r"^\s*name\s*:\s*([^|\n]+)")
        if not name and lines:
            name = re.sub(r"\s*[|·]\s*CND-\d+.*$", "", lines[0], flags=re.IGNORECASE).strip()
        email = value(r"\b([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})\b")
        phone = value(r"(?:phone|mobile|contact)\s*:?\s*((?:\+?91[\s-]?)?[6-9]\d{9})")
        location = value(r"^\s*location\s*:\s*([^\n|]+)") or ""
        role = value(r"^\s*(?:current role|role|designation)\s*:\s*([^\n|]+)")
        if not role:
            role = next((line for line in lines[1:] if not re.match(r"(?:email|phone|mobile|experience|skills|location|notice|expected ctc|current ctc)\s*:", line, re.I)), "")
        exp = value(r"(?:total\s+)?experience\s*:\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)")
        if exp is None:
            exp = value(r"\b(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\b")
        notice = value(r"notice(?:\s+period)?\s*:\s*(\d+)\s*days?")
        expected_ctc = value(r"expected\s+ctc\s*:\s*(\d+(?:\.\d+)?)\s*lpa")
        current_ctc = value(r"current\s+ctc\s*:\s*(\d+(?:\.\d+)?)\s*lpa")
        skills_line = value(r"^\s*skills\s*:\s*([^\n]+)") or ""
        skills = [part.strip() for part in re.split(r"[,;/|]", skills_line) if part.strip()]
        experience = []
        if role:
            experience.append({"title": role, "company": "", "start": "", "end": "", "summary": ""})
        return Profile(
            full_name=name or "Unknown Candidate",
            email=email,
            phone=phone,
            location=location,
            current_role=role or "",
            total_exp_years=float(exp) if exp else None,
            skills=skills,
            experience=experience,
            notice_days=int(notice) if notice else None,
            current_ctc_lpa=float(current_ctc) if current_ctc else None,
            expected_ctc_lpa=float(expected_ctc) if expected_ctc else None,
        )

    async def score_cv(self, text: str, scorecard: dict) -> ScoreResult:
        low = text.lower()
        results = []
        for criterion in scorecard.get("criteria", []):
            if criterion.get("kind") not in ("must_skill", "nice_skill"):
                continue
            label = criterion.get("label", "")
            aliases = criterion.get("params", {}).get("aliases", [])
            terms = [label, *aliases]
            found = next((term for term in terms if term and term.lower() in low), None)
            quote = self._evidence_line(text, found) if found else ""
            results.append(
                CriterionVerdict(
                    criterion_id=criterion.get("id", ""),
                    verdict="met" if found else "not_met",
                    evidence=[{"quote": quote}] if quote else [],
                    reason="Keyword evidence found." if found else "No evidence found.",
                )
            )
        return ScoreResult(criteria=results)
