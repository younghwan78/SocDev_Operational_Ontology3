from typing import Literal

from pydantic import Field

from soc_ot.application.project_fixture_contracts import (
    DecisionCaseReference,
    DevelopmentProject,
    EvidenceStatus,
    IssueStatus,
    MilestoneStatus,
    ProjectAttention,
    ProjectDevelopmentEvent,
    ProjectFixtureHistory,
    ProjectRisk,
    RiskBlastRadius,
    RiskDownside,
    RiskLevel,
    RiskReversibility,
    RiskStatus,
    RiskUrgency,
    reconstruct_project_fixture_at_step,
)
from soc_ot.application.project_repositories import StoredProject
from soc_ot.domain.models import StrictModel, WorkItemStatus

PROJECT_ATTENTION_POLICY_VERSION = "project-attention.v1"
PROJECT_RISK_POLICY_VERSION = "project-risk-order.v1"

_ATTENTION_ORDER = {
    ProjectAttention.BLOCKED: 0,
    ProjectAttention.AT_RISK: 1,
    ProjectAttention.WATCH: 2,
    ProjectAttention.ON_TRACK: 3,
}
_RISK_LEVEL_ORDER = {
    RiskLevel.CRITICAL: 0,
    RiskLevel.HIGH: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.LOW: 3,
}
_RISK_STATUS_ORDER = {
    RiskStatus.REALIZED: 0,
    RiskStatus.OPEN: 1,
    RiskStatus.TREATING: 2,
    RiskStatus.ACCEPTED: 3,
    RiskStatus.CLOSED: 4,
}
_URGENCY_ORDER = {
    RiskUrgency.IMMEDIATE: 0,
    RiskUrgency.BEFORE_MILESTONE: 1,
    RiskUrgency.MONITOR: 2,
}
_DOWNSIDE_ORDER = {
    RiskDownside.SEVERE: 0,
    RiskDownside.MATERIAL: 1,
    RiskDownside.LIMITED: 2,
}
_REVERSIBILITY_ORDER = {
    RiskReversibility.IRREVERSIBLE: 0,
    RiskReversibility.COSTLY: 1,
    RiskReversibility.REVERSIBLE: 2,
}
_BLAST_ORDER = {
    RiskBlastRadius.CROSS_PROJECT: 0,
    RiskBlastRadius.PROJECT: 1,
    RiskBlastRadius.TRACK: 2,
    RiskBlastRadius.WORK_ITEM: 3,
}


class ProjectAttentionReason(StrictModel):
    code: Literal[
        "WORK_ITEM_BLOCKED",
        "CRITICAL_RISK",
        "HIGH_RISK",
        "MILESTONE_AT_RISK",
        "EVIDENCE_LATE",
        "ACTIVE_RISK",
        "NO_ACTIVE_ALERT",
    ]
    summary_ko: str
    source_refs: list[str] = Field(min_length=1)


class ProjectRiskSummary(StrictModel):
    projection_schema_version: Literal["project-risk-summary.v1"] = (
        "project-risk-summary.v1"
    )
    project_id: str
    risk_id: str
    statement: str
    status: RiskStatus
    risk_level: RiskLevel
    rank: int = Field(ge=1)
    policy_version: Literal["project-risk-order.v1"] = "project-risk-order.v1"
    ranking_reasons: list[str] = Field(min_length=1)
    source_refs: list[str] = Field(min_length=1)
    affected_work_item_ids: list[str]
    affected_milestone_ids: list[str]
    treatment_decision_case_ids: list[str]
    treatment_action_ids: list[str]
    missing_evidence_ids: list[str]


class ProjectListItemProjection(StrictModel):
    projection_schema_version: Literal["project-list-item.v1"] = "project-list-item.v1"
    project_id: str
    title_ko: str
    lifecycle_stage: str
    aggregate_version: int = Field(ge=1)
    current_step: int = Field(ge=0)
    attention: ProjectAttention
    attention_policy_version: Literal["project-attention.v1"] = "project-attention.v1"
    attention_reasons: list[ProjectAttentionReason] = Field(min_length=1)
    active_issue_count: int = Field(ge=0)
    active_risk_count: int = Field(ge=0)
    blocked_work_item_count: int = Field(ge=0)
    nearest_milestone_id: str
    nearest_milestone_step: int = Field(ge=0)
    top_risks: list[ProjectRiskSummary]


