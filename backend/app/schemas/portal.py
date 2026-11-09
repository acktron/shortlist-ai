from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PortalFeedback(BaseModel):
    action: Literal["shortlist", "reject", "propose_interview"]
    reason_code: Literal["skills_gap", "experience", "notice_period", "ctc", "location", "culture_fit", "other"] | None = None
    note: str | None = Field(default=None, max_length=2000)
    proposed_slots: list[datetime] = Field(default_factory=list, max_length=3)
