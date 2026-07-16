from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from soc_ot.application.development_twin import (
    BlockerPropagation,
    build_development_timeline,
)
from soc_ot.application.repositories import StoredCase
from soc_ot.domain.models import Claim, DecisionCaseStatus, Evidence, StrictModel, WorkItem

DecisionListGroup = Literal[
    "ACTION_REQUIRED",
    "IN_REVIEW",
    "ACTION_AND_OBSERVATION",
    "COMPLETED",
]
DecisionAttention = Literal["OVERDUE", "DUE_NOW", "DUE_SOON", "NORMAL"]

_GROUP_LABELS: dict[DecisionListGroup, str] = {
    "ACTION_REQUIRED": "지금 확인할 결정",
    "IN_REVIEW": "검토 진행 중",
    "ACTION_AND_OBSERVATION": "실행·관찰 중",
    "COMPLETED": "완료",
}
_GROUP_ORDER: dict[DecisionListGroup, int] = {
    "ACTION_REQUIRED": 0,
    "IN_REVIEW": 1,
    "ACTION_AND_OBSERVATION": 2,
    "COMPLETED": 3,
}
_ATTENTION_ORDER: dict[DecisionAttention, int] = {
    "OVERDUE": 0,
    "DUE_NOW": 1,
    "DUE_SOON": 2,
    "NORMAL": 3,
}
_STATUS_LABELS: dict[DecisionCaseStatus, str] = {
    DecisionCaseStatus.DRAFT: "초안",
    DecisionCaseStatus.CONTEXT_BUILDING: "상황 정리 중",
    DecisionCaseStatus.OPTIONS_READY: "선택지 준비",
    DecisionCaseStatus.DECISION_REQUIRED: "결정 필요",
    DecisionCaseStatus.DECIDED: "판단 완료",
    DecisionCaseStatus.ACTIONING: "실행 중",
    DecisionCaseStatus.VERIFIED: "검증 완료",
    DecisionCaseStatus.CLOSED: "종료",
    DecisionCaseStatus.REOPENED: "재검토 필요",
}


class TrackSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    track_id: str
    name: str
    status: str
    blocker_count: int


class AlternativeSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    option_id: str
    title: str
    description: str
    reversible: bool


class BlockerSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    work_item_title: str
    track_id: str
    blocker: str
    dependency_ids: list[str]


class EvidenceSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    evidence_id: str
    title: str
    evidence_type: str
    source_ref: str
    available_at_step: int
    eligible_now: bool
    limitations: list[str]


class ClaimSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    claim_id: str
    statement: str
    epistemic_status: str
    confidence_level: str
    source_refs: list[str]


class DecisionListDeadline(StrictModel):
    milestone_title: str
    at_step: int = Field(ge=0)
    remaining_steps: int
    attention: DecisionAttention
    label_ko: str


class DecisionListBlocker(StrictModel):
    blocker_count: int = Field(ge=0)
    critical_track_name: str | None = None
    critical_work_item_title: str | None = None
    downstream_work_item_titles: list[str] = Field(default_factory=list)
    impacted_milestone_titles: list[str] = Field(default_factory=list)
    summary_ko: str


class DecisionListItemProjection(StrictModel):
    projection_schema_version: Literal["decision-list-item.v1"] = "decision-list-item.v1"
    case_id: str
    title_ko: str
    decision_question: str
    case_status: DecisionCaseStatus
    current_state_ko: str
    group: DecisionListGroup
    group_label_ko: str
    deadline: DecisionListDeadline
    why_now_ko: str
    blocker: DecisionListBlocker
    next_action: Literal["OPEN_DECISION"] = "OPEN_DECISION"
    next_action_ko: str
    stale: bool = False
    simulated: Literal[True] = True


class DecisionWorkspaceProjection(BaseModel):
    model_config = ConfigDict(frozen=True)
    projection_schema_version: str = "decision-workspace.v1"
    case_id: str
    fixture_version: int
    aggregate_version: int
    title_ko: str
    case_status: str
    current_step: int
    decision_question: str
    deadline_milestone_id: str
    deadline_title: str
    deadline_step: int
    tracks: list[TrackSummary]
    alternative_count: int
    evidence_count: int
    uncertainty_count: int
    alternatives: list[AlternativeSummary]
    blockers: list[BlockerSummary]
    eligible_evidence_titles: list[str]
    evidence: list[EvidenceSummary]
    claims: list[ClaimSummary]
    uncertainties: list[str]


