from typing import Literal

from pydantic import Field, model_validator

from soc_ot.application.hidden_boundary import assert_hidden_free
from soc_ot.domain.models import (
    DecisionCaseStatus,
    Quantity,
    StrictModel,
    WorkItemStatus,
    WorkspacePhase,
)

WorkspaceActionId = Literal[
    "BUILD_CONTEXT",
    "RUN_VIRTUAL_REVIEW",
    "VIEW_REVIEW_PROGRESS",
    "VIEW_DOSSIER",
    "RUN_SIMULATED_DECISION",
    "ADVANCE_SIMULATION",
    "VIEW_EVALUATION",
    "VIEW_LEARNING_SUMMARY",
    "REFRESH_STALE",
]

PRIMARY_ACTION_BY_PHASE: dict[WorkspacePhase, WorkspaceActionId] = {
    WorkspacePhase.CONTEXT_PREPARATION: "BUILD_CONTEXT",
    WorkspacePhase.READY_FOR_REVIEW: "RUN_VIRTUAL_REVIEW",
    WorkspacePhase.REVIEW_RUNNING: "VIEW_REVIEW_PROGRESS",
    WorkspacePhase.DOSSIER_READY: "VIEW_DOSSIER",
    WorkspacePhase.DECISION_REQUIRED: "RUN_SIMULATED_DECISION",
    WorkspacePhase.OUTCOME_RUNNING: "ADVANCE_SIMULATION",
    WorkspacePhase.EVALUATION_READY: "VIEW_EVALUATION",
    WorkspacePhase.CLOSED: "VIEW_LEARNING_SUMMARY",
}

PRIMARY_ACTION_LABELS_KO: dict[WorkspaceActionId, str] = {
    "BUILD_CONTEXT": "상황 구성",
    "RUN_VIRTUAL_REVIEW": "가상 역할 검토 실행",
    "VIEW_REVIEW_PROGRESS": "진행 상태 보기",
    "VIEW_DOSSIER": "의견 종합 보기",
    "RUN_SIMULATED_DECISION": "가상 최종 판단 실행",
    "ADVANCE_SIMULATION": "다음 Simulation Step 진행",
    "VIEW_EVALUATION": "판단 평가 보기",
    "VIEW_LEARNING_SUMMARY": "학습 요약 보기",
    "REFRESH_STALE": "최신 상태 불러오기",
}


class WorkspaceTimeContext(StrictModel):
    current_step: int = Field(ge=0)
    selected_step: int = Field(ge=0)
    mode: Literal["current", "historical"]
    earliest_available_step: int = Field(ge=0)
    latest_observable_step: int = Field(ge=0)
    next_expected_evidence_step: int | None = Field(default=None, ge=0)
    commands_allowed_at_selected_step: bool

    @model_validator(mode="after")
    def validate_time_boundary(self) -> "WorkspaceTimeContext":
        if not (
            self.earliest_available_step
            <= self.selected_step
            <= self.latest_observable_step
            <= self.current_step
        ):
            raise ValueError("WORKSPACE_STEP_BOUNDARY_INVALID")
        expected_mode = "current" if self.selected_step == self.current_step else "historical"
        if self.mode != expected_mode:
            raise ValueError("WORKSPACE_TIME_MODE_MISMATCH")
        if self.commands_allowed_at_selected_step != (self.mode == "current"):
            raise ValueError("HISTORICAL_WORKSPACE_COMMAND_FORBIDDEN")
        if (
            self.next_expected_evidence_step is not None
            and self.next_expected_evidence_step <= self.selected_step
        ):
            raise ValueError("NEXT_EVIDENCE_MUST_BE_FUTURE")
        return self


class WorkspaceDeadline(StrictModel):
    milestone_id: str
    title: str
    at_step: int = Field(ge=0)
    remaining_steps: int


class WorkspaceHeaderV2(StrictModel):
    title_ko: str = Field(min_length=1)
    decision_question: str = Field(min_length=1)
    workspace_phase: WorkspacePhase
    case_status: DecisionCaseStatus
    deadline: WorkspaceDeadline
    simulated: Literal[True] = True


