from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

DISCLAIMER = (
    "Decision support only. This is not a diagnosis. A qualified clinician must review "
    "every suggestion before it affects patient care."
)


class Vitals(BaseModel):
    model_config = ConfigDict(extra="forbid")
    CORE_VITALS: ClassVar[tuple[str, ...]] = ("heart_rate", "resp_rate", "spo2", "temperature_c", "systolic_bp")

    heart_rate: int | None = Field(None, ge=0, le=300, description="beats per minute")
    resp_rate: int | None = Field(None, ge=0, le=100, description="breaths per minute")
    spo2: int | None = Field(None, ge=0, le=100, description="oxygen saturation %")
    temperature_c: float | None = Field(None, ge=25, le=45)
    systolic_bp: int | None = Field(None, ge=0, le=300, description="mmHg")
    avpu: Literal["A", "V", "P", "U"] | None = Field(
        None, description="Alert, responds to Voice, responds to Pain, Unresponsive"
    )

    def missing(self) -> list[str]:
        return [name for name in self.CORE_VITALS if getattr(self, name) is None]


class TriageRequest(BaseModel):
    """No names or identifiers: the AI service only needs clinical signals."""
    model_config = ConfigDict(extra="forbid")

    chief_complaint: str = Field("", max_length=500)
    age_years: float | None = Field(None, ge=0, le=130)
    pain_score: int | None = Field(None, ge=0, le=10)
    vitals: Vitals = Field(default_factory=Vitals)


class TriageResponse(BaseModel):
    suggested_esi: int = Field(ge=1, le=5)
    risk_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    reasons: list[str]
    recommendation: str
    missing_vitals: list[str]
    requires_clinician_review: Literal[True] = True
    method: Literal["rules"] = "rules"
    model_version: str
    disclaimer: str = DISCLAIMER


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=500)


class AskResponse(BaseModel):
    answer: str
    topic: str
    emergency: bool
    source: Literal["built-in-rules"] = "built-in-rules"
    disclaimer: str