def build_workspace_projection(stored: StoredCase) -> DecisionWorkspaceProjection:
    case = stored.case
    deadline = next(
        item for item in case.milestones if item.milestone_id == case.decision_deadline_milestone_id
    )
    blockers_by_track: dict[str, int] = {track.track_id: 0 for track in case.tracks}
    for item in case.work_items:
        if item.blocker:
            blockers_by_track[item.track_id] += 1
    return DecisionWorkspaceProjection(
        case_id=case.case_id,
        fixture_version=case.fixture_version,
        aggregate_version=stored.aggregate_version,
        title_ko=case.title_ko,
        case_status=case.status,
        current_step=case.current_step,
        decision_question=case.decision_question,
        deadline_milestone_id=case.decision_deadline_milestone_id,
        deadline_title=deadline.title,
        deadline_step=deadline.planned_at_step,
        tracks=[
            TrackSummary(
                track_id=track.track_id,
                name=track.name,
                status=track.status,
                blocker_count=blockers_by_track[track.track_id],
            )
            for track in case.tracks
        ],
        alternative_count=len(case.alternatives),
        evidence_count=len(case.evidence),
        uncertainty_count=len(case.uncertainties),
        alternatives=[
            AlternativeSummary(
                option_id=item.option_id,
                title=item.title,
                description=item.description,
                reversible=item.reversible,
            )
            for item in case.alternatives
        ],
        blockers=[
            BlockerSummary(
                work_item_title=item.title,
                track_id=item.track_id,
                blocker=item.blocker,
                dependency_ids=item.dependency_ids,
            )
            for item in case.work_items
            if item.blocker is not None
        ],
        eligible_evidence_titles=[
            item.title for item in case.evidence if item.available_at_step <= case.current_step
        ],
        evidence=[_evidence_summary(item, case.current_step) for item in case.evidence],
        claims=[_claim_summary(item) for item in case.claims],
        uncertainties=case.uncertainties,
    )


def build_decision_list_item(stored: StoredCase) -> DecisionListItemProjection:
    case = stored.case
    deadline = next(
        item for item in case.milestones if item.milestone_id == case.decision_deadline_milestone_id
    )
    remaining_steps = deadline.planned_at_step - case.current_step
    attention = _attention(remaining_steps)
    group = _list_group(case.status)
    timeline = build_development_timeline(stored)
    critical = _critical_blocker(timeline.blocker_propagations)
    track_names = {item.track_id: item.name for item in case.tracks}
    work_items = {item.work_item_id: item for item in case.work_items}
    blocker = _list_blocker(
        blocker_count=len([item for item in case.work_items if item.blocker]),
        critical=critical,
        track_names=track_names,
        work_items=work_items,
    )
    return DecisionListItemProjection(
        case_id=case.case_id,
        title_ko=case.title_ko,
        decision_question=case.decision_question,
        case_status=case.status,
        current_state_ko=_STATUS_LABELS[case.status],
        group=group,
        group_label_ko=_GROUP_LABELS[group],
        deadline=DecisionListDeadline(
            milestone_title=deadline.title,
            at_step=deadline.planned_at_step,
            remaining_steps=remaining_steps,
            attention=attention,
            label_ko=_deadline_label(remaining_steps),
        ),
        why_now_ko=_why_now(
            group=group,
            deadline_title=deadline.title,
            remaining_steps=remaining_steps,
            critical=critical,
        ),
        blocker=blocker,
        next_action_ko=_next_action_label(group),
    )


def sort_decision_list_items(
    items: list[DecisionListItemProjection],
) -> list[DecisionListItemProjection]:
    return sorted(
        items,
        key=lambda item: (
            _GROUP_ORDER[item.group],
            _ATTENTION_ORDER[item.deadline.attention],
            item.deadline.remaining_steps,
            -item.blocker.blocker_count,
            item.case_id,
        ),
    )


def _attention(remaining_steps: int) -> DecisionAttention:
    if remaining_steps < 0:
        return "OVERDUE"
    if remaining_steps == 0:
        return "DUE_NOW"
    if remaining_steps <= 2:
        return "DUE_SOON"
    return "NORMAL"


