from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from soc_ot.domain.models import DecisionType, StrictModel


class RiskAssessment(StrictModel):
    risk_id: str
    statement: str
    severity: Literal["low", "medium", "high", "critical"]
    claim_ids: list[str] = Field(default_factory=list)
    mitigation: str


class RoleReview(StrictModel):
    schema_version: Literal["role-review.v1"] = "role-review.v1"
    role_id: str
    recommendation: DecisionType
    recommended_option_id: str | None = None
    rationale: str
    rationale_claim_ids: list[str] = Field(default_factory=list)
    risks: list[RiskAssessment]
    information_gaps: list[str]
    unique_concern: str | None = None
    no_unique_concern: bool = False
    confidence: Literal["low", "medium", "high"]

    @model_validator(mode="after")
    def validate_decision_shape(self) -> "RoleReview":
        option_required = self.recommendation in {
            DecisionType.APPROVE,
            DecisionType.APPROVE_WITH_GUARDRAILS,
            DecisionType.RUN_REVERSIBLE_TRIAL,
        }
        if option_required and self.recommended_option_id is None:
            raise ValueError("selected decision requires recommended_option_id")
        if option_required and not self.rationale_claim_ids:
            raise ValueError("execution recommendation requires grounded claim")
        if bool(self.unique_concern) == self.no_unique_concern:
            raise ValueError("role must provide one unique concern or declare none")
        return self


class ProviderUsage(StrictModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0)
    provider_attempts: int = Field(default=1, ge=1)


class ProviderAttemptMetadata(StrictModel):
    attempt_id: str
    role_id: str
    review_round: int = Field(ge=0)
    provider: str
    requested_model: str
    returned_model: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int = Field(ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0)
    retry_reason: str | None = None
    validation_result: str
    final_status: Literal[
        "running",
        "accepted",
        "retryable_failed",
        "failed",
        "discarded_after_cancel",
    ]


class AgentRunBudgetPlan(StrictModel):
    max_logical_calls: int = 9
    reserved_logical_calls: int = Field(ge=1, le=9)
    remaining_logical_calls: int = Field(ge=0)
    max_provider_attempts: int = 12
    reserved_provider_attempts: int = Field(ge=1, le=12)
    remaining_provider_attempts: int = Field(ge=0)
    max_output_tokens: int = 20_000
    reserved_output_tokens: int = Field(ge=1, le=20_000)
    remaining_output_tokens: int = Field(ge=0)
    timeout_envelope_seconds: int = Field(ge=1)
    maximum_cost_usd: float = Field(ge=0)


class ProviderReviewResult(StrictModel):
    review: RoleReview
    provider_request_id: str | None = None
    returned_model: str | None = None
    usage: ProviderUsage = ProviderUsage()
