from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DecisionCaseStatus(StrEnum):
    DRAFT = "DRAFT"
    CONTEXT_BUILDING = "CONTEXT_BUILDING"
    OPTIONS_READY = "OPTIONS_READY"
    DECISION_REQUIRED = "DECISION_REQUIRED"
    DECIDED = "DECIDED"
    ACTIONING = "ACTIONING"
    VERIFIED = "VERIFIED"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"


class DecisionType(StrEnum):
    APPROVE = "APPROVE"
    APPROVE_WITH_GUARDRAILS = "APPROVE_WITH_GUARDRAILS"
    RUN_REVERSIBLE_TRIAL = "RUN_REVERSIBLE_TRIAL"
    COLLECT_MINIMUM_EVIDENCE = "COLLECT_MINIMUM_EVIDENCE"
    DEFER_UNTIL_TRIGGER = "DEFER_UNTIL_TRIGGER"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"


class AgentRunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WorkspacePhase(StrEnum):
    CONTEXT_PREPARATION = "CONTEXT_PREPARATION"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    REVIEW_RUNNING = "REVIEW_RUNNING"
    DOSSIER_READY = "DOSSIER_READY"
    DECISION_REQUIRED = "DECISION_REQUIRED"
    OUTCOME_RUNNING = "OUTCOME_RUNNING"
    EVALUATION_READY = "EVALUATION_READY"
    CLOSED = "CLOSED"


class WorkItemStatus(StrEnum):
    PLANNED = "PLANNED"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    DONE = "DONE"
    VERIFIED = "VERIFIED"
    REWORK = "REWORK"
    CANCELLED = "CANCELLED"


class EpistemicStatus(StrEnum):
    FACT = "fact"
    INFERENCE = "inference"
    ASSUMPTION = "assumption"
    UNKNOWN = "unknown"


class ConfidenceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class QuantityMode(StrEnum):
    EXACT = "exact"
    RANGE = "range"
    QUALITATIVE = "qualitative"
    UNKNOWN = "unknown"


CanonicalUnit = Literal[
    "mW", "mJ", "GB/s", "Mbps", "ms", "fps", "degC", "mm2", "ratio", "count",
    "person_day", "step"
]


class Quantity(StrictModel):
    mode: QuantityMode
    unit: CanonicalUnit
    value: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    qualitative: Literal["low", "medium", "high", "critical"] | None = None

    @model_validator(mode="after")
    def validate_mode(self) -> "Quantity":
        numeric = self.value is not None
        bounds = self.lower_bound is not None or self.upper_bound is not None
        if self.mode is QuantityMode.EXACT and (not numeric or bounds or self.qualitative):
            raise ValueError("exact quantity requires only value")
        if self.mode is QuantityMode.RANGE and (
            self.lower_bound is None
            or self.upper_bound is None
            or self.lower_bound > self.upper_bound
            or numeric
            or self.qualitative
        ):
            raise ValueError("range quantity requires ordered lower/upper bounds only")
        if self.mode is QuantityMode.QUALITATIVE and (
            self.qualitative is None or numeric or bounds
        ):
            raise ValueError("qualitative quantity requires only qualitative")
        if self.mode is QuantityMode.UNKNOWN and (numeric or bounds or self.qualitative):
            raise ValueError("unknown quantity cannot carry a value")
        return self


class Claim(StrictModel):
    claim_id: str
    statement: str
    epistemic_status: EpistemicStatus
    source_refs: list[str] = Field(default_factory=list)
    inference_basis: list[str] = Field(default_factory=list)
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    owner: str | None = None
    expires_at_step: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_grounding(self) -> "Claim":
        if self.epistemic_status is EpistemicStatus.FACT and not self.source_refs:
            raise ValueError("fact requires source_refs")
        if self.epistemic_status is EpistemicStatus.INFERENCE and (
            not self.source_refs or not self.inference_basis
        ):
            raise ValueError("inference requires source_refs and inference_basis")
        if self.epistemic_status is EpistemicStatus.ASSUMPTION and not (
            self.owner or self.expires_at_step is not None
        ):
            raise ValueError("assumption requires owner or expires_at_step")
        return self


class Evidence(StrictModel):
    evidence_id: str
    title: str
    evidence_type: str
    source_ref: str
    available_at_step: int = Field(ge=0)
    quantity: Quantity | None = None
    limitations: list[str] = Field(default_factory=list)


class DevelopmentTrack(StrictModel):
    track_id: str
    name: str
    status: WorkItemStatus
    next_milestone_id: str | None = None


class WorkItem(StrictModel):
    work_item_id: str
    track_id: str
    title: str
    status: WorkItemStatus
    owner: str
    dependency_ids: list[str] = Field(default_factory=list)
    blocker: str | None = None
    planned_at_step: int = Field(ge=0)
    effective_at_step: int | None = Field(default=None, ge=0)


class Milestone(StrictModel):
    milestone_id: str
    title: str
    planned_at_step: int = Field(ge=0)


class Alternative(StrictModel):
    option_id: str
    title: str
    description: str
    reversible: bool
    switching_cost: Quantity
    claim_ids: list[str] = Field(default_factory=list)