class ProjectTrackSituation(StrictModel):
    track_id: str
    name: str
    status: str
    blocked_work_item_count: int = Field(ge=0)
    next_milestone_id: str | None


class ProjectWorkItemSituation(StrictModel):
    work_item_id: str
    track_id: str
    title: str
    status: str
    blocker: str | None
    planned_at_step: int = Field(ge=0)
    dependency_ids: list[str]


class ProjectMilestoneSituation(StrictModel):
    milestone_id: str
    title: str
    kind: str
    status: MilestoneStatus
    planned_at_step: int = Field(ge=0)
    remaining_steps: int
    commitment_at_step: int | None


class ProjectIssueSituation(StrictModel):
    issue_id: str
    title: str
    status: str
    observed_at_step: int = Field(ge=0)
    source_refs: list[str]
    affected_work_item_ids: list[str]
    affected_milestone_ids: list[str]


class ProjectEvidenceSituation(StrictModel):
    evidence_id: str
    title: str
    evidence_type: str
    status: EvidenceStatus
    expected_at_step: int = Field(ge=0)
    available_at_step: int | None
    source_ref: str | None
    limitations: list[str]


class ProjectDecisionReferenceProjection(StrictModel):
    case_id: str
    title: str
    status: str
    treated_risk_ids: list[str]
    href: str


class ProjectSituationProjection(StrictModel):
    projection_schema_version: Literal["project-situation.v1"] = "project-situation.v1"
    project_id: str
    title_ko: str
    lifecycle_stage: str
    fixture_version: int = Field(ge=1)
    aggregate_version: int = Field(ge=1)
    current_step: int = Field(ge=0)
    reconstructed_at_step: int = Field(ge=0)
    attention: ProjectAttention
    attention_policy_version: Literal["project-attention.v1"] = "project-attention.v1"
    attention_reasons: list[ProjectAttentionReason] = Field(min_length=1)
    tracks: list[ProjectTrackSituation]
    work_items: list[ProjectWorkItemSituation]
    milestones: list[ProjectMilestoneSituation]
    issues: list[ProjectIssueSituation]
    risks: list[ProjectRiskSummary]
    evidence: list[ProjectEvidenceSituation]
    decision_case_refs: list[ProjectDecisionReferenceProjection]


class ProjectTimelineEventProjection(StrictModel):
    event_id: str
    event_type: str
    effective_at_step: int = Field(ge=0)
    observed_at_step: int = Field(ge=0)
    summary: str
    cause: str
    affected_entity_ids: list[str]
    impacted_milestone_ids: list[str]


class ProjectTimelineProjection(StrictModel):
    projection_schema_version: Literal["project-timeline.v1"] = "project-timeline.v1"
    project_id: str
    aggregate_version: int = Field(ge=1)
    current_step: int = Field(ge=0)
    reconstructed_at_step: int = Field(ge=0)
    attention: ProjectAttention
    events: list[ProjectTimelineEventProjection]


class RiskSourceIssueProjection(StrictModel):
    issue_id: str
    title: str
    status: str
    source_refs: list[str]


class RiskSourceEventProjection(StrictModel):
    event_id: str
    summary: str
    observed_at_step: int = Field(ge=0)


class RiskAffectedObjectProjection(StrictModel):
    object_id: str
    title: str
    object_type: Literal["WORK_ITEM", "MILESTONE"]
    state: str


class RiskCrossProjectSourceProjection(StrictModel):
    source_id: str
    source_project_id: str
    source_event_id: str
    available_at_step: int = Field(ge=0)
    lesson: str


class RiskTreatmentActionProjection(StrictModel):
    action_id: str
    title: str
    status: str
    due_at_step: int = Field(ge=0)
    verification_evidence_ids: list[str]
    rollback_condition: str | None


