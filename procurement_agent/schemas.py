import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


def contract_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class RiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ImmutableModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class LiabilityFinding(ImmutableModel):
    clause_reference: str
    risk_level: RiskLevel
    issue: str
    business_impact: str
    recommended_language: str


class IndemnityFinding(ImmutableModel):
    clause_reference: str
    risk_level: RiskLevel
    issue: str
    third_party_exposure: str
    recommended_language: str


class ContractSubmitted(ImmutableModel):
    event_type: Literal["contract.submitted"] = "contract.submitted"
    event_id: UUID = Field(default_factory=uuid4)
    contract_id: UUID = Field(default_factory=uuid4)
    contract_text: str = Field(min_length=100, max_length=100_000)
    baseline_hash: str
    submitted_at: datetime = Field(default_factory=utc_now)

    @classmethod
    def from_text(cls, text: str) -> "ContractSubmitted":
        normalized = text.strip()
        return cls(contract_text=normalized, baseline_hash=contract_hash(normalized))

    @model_validator(mode="after")
    def hash_matches_text(self) -> "ContractSubmitted":
        if self.baseline_hash != contract_hash(self.contract_text):
            raise ValueError("Contract baseline hash does not match contract text")
        return self


class LiabilityEvaluated(ImmutableModel):
    event_type: Literal["liability.evaluated"] = "liability.evaluated"
    event_id: UUID = Field(default_factory=uuid4)
    contract_id: UUID
    baseline_hash: str
    evaluation_started_at: datetime
    evaluated_at: datetime = Field(default_factory=utc_now)
    findings: tuple[LiabilityFinding, ...]


class IndemnityEvaluated(ImmutableModel):
    event_type: Literal["indemnity.evaluated"] = "indemnity.evaluated"
    event_id: UUID = Field(default_factory=uuid4)
    contract_id: UUID
    baseline_hash: str
    evaluation_started_at: datetime
    evaluated_at: datetime = Field(default_factory=utc_now)
    findings: tuple[IndemnityFinding, ...]


class EvaluationSynthesized(ImmutableModel):
    event_type: Literal["evaluation.synthesized"] = "evaluation.synthesized"
    event_id: UUID = Field(default_factory=uuid4)
    contract_id: UUID
    baseline_hash: str
    contract_text: str
    submitted_at: datetime
    synthesized_at: datetime = Field(default_factory=utc_now)
    liability: LiabilityEvaluated
    indemnity: IndemnityEvaluated

    @model_validator(mode="after")
    def validate_integrity(self) -> "EvaluationSynthesized":
        identifiers = {self.contract_id, self.liability.contract_id, self.indemnity.contract_id}
        hashes = {self.baseline_hash, self.liability.baseline_hash, self.indemnity.baseline_hash}
        if len(identifiers) != 1:
            raise ValueError("Evaluation contract identifiers do not match")
        if len(hashes) != 1 or self.baseline_hash != contract_hash(self.contract_text):
            raise ValueError("Evaluation baseline hashes do not match")
        return self


class ContractRemediated(ImmutableModel):
    event_type: Literal["contract.remediated"] = "contract.remediated"
    event_id: UUID = Field(default_factory=uuid4)
    contract_id: UUID
    baseline_hash: str
    corrected_text: str = Field(min_length=100)
    liability_findings: tuple[LiabilityFinding, ...]
    indemnity_findings: tuple[IndemnityFinding, ...]
    changes_applied: tuple[str, ...]
    legal_review_notes: str
    overall_risk_score: float = Field(ge=0, le=100)
    submitted_at: datetime
    remediation_started_at: datetime
    completed_at: datetime = Field(default_factory=utc_now)
    processing_drift_seconds: float = Field(ge=0)
    baseline_integrity_verified: bool


PipelineEvent = Annotated[
    ContractSubmitted
    | LiabilityEvaluated
    | IndemnityEvaluated
    | EvaluationSynthesized
    | ContractRemediated,
    Field(discriminator="event_type"),
]


class AnalysisRequest(BaseModel):
    contract_text: str = Field(min_length=100)


class AnalysisResponse(BaseModel):
    contract_id: UUID
    status: Literal["completed"] = "completed"
    liability_findings: tuple[LiabilityFinding, ...]
    indemnity_findings: tuple[IndemnityFinding, ...]
    corrected_text: str
    changes_applied: tuple[str, ...]
    legal_review_notes: str
    overall_risk_score: float
    baseline_integrity_verified: bool
    processing_drift_seconds: float
    submitted_at: datetime
    completed_at: datetime