class WorkspaceCurrentBrief(StrictModel):
    state_or_recommendation_ko: str = Field(min_length=1)
    one_line_reason_ko: str = Field(min_length=1)
    why_now_ko: str = Field(min_length=1)
    key_conditions_ko: list[str] = Field(default_factory=list, max_length=3)
    residual_risks_ko: list[str] = Field(default_factory=list, max_length=2)


class WorkspaceDecisionPosture(StrictModel):
    evidence_state: Literal["sufficient", "partial", "insufficient"]
    reversibility: Literal["high", "medium", "low"]
    detectability: Literal["observable_now", "observable_later", "unknown"]
    recoverability: Literal["high", "medium", "low"]
    downside: Literal["low", "medium", "high", "critical"]
    blast_radius: Literal["limited", "cross_track", "milestone", "project"]
    urgency: Literal["low", "medium", "high", "expired"]
    explanations_ko: list[str] = Field(min_length=1, max_length=7)


class WorkspaceTrackState(StrictModel):
    track_id: str
    name: str
    status: WorkItemStatus
    current_work_item_id: str
    current_work_item_title: str
    owner: str
    blocker: str | None = None
    next_milestone_id: str | None = None
    next_milestone_title: str | None = None
    next_milestone_step: int | None = Field(default=None, ge=0)


class WorkspaceStateAtStep(StrictModel):
    reconstructed_at_step: int = Field(ge=0)
    tracks: list[WorkspaceTrackState]
    eligible_evidence_ids: list[str]
    unavailable_evidence_ids: list[str]
    active_action_ids: list[str]


class WorkspaceCausalLink(StrictModel):
    relation_kind: Literal["observed", "inferred"]
    statement_ko: str = Field(min_length=1)
    source_refs: list[str] = Field(min_length=1)
    inference_basis: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_inference_basis(self) -> "WorkspaceCausalLink":
        if self.relation_kind == "inferred" and not self.inference_basis:
            raise ValueError("INFERRED_CAUSAL_LINK_REQUIRES_BASIS")
        return self


class WorkspaceCausalChain(StrictModel):
    source_event_id: str
    observed_at_step: int = Field(ge=0)
    title_ko: str = Field(min_length=1)
    links: list[WorkspaceCausalLink] = Field(min_length=1)
    impacted_milestone_ids: list[str] = Field(default_factory=list)


class WorkspaceCommitmentWindow(StrictModel):
    subject_type: Literal[
        "work_item",
        "milestone",
        "alternative",
        "interface",
        "verification_plan",
    ]
    subject_id: str
    subject_title: str
    closes_at_step: int | None = Field(default=None, ge=0)
    closes_at_milestone_id: str | None = None
    closing_reason_ko: str = Field(min_length=1)
    post_window_impact_ko: str = Field(min_length=1)
    owner: str
    switching_cost: Quantity | None = None

    @model_validator(mode="after")
    def require_window_boundary(self) -> "WorkspaceCommitmentWindow":
        if self.closes_at_step is None and self.closes_at_milestone_id is None:
            raise ValueError("COMMITMENT_WINDOW_REQUIRES_BOUNDARY")
        return self


class WorkspaceDevelopmentTwin(StrictModel):
    state_at_selected_step: WorkspaceStateAtStep
    causal_chains: list[WorkspaceCausalChain]
    commitment_windows: list[WorkspaceCommitmentWindow]
    delay_summary_ko: str = Field(min_length=1)
    recent_decision_relevant_event_ids: list[str]


class WorkspaceStateTransition(StrictModel):
    provenance: Literal["expected_model", "observed_event"]
    entity_type: Literal["action", "work_item", "milestone", "evidence"]
    entity_id: str
    entity_title: str
    from_state: str
    to_state: str
    basis_refs: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def require_state_change(self) -> "WorkspaceStateTransition":
        if self.from_state == self.to_state:
            raise ValueError("WORKSPACE_TRANSITION_REQUIRES_CHANGE")
        return self


class WorkspaceExpectedOptionTransition(StrictModel):
    option_id: str
    option_title: str
    label: Literal["expected_from_observable_model"] = "expected_from_observable_model"
    state_changes: list[WorkspaceStateTransition]
    preserved_options_ko: list[str] = Field(default_factory=list)
    lost_options_ko: list[str] = Field(default_factory=list)
    model_basis: list[str] = Field(default_factory=list)
    unknown_impacts_ko: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_expected_transition(self) -> "WorkspaceExpectedOptionTransition":
        if any(item.provenance != "expected_model" for item in self.state_changes):
            raise ValueError("EXPECTED_TRANSITION_PROVENANCE_MISMATCH")
        if self.state_changes and not self.model_basis:
            raise ValueError("EXPECTED_TRANSITION_REQUIRES_MODEL_BASIS")
        return self


