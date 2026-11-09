from typing import Literal

from pydantic import BaseModel, Field


class Skill(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)


class ExperienceRange(BaseModel):
    min_years: float | None = None
    max_years: float | None = None


class NoticeLimit(BaseModel):
    max_days: int | None = None


class CtcLimit(BaseModel):
    max_lpa: float | None = None


class FieldConfidence(BaseModel):
    title: str | None = None
    location: str | None = None
    experience: str | None = None
    experience_min: str | None = None
    experience_max: str | None = None
    must_have_skills: str | None = None
    nice_to_have_skills: str | None = None
    notice: str | None = None
    ctc: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    current_role: str | None = None
    total_exp_years: str | None = None
    skills: str | None = None
    experience_history: str | None = None
    education: str | None = None
    notice_days: str | None = None
    current_ctc_lpa: str | None = None
    expected_ctc_lpa: str | None = None


class ScorecardDraft(BaseModel):
    title: str = ""
    location: str = ""
    experience: ExperienceRange = Field(default_factory=ExperienceRange)
    must_have_skills: list[Skill] = Field(default_factory=list)
    nice_to_have_skills: list[Skill] = Field(default_factory=list)
    ctc: CtcLimit = Field(default_factory=CtcLimit)
    notice: NoticeLimit = Field(default_factory=NoticeLimit)
    field_confidence: FieldConfidence = Field(default_factory=FieldConfidence)
    missing_fields: list[str] = Field(default_factory=list)


class ExperienceItem(BaseModel):
    title: str = ""
    company: str = ""
    start: str = ""
    end: str = ""
    summary: str = ""


class EducationItem(BaseModel):
    degree: str = ""
    field: str = ""
    institution: str = ""
    year: str = ""
    grade: str = ""


class Profile(BaseModel):
    full_name: str = ""
    email: str | None = None
    phone: str | None = None
    location: str = ""
    current_role: str = ""
    total_exp_years: float | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    notice_days: int | None = None
    current_ctc_lpa: float | None = None
    expected_ctc_lpa: float | None = None
    field_confidence: FieldConfidence = Field(default_factory=FieldConfidence)


class EvidenceQuote(BaseModel):
    quote: str


class CriterionVerdict(BaseModel):
    criterion_id: str
    verdict: Literal["met", "partial", "not_met"]
    evidence: list[EvidenceQuote] = Field(default_factory=list)
    reason: str = ""


class ScoreResult(BaseModel):
    criteria: list[CriterionVerdict] = Field(default_factory=list)


class TranscriptionResult(BaseModel):
    text: str