class ProjectRiskDetailProjection(StrictModel):
    projection_schema_version: Literal["project-risk-detail.v1"] = (
        "project-risk-detail.v1"
    )
    project_id: str
    reconstructed_at_step: int = Field(ge=0)
    risk: ProjectRiskSummary
    epistemic_status: str
    inference_basis: list[str]
    downside: str
    blast_radius: str
    urgency: str
    reversibility: str
    source_issues: list[RiskSourceIssueProjection]
    source_events: list[RiskSourceEventProjection]
    source_evidence: list[ProjectEvidenceSituation]
    cross_project_sources: list[RiskCrossProjectSourceProjection]
    affected_objects: list[RiskAffectedObjectProjection]
    decisions: list[ProjectDecisionReferenceProjection]
    treatment_actions: list[RiskTreatmentActionProjection]


def build_project_list_item(stored: StoredProject) -> ProjectListItemProjection:
    situation = build_project_situation(stored)
    nearest = min(situation.milestones, key=lambda item: (item.planned_at_step, item.milestone_id))
    return ProjectListItemProjection(
        project_id=situation.project_id,
        title_ko=situation.title_ko,
        lifecycle_stage=situation.lifecycle_stage,
        aggregate_version=situation.aggregate_version,
        current_step=situation.current_step,
        attention=situation.attention,
        attention_reasons=situation.attention_reasons,
        active_issue_count=len(
            [item for item in situation.issues if item.status != IssueStatus.RESOLVED]
        ),
        active_risk_count=len(
            [item for item in situation.risks if item.status != RiskStatus.CLOSED]
        ),
        blocked_work_item_count=len(
            [item for item in situation.work_items if item.status == WorkItemStatus.BLOCKED]
        ),
        nearest_milestone_id=nearest.milestone_id,
        nearest_milestone_step=nearest.planned_at_step,
        top_risks=situation.risks[:2],
    )


def sort_project_list_items(
    items: list[ProjectListItemProjection],
) -> list[ProjectListItemProjection]:
    return sorted(
        items,
        key=lambda item: (
            _ATTENTION_ORDER[item.attention],
            item.nearest_milestone_step - item.current_step,
            item.project_id,
        ),
    )


def build_project_situation(
    stored: StoredProject, *, at_step: int | None = None
) -> ProjectSituationProjection:
    project = stored.project
    requested_step = project.current_step if at_step is None else at_step
    history = reconstruct_project_fixture_at_step(project, requested_step)
    risks = _risk_summaries(project, history)
    attention, reasons = _project_attention(project, history, risks)
    visible_issue_ids = set(history.issue_states)
    visible_evidence_ids = set(history.evidence_states)
    visible_decision_ids = set(history.decision_case_ids)
    return ProjectSituationProjection(
        project_id=project.project_id,
        title_ko=project.title_ko,
        lifecycle_stage=project.lifecycle_stage,
        fixture_version=project.fixture_version,
        aggregate_version=stored.aggregate_version,
        current_step=project.current_step,
        reconstructed_at_step=requested_step,
        attention=attention,
        attention_reasons=reasons,
        tracks=[_track_situation(project, history, item.track_id) for item in project.tracks],
        work_items=[
            ProjectWorkItemSituation(
                work_item_id=item.work_item_id,
                track_id=item.track_id,
                title=item.title,
                status=history.work_item_states[item.work_item_id].status,
                blocker=history.work_item_states[item.work_item_id].blocker,
                planned_at_step=history.work_item_states[item.work_item_id].planned_at_step,
                dependency_ids=history.work_item_states[item.work_item_id].dependency_ids,
            )
            for item in project.work_items
        ],
        milestones=[
            ProjectMilestoneSituation(
                milestone_id=item.milestone_id,
                title=item.title,
                kind=item.kind,
                status=history.milestone_states[item.milestone_id].status,
                planned_at_step=history.milestone_states[item.milestone_id].planned_at_step,
                remaining_steps=(
                    history.milestone_states[item.milestone_id].planned_at_step - requested_step
                ),
                commitment_at_step=item.commitment_at_step,
            )
            for item in project.milestones
        ],
        issues=[
            ProjectIssueSituation(
                issue_id=item.issue_id,
                title=item.title,
                status=history.issue_states[item.issue_id].status,
                observed_at_step=item.observed_at_step,
                source_refs=item.source_refs,
                affected_work_item_ids=item.affected_work_item_ids,
                affected_milestone_ids=item.affected_milestone_ids,
            )
            for item in project.issues
            if item.issue_id in visible_issue_ids
        ],
        risks=risks,
        evidence=[
            _evidence_situation(project, history, item.evidence_id)
            for item in project.evidence
            if item.evidence_id in visible_evidence_ids
        ],
        decision_case_refs=[
            _decision_projection(item)
            for item in project.decision_case_refs
            if item.case_id in visible_decision_ids
        ],
    )


