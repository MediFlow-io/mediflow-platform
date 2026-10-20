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


class RiskScoreRequest(BaseModel):
    """Vital signs only. No names or identifiers."""
    model_config = ConfigDict(extra="forbid")

    vitals: Vitals = Field(default_factory=Vitals)
    on_oxygen: bool = False
    new_confusion: bool = False


class RiskParameter(BaseModel):
    parameter: str
    value: int | float | str | bool | None
    points: int


class RiskScoreResponse(BaseModel):
    score: int
    risk: Literal["low", "low-medium", "medium", "high"]
    complete: bool
    parameters: list[RiskParameter]
    missing: list[str]
    reasons: list[str]
    recommendation: str
    requires_clinician_review: Literal[True] = True
    method: Literal["news2"] = "news2"
    model_version: str
    disclaimer: str = DISCLAIMER


class QueueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field("", max_length=100)
    ahead: int = Field(ge=0, le=1000)
    clinicians: int = Field(1, ge=0, le=100)
    recent_service_minutes: list[float] = Field(default_factory=list, max_length=1000)


class WaitTimeRequest(BaseModel):
    """One or more queues (e.g. every department) in a single call."""
    model_config = ConfigDict(extra="forbid")

    queues: list[QueueInput] = Field(min_length=1, max_length=100)


class WaitEstimate(BaseModel):
    name: str
    expected_minutes: int
    low_minutes: int
    high_minutes: int
    confidence: Literal["low", "medium", "high"]
    basis: str
    note: str


class WaitTimeResponse(BaseModel):
    estimates: list[WaitEstimate]
    method: Literal["statistics"] = "statistics"
    model_version: str


class DepartmentFlow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=100)
    check_ins: int = Field(ge=0)
    waiting_now: int = Field(0, ge=0)
    avg_wait_minutes: float | None = Field(None, ge=0)
    avg_call_to_start_minutes: float | None = Field(None, ge=0)
    avg_consult_minutes: float | None = Field(None, ge=0)
    seen_within_target_percent: float | None = Field(None, ge=0, le=100)


class HourFlow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hour: int = Field(ge=0, le=23)
    check_ins: int = Field(ge=0)
    avg_wait_minutes: float | None = Field(None, ge=0)


class BottleneckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    departments: list[DepartmentFlow] = Field(default_factory=list, max_length=100)
    hours: list[HourFlow] = Field(default_factory=list, max_length=24)


class Finding(BaseModel):
    severity: Literal["high", "medium", "low"]
    department: str
    stage: str
    message: str


class BottleneckResponse(BaseModel):
    findings: list[Finding]
    method: Literal["rules"] = "rules"
    model_version: str
