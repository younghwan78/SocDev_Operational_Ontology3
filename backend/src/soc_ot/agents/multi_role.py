from typing import Literal

from pydantic import Field, model_validator

from soc_ot.agents.contracts import ProviderReviewResult, ProviderUsage, RoleReview
from soc_ot.domain.models import DecisionType, Quantity, StrictModel


class ChallengerObjection(StrictModel):
    objection_id: str
    target_role_id: str
    statement: str
    claim_ids: list[str] = Field(default_factory=list)
    requested_revision: str


class ChallengerReview(StrictModel):
    schema_version: Literal["challenger-review.v1"] = "challenger-review.v1"
    objections: list[ChallengerObjection]
    no_objection_reason: str | None = None

    @model_validator(mode="after")
    def require_objection_or_reason(self) -> "ChallengerReview":
        if bool(self.objections) == bool(self.no_objection_reason):
            raise ValueError("provide objections or a no-objection reason")
        return self


class ChallengerProviderResult(StrictModel):
    challenger: ChallengerReview
    provider_request_id: str | None = None
    returned_model: str | None = None
    usage: ProviderUsage = ProviderUsage()


class ChairProviderResult(StrictModel):
    decision: "SimulatedDecision"
    provider_request_id: str | None = None
    returned_model: str | None = None
    usage: ProviderUsage = ProviderUsage()


class AgreementGroup(StrictModel):
    recommendation: DecisionType
    role_ids: list[str]


class DissentItem(StrictModel):
    role_id: str
    recommendation: DecisionType
    rationale: str


class DecisionDossier(StrictModel):
    schema_version: Literal["decision-dossier.v1"] = "decision-dossier.v1"
    case_id: str
    packet_hash: str
    original_reviews: list[RoleReview]
    challenger: ChallengerReview | None = None
    revised_reviews: list[RoleReview] = Field(default_factory=list)
    agreement_groups: list[AgreementGroup]
    dissent: list[DissentItem]
    unresolved_uncertainties: list[str]


class Safeguard(StrictModel):
    safeguard_id: str
    metric_id: str
    operator: Literal["lt", "lte", "gt", "gte", "eq"]
    threshold: Quantity
    check_at_step: int = Field(ge=0)
    expires_at_step: int = Field(ge=0)
    violation_action: Literal["rollback", "pause", "escalate", "re_review"]
    condition: str
    rollback_trigger: str
    owner: str
    verification: str


class SimulatedDecision(StrictModel):
    schema_version: Literal["simulated-decision.v1"] = "simulated-decision.v1"
    case_id: str
    decision_type: DecisionType
    selected_option_id: str | None = None
    rationale: str
    safeguards: list[Safeguard]
    dissent_acknowledged: list[str]
    decision_source: Literal["deterministic_core", "simulated_chair"] = "simulated_chair"
    simulated: Literal[True] = True


class AblationResult(StrictModel):
    topology: Literal["B0", "B1", "B2", "B3"]
    role_count: int
    challenger_used: bool
    chair_used: bool
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0)
    provider_attempts: int = Field(default=0, ge=0)
    dossier: DecisionDossier
    decision: SimulatedDecision


class DossierExecution(StrictModel):
    schema_version: Literal["dossier-execution.v1"] = "dossier-execution.v1"
    topology: Literal["B1", "B2", "B3"]
    role_count: int
    challenger_used: bool
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0)
    provider_attempts: int = Field(default=0, ge=0)
    returned_models: list[str]
    accepted_role_results: list[ProviderReviewResult] = Field(default_factory=list)
    accepted_revision_results: list[ProviderReviewResult] = Field(default_factory=list)
    challenger_provider_result: ChallengerProviderResult | None = None
    chair_provider_result: ChairProviderResult | None = None
    failed_roles: list["RoleFailure"] = Field(default_factory=list)
    failed_revisions: list["RoleFailure"] = Field(default_factory=list)
    dossier: DecisionDossier


class RoleFailure(StrictModel):
    role_id: str
    error_code: str
    provider_attempts: int = Field(default=1, ge=1)