def build_project_risks(
    stored: StoredProject, *, at_step: int | None = None
) -> list[ProjectRiskSummary]:
    project = stored.project
    requested_step = project.current_step if at_step is None else at_step
    history = reconstruct_project_fixture_at_step(project, requested_step)
    return _risk_summaries(project, history)


def build_project_risk_detail(
    stored: StoredProject,
    risk_id: str,
    *,
    at_step: int | None = None,
) -> ProjectRiskDetailProjection:
    project = stored.project
    requested_step = project.current_step if at_step is None else at_step
    history = reconstruct_project_fixture_at_step(project, requested_step)
    summaries = _risk_summaries(project, history)
    summary = next((item for item in summaries if item.risk_id == risk_id), None)
    if summary is None:
        raise ValueError("PROJECT_RISK_NOT_FOUND")
    risk = next(item for item in project.risks if item.risk_id == risk_id)
    issue_by_id = {item.issue_id: item for item in project.issues}
    event_by_id = {item.event_id: item for item in project.development_events}
    work_by_id = {item.work_item_id: item for item in project.work_items}
    milestone_by_id = {item.milestone_id: item for item in project.milestones}
    decisions = {item.case_id: item for item in project.decision_case_refs}
    cross_sources = {item.source_id: item for item in project.cross_project_sources}
    actions = {item.action_id: item for item in project.development_actions}
    visible_events = set(history.event_ids)
    return ProjectRiskDetailProjection(
        project_id=project.project_id,
        reconstructed_at_step=requested_step,
        risk=summary,
        epistemic_status=risk.epistemic_status,
        inference_basis=risk.inference_basis,
        downside=risk.downside,
        blast_radius=risk.blast_radius,
        urgency=risk.urgency,
        reversibility=risk.reversibility,
        source_issues=[
            RiskSourceIssueProjection(
                issue_id=issue_id,
                title=issue_by_id[issue_id].title,
                status=history.issue_states[issue_id].status,
                source_refs=issue_by_id[issue_id].source_refs,
            )
            for issue_id in risk.source_issue_ids
            if issue_id in history.issue_states
        ],
        source_events=[
            RiskSourceEventProjection(
                event_id=event_id,
                summary=event_by_id[event_id].summary,
                observed_at_step=event_by_id[event_id].observed_at_step,
            )
            for event_id in risk.source_event_ids
            if event_id in visible_events
        ],
        source_evidence=[
            _evidence_situation(project, history, evidence_id)
            for evidence_id in risk.source_refs
            if evidence_id in history.evidence_states
        ],
        cross_project_sources=[
            RiskCrossProjectSourceProjection(
                source_id=source_id,
                source_project_id=cross_sources[source_id].source_project_id,
                source_event_id=cross_sources[source_id].source_event_id,
                available_at_step=cross_sources[source_id].available_at_step,
                lesson=cross_sources[source_id].lesson,
            )
            for source_id in risk.cross_project_source_ids
            if source_id in history.cross_project_source_ids
        ],
        affected_objects=[
            *[
                RiskAffectedObjectProjection(
                    object_id=work_id,
                    title=work_by_id[work_id].title,
                    object_type="WORK_ITEM",
                    state=history.work_item_states[work_id].status,
                )
                for work_id in risk.affected_work_item_ids
            ],
            *[
                RiskAffectedObjectProjection(
                    object_id=milestone_id,
                    title=milestone_by_id[milestone_id].title,
                    object_type="MILESTONE",
                    state=history.milestone_states[milestone_id].status,
                )
                for milestone_id in risk.affected_milestone_ids
            ],
        ],
        decisions=[
            _decision_projection(decisions[case_id])
            for case_id in risk.treatment_decision_case_ids
            if case_id in history.decision_case_ids
        ],
        treatment_actions=[
            RiskTreatmentActionProjection(
                action_id=action_id,
                title=actions[action_id].title,
                status=history.action_states[action_id].status,
                due_at_step=history.action_states[action_id].due_at_step,
                verification_evidence_ids=actions[action_id].verification_evidence_ids,
                rollback_condition=actions[action_id].rollback_condition,
            )
            for action_id in risk.treatment_action_ids
            if action_id in history.action_states
        ],
    )