def _deadline_label(remaining_steps: int) -> str:
    if remaining_steps < 0:
        return f"기한 {abs(remaining_steps)} Step 경과"
    if remaining_steps == 0:
        return "이번 Step 결정"
    return f"{remaining_steps} Step 남음"


def _list_group(status: DecisionCaseStatus) -> DecisionListGroup:
    if status is DecisionCaseStatus.CLOSED:
        return "COMPLETED"
    if status in {
        DecisionCaseStatus.DECIDED,
        DecisionCaseStatus.ACTIONING,
        DecisionCaseStatus.VERIFIED,
    }:
        return "ACTION_AND_OBSERVATION"
    return "ACTION_REQUIRED"


def _critical_blocker(
    propagations: list[BlockerPropagation],
) -> BlockerPropagation | None:
    if not propagations:
        return None
    return min(
        propagations,
        key=lambda item: (
            0 if item.reaches_decision_deadline else 1,
            -len(item.downstream_work_item_ids),
            -len(item.impacted_milestone_ids),
            item.source_work_item_id,
        ),
    )


def _list_blocker(
    *,
    blocker_count: int,
    critical: BlockerPropagation | None,
    track_names: dict[str, str],
    work_items: dict[str, WorkItem],
) -> DecisionListBlocker:
    if critical is None:
        return DecisionListBlocker(blocker_count=blocker_count, summary_ko="현재 막힌 작업 없음")
    source = work_items[critical.source_work_item_id]
    if critical.downstream_work_item_titles:
        downstream = ", ".join(critical.downstream_work_item_titles[:2])
        summary = f"대기 원인: {critical.source_work_item_title}. 영향 작업: {downstream}."
    else:
        summary = f"확인 필요: {critical.source_work_item_title} ({source.blocker})."
    return DecisionListBlocker(
        blocker_count=blocker_count,
        critical_track_name=track_names[source.track_id],
        critical_work_item_title=critical.source_work_item_title,
        downstream_work_item_titles=critical.downstream_work_item_titles,
        impacted_milestone_titles=critical.impacted_milestone_titles,
        summary_ko=summary,
    )


def _why_now(
    *,
    group: DecisionListGroup,
    deadline_title: str,
    remaining_steps: int,
    critical: BlockerPropagation | None,
) -> str:
    if group == "COMPLETED":
        return "결정과 결과가 종료되어 다음 판단에 재사용할 학습을 확인할 수 있습니다."
    if group == "ACTION_AND_OBSERVATION":
        return "결정 후 action, guardrail과 다음 확인 시점을 추적해야 합니다."
    if remaining_steps < 0:
        deadline_reason = f"{deadline_title} 기한이 {abs(remaining_steps)} Step 지났습니다."
    elif remaining_steps == 0:
        deadline_reason = f"{deadline_title}가 현재 Step입니다."
    else:
        deadline_reason = f"{deadline_title}까지 {remaining_steps} Step 남았습니다."
    if critical is None:
        return deadline_reason
    if critical.downstream_work_item_titles:
        downstream = ", ".join(critical.downstream_work_item_titles[:2])
        return (
            f"{deadline_reason} "
            f"대기 원인: {critical.source_work_item_title}. 영향 작업: {downstream}."
        )
    return f"{deadline_reason} 확인 필요: {critical.source_work_item_title}."


def _next_action_label(group: DecisionListGroup) -> str:
    if group == "COMPLETED":
        return "학습 요약 보기"
    if group == "ACTION_AND_OBSERVATION":
        return "실행 상태 보기"
    return "결정 검토"


def _evidence_summary(item: Evidence, current_step: int) -> EvidenceSummary:
    return EvidenceSummary(
        evidence_id=item.evidence_id,
        title=item.title,
        evidence_type=item.evidence_type,
        source_ref=item.source_ref,
        available_at_step=item.available_at_step,
        eligible_now=item.available_at_step <= current_step,
        limitations=item.limitations,
    )


def _claim_summary(item: Claim) -> ClaimSummary:
    return ClaimSummary(
        claim_id=item.claim_id,
        statement=item.statement,
        epistemic_status=item.epistemic_status,
        confidence_level=item.confidence_level,
        source_refs=item.source_refs,
    )