class Guardrail(StrictModel):
    guardrail_id: str
    metric_id: str
    operator: Literal["lt", "lte", "gt", "gte", "eq"]
    threshold: Quantity
    check_at_steps: list[int]
    violation_action: Literal["rollback", "pause", "escalate", "re_review"]
    action_owner: str


class ObservableCase(StrictModel):
    schema_version: Literal["observable-case.v1"]
    fixture_version: int = Field(ge=1)
    case_id: str
    title_ko: str
    current_step: int = Field(ge=0)
    status: DecisionCaseStatus
    decision_question: str
    decision_deadline_milestone_id: str
    tracks: list[DevelopmentTrack]
    work_items: list[WorkItem]
    milestones: list[Milestone]
    evidence: list[Evidence]
    claims: list[Claim]
    uncertainties: list[str]
    alternatives: Annotated[list[Alternative], Field(min_length=2)]
    required_role_ids: list[str]
    allowed_decision_types: list[DecisionType]

    @model_validator(mode="after")
    def validate_references(self) -> "ObservableCase":
        track_ids = {item.track_id for item in self.tracks}
        work_ids = {item.work_item_id for item in self.work_items}
        milestone_ids = {item.milestone_id for item in self.milestones}
        evidence_ids = {item.evidence_id for item in self.evidence}
        claim_ids = {item.claim_id for item in self.claims}
        if len(track_ids) != len(self.tracks) or len(work_ids) != len(self.work_items):
            raise ValueError("duplicate track or work item id")
        if self.decision_deadline_milestone_id not in milestone_ids:
            raise ValueError("decision deadline milestone is missing")
        for item in self.work_items:
            if item.track_id not in track_ids:
                raise ValueError(f"unknown track reference: {item.track_id}")
            missing = set(item.dependency_ids) - work_ids
            if missing:
                raise ValueError(f"dangling work dependency: {sorted(missing)}")
        for claim in self.claims:
            missing = set(claim.source_refs) - evidence_ids
            if missing:
                raise ValueError(f"dangling evidence reference: {sorted(missing)}")
        for alternative in self.alternatives:
            missing = set(alternative.claim_ids) - claim_ids
            if missing:
                raise ValueError(f"dangling claim reference: {sorted(missing)}")
        self._validate_acyclic(work_ids)
        return self

    def _validate_acyclic(self, work_ids: set[str]) -> None:
        dependencies = {item.work_item_id: item.dependency_ids for item in self.work_items}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(item_id: str) -> None:
            if item_id in visiting:
                raise ValueError(f"cyclic work dependency at {item_id}")
            if item_id in visited:
                return
            visiting.add(item_id)
            for dependency_id in dependencies.get(item_id, []):
                if dependency_id in work_ids:
                    visit(dependency_id)
            visiting.remove(item_id)
            visited.add(item_id)

        for work_id in work_ids:
            visit(work_id)


class OutcomePath(StrictModel):
    option_id: str
    rule_id: str
    parameters: dict[str, str | int | float | bool]


class HiddenCase(StrictModel):
    schema_version: Literal["hidden-case.v1"]
    fixture_version: int = Field(ge=1)
    case_id: str
    hidden_root_causes: list[str]
    outcome_paths: list[OutcomePath]


class ExpectedResult(StrictModel):
    schema_version: Literal["expected-result.v1"]
    fixture_version: int = Field(ge=1)
    case_id: str
    acceptable_decision_types: list[DecisionType]
    unacceptable_decision_types: list[DecisionType]
    mandatory_claim_ids: list[str]
    mandatory_dependency_ids: list[str]
    mandatory_guardrail_metric_ids: list[str]


ALLOWED_WORK_TRANSITIONS: dict[WorkItemStatus, set[WorkItemStatus]] = {
    WorkItemStatus.PLANNED: {WorkItemStatus.READY, WorkItemStatus.CANCELLED},
    WorkItemStatus.READY: {
        WorkItemStatus.IN_PROGRESS,
        WorkItemStatus.BLOCKED,
        WorkItemStatus.CANCELLED,
    },
    WorkItemStatus.IN_PROGRESS: {
        WorkItemStatus.DONE,
        WorkItemStatus.BLOCKED,
        WorkItemStatus.CANCELLED,
    },
    WorkItemStatus.BLOCKED: {WorkItemStatus.IN_PROGRESS, WorkItemStatus.CANCELLED},
    WorkItemStatus.DONE: {WorkItemStatus.VERIFIED, WorkItemStatus.REWORK},
    WorkItemStatus.VERIFIED: {WorkItemStatus.REWORK},
    WorkItemStatus.REWORK: {WorkItemStatus.IN_PROGRESS, WorkItemStatus.CANCELLED},
    WorkItemStatus.CANCELLED: set(),
}


def validate_work_transition(before: WorkItemStatus, after: WorkItemStatus) -> None:
    if after not in ALLOWED_WORK_TRANSITIONS[before]:
        raise ValueError(f"invalid work transition: {before} -> {after}")