def build_project_timeline(
    stored: StoredProject, *, at_step: int | None = None
) -> ProjectTimelineProjection:
    situation = build_project_situation(stored, at_step=at_step)
    visible_event_ids = {
        item.event_id
        for item in stored.project.development_events
        if item.observed_at_step <= situation.reconstructed_at_step
    }
    return ProjectTimelineProjection(
        project_id=stored.project.project_id,
        aggregate_version=stored.aggregate_version,
        current_step=stored.project.current_step,
        reconstructed_at_step=situation.reconstructed_at_step,
        attention=situation.attention,
        events=[
            _timeline_event(item)
            for item in stored.project.development_events
            if item.event_id in visible_event_ids
        ],
    )


def _risk_summaries(
    project: DevelopmentProject, history: ProjectFixtureHistory
) -> list[ProjectRiskSummary]:
    visible_risks = [item for item in project.risks if item.risk_id in history.risk_states]
    ordered = sorted(
        visible_risks,
        key=lambda item: _risk_sort_key(
            item.model_copy(
                update={
                    "status": history.risk_states[item.risk_id].status,
                    "realized_issue_id": history.risk_states[item.risk_id].realized_issue_id,
                }
            ),
            project,
        ),
    )
    return [
        _risk_summary(project, history, item, rank=index)
        for index, item in enumerate(ordered, start=1)
    ]


def _risk_sort_key(risk: ProjectRisk, project: DevelopmentProject) -> tuple[object, ...]:
    milestone_steps = {
        item.milestone_id: item.planned_at_step for item in project.milestones
    }
    nearest_impact = min(
        (milestone_steps[item] for item in risk.affected_milestone_ids),
        default=project.current_step + 999,
    )
    risk_level, _ = _risk_level(risk)
    return (
        _RISK_LEVEL_ORDER[risk_level],
        _RISK_STATUS_ORDER[risk.status],
        _URGENCY_ORDER[risk.urgency],
        _DOWNSIDE_ORDER[risk.downside],
        _REVERSIBILITY_ORDER[risk.reversibility],
        _BLAST_ORDER[risk.blast_radius],
        nearest_impact,
        risk.risk_id,
    )


def _risk_summary(
    project: DevelopmentProject,
    history: ProjectFixtureHistory,
    risk: ProjectRisk,
    *,
    rank: int,
) -> ProjectRiskSummary:
    state = history.risk_states[risk.risk_id]
    current_risk = risk.model_copy(
        update={"status": state.status, "realized_issue_id": state.realized_issue_id}
    )
    level, reasons = _risk_level(current_risk)
    missing_evidence = {
        evidence_id
        for action in project.development_actions
        if action.action_id in risk.treatment_action_ids
        for evidence_id in action.verification_evidence_ids
        if evidence_id not in history.evidence_states
        or history.evidence_states[evidence_id].status is not EvidenceStatus.RECEIVED
    }
    source_refs = sorted(
        {
            *risk.source_issue_ids,
            *risk.source_event_ids,
            *risk.source_refs,
            *risk.cross_project_source_ids,
        }
    )
    return ProjectRiskSummary(
        project_id=project.project_id,
        risk_id=risk.risk_id,
        statement=risk.statement,
        status=state.status,
        risk_level=level,
        rank=rank,
        ranking_reasons=reasons,
        source_refs=source_refs,
        affected_work_item_ids=risk.affected_work_item_ids,
        affected_milestone_ids=risk.affected_milestone_ids,
        treatment_decision_case_ids=[
            item for item in risk.treatment_decision_case_ids if item in history.decision_case_ids
        ],
        treatment_action_ids=[
            item for item in risk.treatment_action_ids if item in history.action_states
        ],
        missing_evidence_ids=sorted(missing_evidence),
    )


