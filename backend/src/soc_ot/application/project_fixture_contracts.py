from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any, Literal, Protocol

from pydantic import Field, model_validator

from soc_ot.domain.models import (
    ConfidenceLevel,
    DecisionCaseStatus,
    DevelopmentEventType,
    DevelopmentTrack,
    EpistemicStatus,
    StrictModel,
    WorkItem,
    WorkItemDynamicState,
    WorkItemStateChange,
)


class ProjectLifecycleStage(StrEnum):
    SPEC_DEFINITION = "SPEC_DEFINITION"
    PRE_SILICON_CLOSURE = "PRE_SILICON_CLOSURE"
    MASS_PRODUCTION = "MASS_PRODUCTION"


class MilestoneKind(StrEnum):
    CHECKPOINT = "CHECKPOINT"
    GATE = "GATE"
    RELEASE = "RELEASE"


class MilestoneStatus(StrEnum):
    PLANNED = "PLANNED"
    AT_RISK = "AT_RISK"
    ACHIEVED = "ACHIEVED"


class IssueStatus(StrEnum):
    OPEN = "OPEN"
    MITIGATING = "MITIGATING"
    RESOLVED = "RESOLVED"


class RiskStatus(StrEnum):
    OPEN = "OPEN"
    TREATING = "TREATING"
    ACCEPTED = "ACCEPTED"
    REALIZED = "REALIZED"
    CLOSED = "CLOSED"


class ProjectAttention(StrEnum):
    ON_TRACK = "ON_TRACK"
    WATCH = "WATCH"
    AT_RISK = "AT_RISK"
    BLOCKED = "BLOCKED"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EvidenceStatus(StrEnum):
    REQUESTED = "REQUESTED"
    LATE = "LATE"
    RECEIVED = "RECEIVED"


