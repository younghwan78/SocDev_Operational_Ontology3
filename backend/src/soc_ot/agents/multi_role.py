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


class DecisionActionPlan(StrictModel):
    schema_version: Literal["decision-action-plan.v1"] = "decision-action-plan.v1"
    action_type: Literal["execute", "collect_evidence", "defer", "escalate", "reject"]
    owner: str = Field(min_length=1)
    action: str = Field(min_length=1)
    due_at_step: int = Field(ge=0)
    trigger: str = Field(min_length=1)
    verification: str = Field(min_length=1)
    fallback_action: str = Field(min_length=1)
    evidence_required: list[str] = Field(default_factory=list)
    escalation_target: str | None = None
    questions_to_resolve: list[str] = Field(default_factory=list)
    reopen_condition: str | None = None

    @model_validator(mode="after")
    def reject_blank_action_details(self) -> "DecisionActionPlan":
        required_values = (
            self.owner,
            self.action,
            self.trigger,
            self.verification,
            self.fallback_action,
        )
        optional_values = (self.escalation_target, self.reopen_condition)
        if not all(value.strip() for value in required_values):
            raise ValueError("ACTION_PLAN_DETAIL_BLANK")
        if any(value is not None and not value.strip() for value in optional_values):
            raise ValueError("ACTION_PLAN_DETAIL_BLANK")
        if any(
            not value.strip()
            for value in self.evidence_required + self.questions_to_resolve
        ):
            raise ValueError("ACTION_PLAN_DETAIL_BLANK")
        return self


class SimulatedDecision(StrictModel):
    schema_version: Literal["simulated-decision.v2"] = "simulated-decision.v2"
    case_id: str
    decision_type: DecisionType
    selected_option_id: str | None = None
    rationale: str
    safeguards: list[Safeguard]
    action_plan: DecisionActionPlan
    dissent_acknowledged: list[str]
    decision_source: Literal["deterministic_core", "simulated_chair"] = "simulated_chair"
    simulated: Literal[True] = True

    @model_validator(mode="after")
    def require_action_for_decision_type(self) -> "SimulatedDecision":
        expected_action_type = {
            DecisionType.APPROVE: "execute",
            DecisionType.APPROVE_WITH_GUARDRAILS: "execute",
            DecisionType.RUN_REVERSIBLE_TRIAL: "execute",
            DecisionType.COLLECT_MINIMUM_EVIDENCE: "collect_evidence",
            DecisionType.DEFER_UNTIL_TRIGGER: "defer",
            DecisionType.ESCALATE: "escalate",
            DecisionType.REJECT: "reject",
        }[self.decision_type]
        if self.action_plan.action_type != expected_action_type:
            raise ValueError("ACTION_TYPE_MISMATCH")
        if (
            self.decision_type is DecisionType.COLLECT_MINIMUM_EVIDENCE
            and not self.action_plan.evidence_required
        ):
            raise ValueError("COLLECT_REQUIRES_EVIDENCE_LIST")
        if self.decision_type is DecisionType.ESCALATE and not (
            self.action_plan.escalation_target
            and self.action_plan.questions_to_resolve
        ):
            raise ValueError("ESCALATE_REQUIRES_TARGET_AND_QUESTIONS")
        if (
            self.decision_type is DecisionType.REJECT
            and not self.action_plan.reopen_condition
        ):
            raise ValueError("REJECT_REQUIRES_REOPEN_CONDITION")
        return self


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