def _risk_level(risk: ProjectRisk) -> tuple[RiskLevel, list[str]]:
    if risk.status is RiskStatus.CLOSED:
        return RiskLevel.LOW, ["RISK_CLOSED"]
    if risk.status is RiskStatus.REALIZED:
        return RiskLevel.CRITICAL, ["RISK_REALIZED"]
    reasons = [f"DOWNSIDE_{risk.downside}", f"URGENCY_{risk.urgency}"]
    if risk.reversibility is RiskReversibility.IRREVERSIBLE:
        reasons.append("IRREVERSIBLE_COMMITMENT")
    if risk.blast_radius is RiskBlastRadius.CROSS_PROJECT:
        reasons.append("CROSS_PROJECT_BLAST_RADIUS")
    if risk.downside is RiskDownside.SEVERE and (
        risk.urgency is RiskUrgency.IMMEDIATE
        or risk.reversibility is RiskReversibility.IRREVERSIBLE
    ):
        return RiskLevel.CRITICAL, reasons
    if (
        risk.downside is RiskDownside.SEVERE
        or risk.urgency is RiskUrgency.IMMEDIATE
        or risk.blast_radius is RiskBlastRadius.CROSS_PROJECT
    ):
        return RiskLevel.HIGH, reasons
    if risk.downside is RiskDownside.MATERIAL or risk.urgency is RiskUrgency.BEFORE_MILESTONE:
        return RiskLevel.MEDIUM, reasons
    return RiskLevel.LOW, reasons


def _project_attention(
    project: DevelopmentProject,
    history: ProjectFixtureHistory,
    risks: list[ProjectRiskSummary],
) -> tuple[ProjectAttention, list[ProjectAttentionReason]]:
    blocked = sorted(
        item_id
        for item_id, state in history.work_item_states.items()
        if state.status is WorkItemStatus.BLOCKED
    )
    if blocked:
        return ProjectAttention.BLOCKED, [
            ProjectAttentionReason(
                code="WORK_ITEM_BLOCKED",
                summary_ko=f"현재 진행이 막힌 작업이 {len(blocked)}개 있습니다.",
                source_refs=blocked,
            )
        ]
    active_critical = [
        item.risk_id
        for item in risks
        if item.status is not RiskStatus.CLOSED and item.risk_level is RiskLevel.CRITICAL
    ]
    if active_critical:
        return ProjectAttention.AT_RISK, [
            ProjectAttentionReason(
                code="CRITICAL_RISK",
                summary_ko="현실화되었거나 비가역 commitment에 가까운 위험이 있습니다.",
                source_refs=active_critical,
            )
        ]
    active_high = [
        item.risk_id
        for item in risks
        if item.status is not RiskStatus.CLOSED and item.risk_level is RiskLevel.HIGH
    ]
    at_risk_milestones = sorted(
        item_id
        for item_id, state in history.milestone_states.items()
        if state.status is MilestoneStatus.AT_RISK
    )
    if active_high or at_risk_milestones:
        reasons = []
        if active_high:
            reasons.append(
                ProjectAttentionReason(
                    code="HIGH_RISK",
                    summary_ko="높은 downside 또는 넓은 영향 범위의 위험이 있습니다.",
                    source_refs=active_high,
                )
            )
        if at_risk_milestones:
            reasons.append(
                ProjectAttentionReason(
                    code="MILESTONE_AT_RISK",
                    summary_ko="계획 대비 위험 상태인 milestone이 있습니다.",
                    source_refs=at_risk_milestones,
                )
            )
        return ProjectAttention.AT_RISK, reasons
    late_evidence = sorted(
        item_id
        for item_id, state in history.evidence_states.items()
        if state.status is EvidenceStatus.LATE
    )
    active_risks = [item.risk_id for item in risks if item.status is not RiskStatus.CLOSED]
    if late_evidence:
        return ProjectAttention.WATCH, [
            ProjectAttentionReason(
                code="EVIDENCE_LATE",
                summary_ko="예정 시점까지 도착하지 않은 근거가 있습니다.",
                source_refs=late_evidence,
            )
        ]
    if active_risks:
        return ProjectAttention.WATCH, [
            ProjectAttentionReason(
                code="ACTIVE_RISK",
                summary_ko="추적 중인 위험이 있으나 현재 작업을 막지는 않습니다.",
                source_refs=active_risks,
            )
        ]
    return ProjectAttention.ON_TRACK, [
        ProjectAttentionReason(
            code="NO_ACTIVE_ALERT",
            summary_ko="현재 관측 범위에서 즉시 대응할 경보가 없습니다.",
            source_refs=[project.project_id],
        )
    ]