class WorkspaceObservedDecisionTransitions(StrictModel):
    available: bool
    decision_id: str | None = None
    state_changes: list[WorkspaceStateTransition] = Field(default_factory=list)
    guardrail_events_ko: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_observed_transition(self) -> "WorkspaceObservedDecisionTransitions":
        if self.available:
            if self.decision_id is None or not self.state_changes:
                raise ValueError("OBSERVED_TRANSITION_REQUIRES_DECISION_AND_CHANGE")
            if any(item.provenance != "observed_event" for item in self.state_changes):
                raise ValueError("OBSERVED_TRANSITION_PROVENANCE_MISMATCH")
        elif self.decision_id or self.state_changes or self.guardrail_events_ko:
            raise ValueError("UNAVAILABLE_OBSERVED_TRANSITION_MUST_BE_EMPTY")
        return self


class WorkspaceAlternativeV2(StrictModel):
    option_id: str
    title: str
    description: str
    reversible: bool
    switching_cost: Quantity


class WorkspaceAlternativesV2(StrictModel):
    comparison_dimensions_ko: list[str] = Field(min_length=1)
    items: list[WorkspaceAlternativeV2] = Field(min_length=2)


class WorkspaceDeliberation(StrictModel):
    agreement_ko: list[str]
    dissent_ko: list[str]
    needs_confirmation_ko: list[str]
    changed_after_challenge_ko: list[str]
    key_assumptions_ko: list[str]
    key_unknowns_ko: list[str]


class WorkspaceSafeguardSummary(StrictModel):
    safeguard_id: str
    cause_ko: str
    condition_ko: str
    rollback_trigger_ko: str
    owner: str
    verification_ko: str


class WorkspaceActionPlanSummary(StrictModel):
    action_type: Literal["execute", "collect_evidence", "defer", "escalate", "reject"]
    owner: str
    action_ko: str
    due_at_step: int = Field(ge=0)
    trigger_ko: str
    verification_ko: str
    fallback_action_ko: str


class WorkspaceControls(StrictModel):
    safeguards: list[WorkspaceSafeguardSummary]
    action_plan: WorkspaceActionPlanSummary | None = None


class WorkspaceOutcomeAndEvaluation(StrictModel):
    outcome_state: Literal["not_available", "running", "available"]
    hidden_until_step_advance: bool
    expectation_vs_actual_ko: list[str] = Field(default_factory=list)
    process_evaluation_ko: str | None = None
    outcome_evaluation_ko: str | None = None
    lessons_ko: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_outcome_boundary(self) -> "WorkspaceOutcomeAndEvaluation":
        revealed = bool(
            self.expectation_vs_actual_ko
            or self.process_evaluation_ko
            or self.outcome_evaluation_ko
            or self.lessons_ko
        )
        if self.outcome_state in {"not_available", "running"} and (
            not self.hidden_until_step_advance or revealed
        ):
            raise ValueError("PRE_REVEAL_OUTCOME_MUST_REMAIN_HIDDEN")
        if self.outcome_state == "available" and self.hidden_until_step_advance:
            raise ValueError("AVAILABLE_OUTCOME_CANNOT_REMAIN_HIDDEN")
        return self


class WorkspaceWorkflow(StrictModel):
    primary_action: WorkspaceActionId | None = None
    allowed_actions: list[WorkspaceActionId]
    running_operation_ko: str | None = None

    @model_validator(mode="after")
    def validate_primary_action(self) -> "WorkspaceWorkflow":
        if len(self.allowed_actions) != len(set(self.allowed_actions)):
            raise ValueError("WORKSPACE_ALLOWED_ACTION_DUPLICATE")
        if self.primary_action is not None and self.primary_action not in self.allowed_actions:
            raise ValueError("PRIMARY_ACTION_NOT_ALLOWED")
        return self


class WorkspaceDetails(StrictModel):
    evidence_available: bool
    timeline_available: bool
    impact_path_available: bool
    role_originals_available: bool