class DevelopmentActionStatus(StrEnum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ProjectEventType(StrEnum):
    WORK_PROGRESS = DevelopmentEventType.WORK_PROGRESS
    BLOCKER_CHANGE = DevelopmentEventType.BLOCKER_CHANGE
    PLAN_CHANGE = DevelopmentEventType.PLAN_CHANGE
    DEPENDENCY_CHANGE = DevelopmentEventType.DEPENDENCY_CHANGE
    EVIDENCE_CHANGE = DevelopmentEventType.EVIDENCE_CHANGE
    REWORK = DevelopmentEventType.REWORK
    INTERFACE_CHANGE = DevelopmentEventType.INTERFACE_CHANGE
    RESOURCE_CONFLICT = DevelopmentEventType.RESOURCE_CONFLICT
    PRIORITY_CHANGE = DevelopmentEventType.PRIORITY_CHANGE
    DECISION_ACTION_PROGRESS = DevelopmentEventType.DECISION_ACTION_PROGRESS
    ISSUE_CHANGE = "ISSUE_CHANGE"
    RISK_CHANGE = "RISK_CHANGE"
    CROSS_PROJECT_PROPAGATION = "CROSS_PROJECT_PROPAGATION"


class ProjectMilestone(StrictModel):
    milestone_id: str
    title: str
    kind: MilestoneKind
    status: MilestoneStatus
    planned_at_step: int = Field(ge=0)
    commitment_at_step: int | None = Field(default=None, ge=0)


class MilestoneDynamicState(StrictModel):
    status: MilestoneStatus
    planned_at_step: int = Field(ge=0)


class MilestoneStateChange(StrictModel):
    milestone_id: str
    before: MilestoneDynamicState
    after: MilestoneDynamicState

    @model_validator(mode="after")
    def require_change(self) -> "MilestoneStateChange":
        if self.before == self.after:
            raise ValueError("milestone event must change state")
        return self


class ProjectEvidence(StrictModel):
    evidence_id: str
    title: str
    evidence_type: str
    status: EvidenceStatus
    requested_at_step: int = Field(ge=0)
    expected_at_step: int = Field(ge=0)
    available_at_step: int | None = Field(default=None, ge=0)
    source_ref: str | None = None
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_timing(self) -> "ProjectEvidence":
        if self.expected_at_step < self.requested_at_step:
            raise ValueError("evidence cannot be expected before it is requested")
        if self.status is EvidenceStatus.RECEIVED:
            if self.available_at_step is None or self.source_ref is None:
                raise ValueError("received evidence requires availability and source_ref")
        elif self.available_at_step is not None or self.source_ref is not None:
            raise ValueError("unreceived evidence cannot expose availability or source_ref")
        return self


class EvidenceDynamicState(StrictModel):
    status: EvidenceStatus
    expected_at_step: int = Field(ge=0)
    available_at_step: int | None = Field(default=None, ge=0)


class EvidenceStateChange(StrictModel):
    evidence_id: str
    before: EvidenceDynamicState
    after: EvidenceDynamicState

    @model_validator(mode="after")
    def require_change(self) -> "EvidenceStateChange":
        if self.before == self.after:
            raise ValueError("evidence event must change state")
        return self


class ProjectClaim(StrictModel):
    claim_id: str
    statement: str
    epistemic_status: EpistemicStatus
    asserted_at_step: int = Field(ge=0)
    source_refs: list[str] = Field(default_factory=list)
    inference_basis: list[str] = Field(default_factory=list)
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    owner: str | None = None
    expires_at_step: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_grounding(self) -> "ProjectClaim":
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


class DevelopmentIssue(StrictModel):
    issue_id: str
    title: str
    status: IssueStatus
    observed_at_step: int = Field(ge=0)
    source_refs: list[str] = Field(min_length=1)
    affected_work_item_ids: list[str] = Field(default_factory=list)
    affected_milestone_ids: list[str] = Field(default_factory=list)


class IssueDynamicState(StrictModel):
    status: IssueStatus


class IssueStateChange(StrictModel):
    issue_id: str
    before: IssueDynamicState
    after: IssueDynamicState

    @model_validator(mode="after")
    def require_change(self) -> "IssueStateChange":
        if self.before == self.after:
            raise ValueError("issue event must change state")
        return self


class RiskDownside(StrEnum):
    LIMITED = "LIMITED"
    MATERIAL = "MATERIAL"
    SEVERE = "SEVERE"


class RiskBlastRadius(StrEnum):
    WORK_ITEM = "WORK_ITEM"
    TRACK = "TRACK"
    PROJECT = "PROJECT"
    CROSS_PROJECT = "CROSS_PROJECT"


class RiskUrgency(StrEnum):
    MONITOR = "MONITOR"
    BEFORE_MILESTONE = "BEFORE_MILESTONE"
    IMMEDIATE = "IMMEDIATE"


class RiskReversibility(StrEnum):
    REVERSIBLE = "REVERSIBLE"
    COSTLY = "COSTLY"
    IRREVERSIBLE = "IRREVERSIBLE"


class ProjectRisk(StrictModel):
    risk_id: str
    statement: str
    status: RiskStatus
    epistemic_status: Literal[EpistemicStatus.INFERENCE, EpistemicStatus.ASSUMPTION]
    identified_at_step: int = Field(ge=0)
    source_issue_ids: list[str] = Field(default_factory=list)
    source_event_ids: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    cross_project_source_ids: list[str] = Field(default_factory=list)
    inference_basis: list[str] = Field(min_length=1)
    downside: RiskDownside
    blast_radius: RiskBlastRadius
    urgency: RiskUrgency
    reversibility: RiskReversibility
    affected_work_item_ids: list[str] = Field(default_factory=list)
    affected_milestone_ids: list[str] = Field(default_factory=list)
    treatment_decision_case_ids: list[str] = Field(default_factory=list)
    treatment_action_ids: list[str] = Field(default_factory=list)
    realized_issue_id: str | None = None

    @model_validator(mode="after")
    def validate_provenance(self) -> "ProjectRisk":
        if not any(
            (
                self.source_issue_ids,
                self.source_event_ids,
                self.source_refs,
                self.cross_project_source_ids,
            )
        ):
            raise ValueError("project risk requires at least one provenance source")
        if self.epistemic_status is EpistemicStatus.INFERENCE and not self.source_refs:
            raise ValueError("inferred project risk requires evidence source_refs")
        if self.status is RiskStatus.REALIZED and self.realized_issue_id is None:
            raise ValueError("realized project risk requires realized_issue_id")
        return self


class RiskDynamicState(StrictModel):
    status: RiskStatus
    realized_issue_id: str | None = None


class RiskStateChange(StrictModel):
    risk_id: str
    before: RiskDynamicState
    after: RiskDynamicState

    @model_validator(mode="after")
    def require_change(self) -> "RiskStateChange":
        if self.before == self.after:
            raise ValueError("risk event must change state")
        if self.after.status is RiskStatus.REALIZED and self.after.realized_issue_id is None:
            raise ValueError("realized risk state requires realized_issue_id")
        return self


class ProjectDevelopmentAction(StrictModel):
    action_id: str
    title: str
    owner: str
    status: DevelopmentActionStatus
    created_at_step: int = Field(ge=0)
    due_at_step: int = Field(ge=0)
    verification_evidence_ids: list[str] = Field(default_factory=list)
    rollback_condition: str | None = None


class ActionDynamicState(StrictModel):
    status: DevelopmentActionStatus
    due_at_step: int = Field(ge=0)


class ActionStateChange(StrictModel):
    action_id: str
    before: ActionDynamicState
    after: ActionDynamicState

    @model_validator(mode="after")
    def require_change(self) -> "ActionStateChange":
        if self.before == self.after:
            raise ValueError("action event must change state")
        return self


class DecisionCaseReference(StrictModel):
    case_id: str
    title: str
    status: DecisionCaseStatus
    opened_at_step: int = Field(ge=0)
    decision_deadline_milestone_id: str
    source_issue_ids: list[str] = Field(default_factory=list)
    treated_risk_ids: list[str] = Field(min_length=1)
    affected_work_item_ids: list[str] = Field(default_factory=list)


class CrossProjectSource(StrictModel):
    source_id: str
    source_project_id: str
    source_event_id: str
    available_at_step: int = Field(ge=0)
    lesson: str
    target_risk_ids: list[str] = Field(min_length=1)


class ProjectDevelopmentEvent(StrictModel):
    event_id: str
    event_type: ProjectEventType
    effective_at_step: int = Field(ge=0)
    observed_at_step: int = Field(ge=0)
    summary: str = Field(min_length=1)
    cause: str = Field(min_length=1)
    work_item_changes: list[WorkItemStateChange] = Field(default_factory=list)
    milestone_changes: list[MilestoneStateChange] = Field(default_factory=list)
    evidence_changes: list[EvidenceStateChange] = Field(default_factory=list)
    issue_changes: list[IssueStateChange] = Field(default_factory=list)
    risk_changes: list[RiskStateChange] = Field(default_factory=list)
    action_changes: list[ActionStateChange] = Field(default_factory=list)
    impacted_milestone_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_event(self) -> "ProjectDevelopmentEvent":
        if self.observed_at_step < self.effective_at_step:
            raise ValueError("project event cannot be observed before it is effective")
        if not any(
            (
                self.work_item_changes,
                self.milestone_changes,
                self.evidence_changes,
                self.issue_changes,
                self.risk_changes,
                self.action_changes,
            )
        ):
            raise ValueError("project event requires at least one state change")
        return self


class StateChangeProtocol(Protocol):
    @property
    def before(self) -> object: ...

    @property
    def after(self) -> object: ...


class DevelopmentProject(StrictModel):
    schema_version: Literal["development-project.v1"]
    fixture_version: int = Field(ge=1)
    project_id: str
    title_ko: str
    current_step: int = Field(ge=0)
    lifecycle_stage: ProjectLifecycleStage
    tracks: list[DevelopmentTrack]
    work_items: list[WorkItem]
    milestones: list[ProjectMilestone]
    issues: list[DevelopmentIssue]
    risks: list[ProjectRisk]
    evidence: list[ProjectEvidence]
    claims: list[ProjectClaim]
    development_actions: list[ProjectDevelopmentAction] = Field(default_factory=list)
    development_events: list[ProjectDevelopmentEvent]
    decision_case_refs: list[DecisionCaseReference]
    cross_project_sources: list[CrossProjectSource] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references_and_history(self) -> "DevelopmentProject":
        track_ids = self._unique_ids(self.tracks, "track_id")
        work_ids = self._unique_ids(self.work_items, "work_item_id")
        milestone_ids = self._unique_ids(self.milestones, "milestone_id")
        issue_ids = self._unique_ids(self.issues, "issue_id")
        risk_ids = self._unique_ids(self.risks, "risk_id")
        evidence_ids = self._unique_ids(self.evidence, "evidence_id")
        self._unique_ids(self.claims, "claim_id")
        action_ids = self._unique_ids(self.development_actions, "action_id")
        event_ids = self._unique_ids(self.development_events, "event_id")
        decision_ids = self._unique_ids(self.decision_case_refs, "case_id")
        cross_source_ids = self._unique_ids(self.cross_project_sources, "source_id")

        for item in self.work_items:
            self._require_refs({item.track_id}, track_ids, "track")
            self._require_refs(set(item.dependency_ids), work_ids, "work dependency")
        for track in self.tracks:
            if track.next_milestone_id is not None:
                self._require_refs(
                    {track.next_milestone_id}, milestone_ids, "track milestone"
                )
        self._validate_acyclic_work_items(work_ids)
        for milestone in self.milestones:
            if (
                milestone.commitment_at_step is not None
                and milestone.commitment_at_step > milestone.planned_at_step
            ):
                raise ValueError("milestone commitment cannot follow its planned step")
        evidence_by_id = {item.evidence_id: item for item in self.evidence}
        event_by_id = {item.event_id: item for item in self.development_events}
        observed_steps = [
            *(item.asserted_at_step for item in self.claims),
            *(item.observed_at_step for item in self.issues),
            *(item.identified_at_step for item in self.risks),
            *(item.requested_at_step for item in self.evidence),
            *(
                item.available_at_step
                for item in self.evidence
                if item.available_at_step is not None
            ),
            *(item.created_at_step for item in self.development_actions),
            *(item.opened_at_step for item in self.decision_case_refs),
            *(item.available_at_step for item in self.cross_project_sources),
        ]
        if any(step > self.current_step for step in observed_steps):
            raise ValueError("project fixture exposes an object from a future step")
        for claim in self.claims:
            self._require_refs(set(claim.source_refs), evidence_ids, "claim evidence")
            for evidence_id in claim.source_refs:
                available = evidence_by_id[evidence_id].available_at_step
                if available is None or claim.asserted_at_step < available:
                    raise ValueError("claim cannot precede its evidence availability")
        for issue in self.issues:
            self._require_refs(set(issue.source_refs), evidence_ids, "issue evidence")
            self._require_refs(set(issue.affected_work_item_ids), work_ids, "issue work item")
            self._require_refs(set(issue.affected_milestone_ids), milestone_ids, "issue milestone")
            for evidence_id in issue.source_refs:
                available = evidence_by_id[evidence_id].available_at_step
                if available is None or issue.observed_at_step < available:
                    raise ValueError("issue cannot precede its evidence availability")
        for risk in self.risks:
            self._require_refs(set(risk.source_issue_ids), issue_ids, "risk issue")
            self._require_refs(set(risk.source_event_ids), event_ids, "risk event")
            self._require_refs(set(risk.source_refs), evidence_ids, "risk evidence")
            self._require_refs(
                set(risk.cross_project_source_ids), cross_source_ids, "cross-project source"
            )
            self._require_refs(set(risk.affected_work_item_ids), work_ids, "risk work item")
            self._require_refs(set(risk.affected_milestone_ids), milestone_ids, "risk milestone")
            self._require_refs(
                set(risk.treatment_decision_case_ids), decision_ids, "risk decision"
            )
            self._require_refs(set(risk.treatment_action_ids), action_ids, "risk action")
            if risk.realized_issue_id is not None:
                self._require_refs({risk.realized_issue_id}, issue_ids, "realized issue")
            for evidence_id in risk.source_refs:
                available = evidence_by_id[evidence_id].available_at_step
                if available is None or risk.identified_at_step < available:
                    raise ValueError("risk cannot precede its evidence availability")
            for event_id in risk.source_event_ids:
                if risk.identified_at_step < event_by_id[event_id].observed_at_step:
                    raise ValueError("risk cannot precede its source event")
            for issue_id in risk.source_issue_ids:
                issue = next(item for item in self.issues if item.issue_id == issue_id)
                if risk.identified_at_step < issue.observed_at_step:
                    raise ValueError("risk cannot precede its source issue")
        for action in self.development_actions:
            self._require_refs(
                set(action.verification_evidence_ids), evidence_ids, "action evidence"
            )
        for decision in self.decision_case_refs:
            self._require_refs(
                {decision.decision_deadline_milestone_id},
                milestone_ids,
                "decision milestone",
            )
            self._require_refs(set(decision.source_issue_ids), issue_ids, "decision issue")
            self._require_refs(set(decision.treated_risk_ids), risk_ids, "decision risk")
            self._require_refs(
                set(decision.affected_work_item_ids), work_ids, "decision work item"
            )
            for issue_id in decision.source_issue_ids:
                issue = next(item for item in self.issues if item.issue_id == issue_id)
                if decision.opened_at_step < issue.observed_at_step:
                    raise ValueError("decision cannot precede its source issue")
            for risk_id in decision.treated_risk_ids:
                risk = next(item for item in self.risks if item.risk_id == risk_id)
                if decision.opened_at_step < risk.identified_at_step:
                    raise ValueError("decision cannot precede its treated risk")
        for source in self.cross_project_sources:
            self._require_refs(set(source.target_risk_ids), risk_ids, "cross-project target risk")
            for risk_id in source.target_risk_ids:
                risk = next(item for item in self.risks if item.risk_id == risk_id)
                if risk.identified_at_step < source.available_at_step:
                    raise ValueError("risk cannot precede its cross-project source")

        self._validate_events(
            work_ids,
            milestone_ids,
            evidence_ids,
            issue_ids,
            risk_ids,
            action_ids,
        )
        return self

    def _validate_acyclic_work_items(self, work_ids: set[str]) -> None:
        dependencies = {item.work_item_id: item.dependency_ids for item in self.work_items}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(item_id: str) -> None:
            if item_id in visiting:
                raise ValueError(f"cyclic project work dependency at {item_id}")
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

    @staticmethod
    def _unique_ids(items: Sequence[object], attribute: str) -> set[str]:
        values = [str(getattr(item, attribute)) for item in items]
        if len(values) != len(set(values)):
            raise ValueError(f"duplicate {attribute}")
        return set(values)

    @staticmethod
    def _require_refs(values: set[str], eligible: set[str], label: str) -> None:
        missing = values - eligible
        if missing:
            raise ValueError(f"unknown {label} reference: {sorted(missing)}")

    def _validate_events(
        self,
        work_ids: set[str],
        milestone_ids: set[str],
        evidence_ids: set[str],
        issue_ids: set[str],
        risk_ids: set[str],
        action_ids: set[str],
    ) -> None:
        current_states: dict[str, Mapping[str, object]] = {
            "work": {
                item.work_item_id: WorkItemDynamicState(
                    status=item.status,
                    blocker=item.blocker,
                    planned_at_step=item.planned_at_step,
                    dependency_ids=item.dependency_ids,
                )
                for item in self.work_items
            },
            "milestone": {
                item.milestone_id: MilestoneDynamicState(
                    status=item.status, planned_at_step=item.planned_at_step
                )
                for item in self.milestones
            },
            "evidence": {
                item.evidence_id: EvidenceDynamicState(
                    status=item.status,
                    expected_at_step=item.expected_at_step,
                    available_at_step=item.available_at_step,
                )
                for item in self.evidence
            },
            "issue": {item.issue_id: IssueDynamicState(status=item.status) for item in self.issues},
            "risk": {
                item.risk_id: RiskDynamicState(
                    status=item.status, realized_issue_id=item.realized_issue_id
                )
                for item in self.risks
            },
            "action": {
                item.action_id: ActionDynamicState(status=item.status, due_at_step=item.due_at_step)
                for item in self.development_actions
            },
        }
        eligible = {
            "work": work_ids,
            "milestone": milestone_ids,
            "evidence": evidence_ids,
            "issue": issue_ids,
            "risk": risk_ids,
            "action": action_ids,
        }
        chains: dict[str, dict[str, list[StateChangeProtocol]]] = {
            key: {} for key in eligible
        }
        ordered = sorted(
            self.development_events,
            key=lambda item: (item.observed_at_step, item.event_id),
        )
        for event in ordered:
            if event.observed_at_step > self.current_step:
                raise ValueError("future project event is not observable")
            self._require_refs(set(event.impacted_milestone_ids), milestone_ids, "event milestone")
            groups = (
                ("work", event.work_item_changes, "work_item_id"),
                ("milestone", event.milestone_changes, "milestone_id"),
                ("evidence", event.evidence_changes, "evidence_id"),
                ("issue", event.issue_changes, "issue_id"),
                ("risk", event.risk_changes, "risk_id"),
                ("action", event.action_changes, "action_id"),
            )
            for kind, changes, attribute in groups:
                for change in changes:
                    entity_id = str(getattr(change, attribute))
                    self._require_refs({entity_id}, eligible[kind], f"event {kind}")
                    chains[kind].setdefault(entity_id, []).append(change)
        for kind, entity_chains in chains.items():
            self._validate_chains(entity_chains, current_states[kind])

    @staticmethod
    def _validate_chains(
        chains: Mapping[str, Sequence[StateChangeProtocol]],
        current: Mapping[str, object],
    ) -> None:
        for entity_id, changes in chains.items():
            for previous, following in zip(changes, changes[1:], strict=False):
                if previous.after != following.before:
                    raise ValueError(f"project event chain is discontinuous: {entity_id}")
            if changes[-1].after != current[entity_id]:
                raise ValueError(f"project event does not match current state: {entity_id}")


class ProjectFixtureHistory(StrictModel):
    project_id: str
    at_step: int
    event_ids: list[str]
    work_item_states: dict[str, WorkItemDynamicState]
    milestone_states: dict[str, MilestoneDynamicState]
    evidence_states: dict[str, EvidenceDynamicState]
    issue_states: dict[str, IssueDynamicState]
    risk_states: dict[str, RiskDynamicState]
    action_states: dict[str, ActionDynamicState]
    available_evidence_source_refs: dict[str, str]
    claim_ids: list[str]
    decision_case_ids: list[str]
    cross_project_source_ids: list[str]


def reconstruct_project_fixture_at_step(
    project: DevelopmentProject, at_step: int
) -> ProjectFixtureHistory:
    if at_step < 0 or at_step > project.current_step:
        raise ValueError("PROJECT_STEP_OUT_OF_RANGE")

    work = {
        item.work_item_id: WorkItemDynamicState(
            status=item.status,
            blocker=item.blocker,
            planned_at_step=item.planned_at_step,
            dependency_ids=item.dependency_ids,
        )
        for item in project.work_items
    }
    milestones = {
        item.milestone_id: MilestoneDynamicState(
            status=item.status, planned_at_step=item.planned_at_step
        )
        for item in project.milestones
    }
    evidence = {
        item.evidence_id: EvidenceDynamicState(
            status=item.status,
            expected_at_step=item.expected_at_step,
            available_at_step=item.available_at_step,
        )
        for item in project.evidence
    }
    issues = {item.issue_id: IssueDynamicState(status=item.status) for item in project.issues}
    risks = {
        item.risk_id: RiskDynamicState(
            status=item.status, realized_issue_id=item.realized_issue_id
        )
        for item in project.risks
    }
    actions = {
        item.action_id: ActionDynamicState(status=item.status, due_at_step=item.due_at_step)
        for item in project.development_actions
    }
    state_groups: dict[str, dict[str, Any]] = {
        "work_item_changes": work,
        "milestone_changes": milestones,
        "evidence_changes": evidence,
        "issue_changes": issues,
        "risk_changes": risks,
        "action_changes": actions,
    }
    id_fields = {
        "work_item_changes": "work_item_id",
        "milestone_changes": "milestone_id",
        "evidence_changes": "evidence_id",
        "issue_changes": "issue_id",
        "risk_changes": "risk_id",
        "action_changes": "action_id",
    }
    for event in sorted(
        (item for item in project.development_events if item.observed_at_step > at_step),
        key=lambda item: (item.observed_at_step, item.event_id),
        reverse=True,
    ):
        for changes_field, states in state_groups.items():
            for change in reversed(getattr(event, changes_field)):
                states[str(getattr(change, id_fields[changes_field]))] = change.before

    visible_evidence = {
        item.evidence_id
        for item in project.evidence
        if item.requested_at_step <= at_step
    }
    evidence = {key: value for key, value in evidence.items() if key in visible_evidence}
    visible_issues = {item.issue_id for item in project.issues if item.observed_at_step <= at_step}
    issues = {key: value for key, value in issues.items() if key in visible_issues}
    visible_risks = {item.risk_id for item in project.risks if item.identified_at_step <= at_step}
    risks = {key: value for key, value in risks.items() if key in visible_risks}
    action_created_at = {
        item.action_id: item.created_at_step for item in project.development_actions
    }
    actions = {
        key: value
        for key, value in actions.items()
        if action_created_at[key] <= at_step
    }
    available_source_refs: dict[str, str] = {}
    for item in project.evidence:
        if item.evidence_id not in evidence:
            continue
        state = evidence[item.evidence_id]
        if (
            state.status is EvidenceStatus.RECEIVED
            and state.available_at_step is not None
            and state.available_at_step <= at_step
            and item.source_ref is not None
        ):
            available_source_refs[item.evidence_id] = item.source_ref
    return ProjectFixtureHistory(
        project_id=project.project_id,
        at_step=at_step,
        event_ids=[
            item.event_id for item in project.development_events if item.observed_at_step <= at_step
        ],
        work_item_states=work,
        milestone_states=milestones,
        evidence_states=evidence,
        issue_states=issues,
        risk_states=risks,
        action_states=actions,
        available_evidence_source_refs=available_source_refs,
        claim_ids=[item.claim_id for item in project.claims if item.asserted_at_step <= at_step],
        decision_case_ids=[
            item.case_id for item in project.decision_case_refs if item.opened_at_step <= at_step
        ],
        cross_project_source_ids=[
            item.source_id
            for item in project.cross_project_sources
            if item.available_at_step <= at_step
        ],
    )