def _track_situation(
    project: DevelopmentProject, history: ProjectFixtureHistory, track_id: str
) -> ProjectTrackSituation:
    track = next(item for item in project.tracks if item.track_id == track_id)
    work_ids = [item.work_item_id for item in project.work_items if item.track_id == track_id]
    blocked_count = len(
        [
            item_id
            for item_id in work_ids
            if history.work_item_states[item_id].status is WorkItemStatus.BLOCKED
        ]
    )
    work_states = [history.work_item_states[item_id].status for item_id in work_ids]
    if WorkItemStatus.BLOCKED in work_states:
        track_status = WorkItemStatus.BLOCKED
    elif WorkItemStatus.REWORK in work_states:
        track_status = WorkItemStatus.REWORK
    elif WorkItemStatus.IN_PROGRESS in work_states:
        track_status = WorkItemStatus.IN_PROGRESS
    elif work_states and all(
        item in {WorkItemStatus.DONE, WorkItemStatus.VERIFIED} for item in work_states
    ):
        track_status = WorkItemStatus.VERIFIED
    elif WorkItemStatus.READY in work_states:
        track_status = WorkItemStatus.READY
    elif WorkItemStatus.PLANNED in work_states:
        track_status = WorkItemStatus.PLANNED
    else:
        track_status = track.status
    return ProjectTrackSituation(
        track_id=track.track_id,
        name=track.name,
        status=track_status,
        blocked_work_item_count=blocked_count,
        next_milestone_id=track.next_milestone_id,
    )


def _evidence_situation(
    project: DevelopmentProject, history: ProjectFixtureHistory, evidence_id: str
) -> ProjectEvidenceSituation:
    evidence = next(item for item in project.evidence if item.evidence_id == evidence_id)
    state = history.evidence_states[evidence_id]
    return ProjectEvidenceSituation(
        evidence_id=evidence.evidence_id,
        title=evidence.title,
        evidence_type=evidence.evidence_type,
        status=state.status,
        expected_at_step=state.expected_at_step,
        available_at_step=state.available_at_step,
        source_ref=history.available_evidence_source_refs.get(evidence_id),
        limitations=evidence.limitations,
    )


def _decision_projection(
    item: DecisionCaseReference,
) -> ProjectDecisionReferenceProjection:
    case_id = item.case_id
    return ProjectDecisionReferenceProjection(
        case_id=case_id,
        title=item.title,
        status=item.status,
        treated_risk_ids=item.treated_risk_ids,
        href=f"/decisions/{case_id}",
    )


def _timeline_event(event: ProjectDevelopmentEvent) -> ProjectTimelineEventProjection:
    affected = [item.work_item_id for item in event.work_item_changes]
    affected.extend(item.milestone_id for item in event.milestone_changes)
    affected.extend(item.evidence_id for item in event.evidence_changes)
    affected.extend(item.issue_id for item in event.issue_changes)
    affected.extend(item.risk_id for item in event.risk_changes)
    affected.extend(item.action_id for item in event.action_changes)
    return ProjectTimelineEventProjection(
        event_id=event.event_id,
        event_type=event.event_type,
        effective_at_step=event.effective_at_step,
        observed_at_step=event.observed_at_step,
        summary=event.summary,
        cause=event.cause,
        affected_entity_ids=sorted(set(affected)),
        impacted_milestone_ids=event.impacted_milestone_ids,
    )