class DecisionWorkspaceProjectionV2(StrictModel):
    projection_schema_version: Literal["decision-workspace.v2"] = "decision-workspace.v2"
    generated_at: str
    aggregate_version: int = Field(ge=0)
    case_id: str
    fixture_version: int = Field(ge=1)
    stale: bool
    time_context: WorkspaceTimeContext
    header: WorkspaceHeaderV2
    current_brief: WorkspaceCurrentBrief
    decision_posture: WorkspaceDecisionPosture
    development_twin: WorkspaceDevelopmentTwin
    expected_option_transitions: list[WorkspaceExpectedOptionTransition]
    observed_decision_transitions: WorkspaceObservedDecisionTransitions
    alternatives: WorkspaceAlternativesV2
    deliberation: WorkspaceDeliberation
    controls: WorkspaceControls
    outcome_and_evaluation: WorkspaceOutcomeAndEvaluation
    workflow: WorkspaceWorkflow
    details: WorkspaceDetails

    @model_validator(mode="after")
    def validate_workspace_boundary(self) -> "DecisionWorkspaceProjectionV2":
        selected_step = self.time_context.selected_step
        if self.development_twin.state_at_selected_step.reconstructed_at_step != selected_step:
            raise ValueError("WORKSPACE_RECONSTRUCTED_STEP_MISMATCH")
        if any(
            item.observed_at_step > selected_step
            for item in self.development_twin.causal_chains
        ):
            raise ValueError("FUTURE_CAUSAL_CHAIN_FORBIDDEN")
        option_ids = [item.option_id for item in self.alternatives.items]
        expected_option_ids = [item.option_id for item in self.expected_option_transitions]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("WORKSPACE_ALTERNATIVE_DUPLICATE")
        if len(expected_option_ids) != len(set(expected_option_ids)):
            raise ValueError("EXPECTED_OPTION_TRANSITION_DUPLICATE")
        if set(option_ids) != set(expected_option_ids):
            raise ValueError("EXPECTED_OPTION_TRANSITION_INCOMPLETE")
        expected_primary = PRIMARY_ACTION_BY_PHASE[self.header.workspace_phase]
        if not self.stale and self.workflow.primary_action != expected_primary:
            raise ValueError("WORKSPACE_PHASE_PRIMARY_ACTION_MISMATCH")
        if self.stale and self.workflow.primary_action != "REFRESH_STALE":
            raise ValueError("STALE_WORKSPACE_REQUIRES_REFRESH")
        assert_hidden_free(
            self.model_dump(mode="json"),
            error_code="HIDDEN_FIELD_IN_WORKSPACE",
        )
        return self


class WorkspacePhaseContent(StrictModel):
    phase: WorkspacePhase
    state_summary_ko: str = Field(min_length=1)
    primary_action: WorkspaceActionId
    primary_action_ko: str = Field(min_length=1)
    guidance_ko: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_phase_action(self) -> "WorkspacePhaseContent":
        expected_action = PRIMARY_ACTION_BY_PHASE[self.phase]
        if self.primary_action != expected_action:
            raise ValueError("PHASE_CONTENT_ACTION_MISMATCH")
        if self.primary_action_ko != PRIMARY_ACTION_LABELS_KO[expected_action]:
            raise ValueError("PHASE_CONTENT_LABEL_MISMATCH")
        return self


class WorkspaceUxFixture(StrictModel):
    schema_version: Literal["workspace-ux-fixture.v1"] = "workspace-ux-fixture.v1"
    content_version: int = Field(ge=1)
    case_id: str
    phase_contents: list[WorkspacePhaseContent]
    workspace_example: DecisionWorkspaceProjectionV2

    @model_validator(mode="after")
    def validate_fixture(self) -> "WorkspaceUxFixture":
        phases = [item.phase for item in self.phase_contents]
        if len(phases) != len(set(phases)) or set(phases) != set(WorkspacePhase):
            raise ValueError("WORKSPACE_PHASE_CONTENT_INCOMPLETE")
        if self.workspace_example.case_id != self.case_id:
            raise ValueError("WORKSPACE_FIXTURE_CASE_MISMATCH")
        assert_hidden_free(
            self.model_dump(mode="json"),
            error_code="HIDDEN_FIELD_IN_WORKSPACE_FIXTURE",
        )
        return self
