from pydantic import BaseModel, ConfigDict

from soc_ot.application.repositories import StoredCase
from soc_ot.domain.models import (
    DevelopmentAction,
    DevelopmentActionDynamicState,
    DevelopmentEvent,
    EvidenceDynamicState,
    MilestoneDynamicState,
    ObservableCase,
    WorkItemDynamicState,
)


class TimelineWorkItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    work_item_id: str
    track_id: str
    title: str
    status: str
    blocker: str | None
    planned_at_step: int
    dependency_ids: list[str]


class TimelineMilestone(BaseModel):
    model_config = ConfigDict(frozen=True)

    milestone_id: str
    title: str
    planned_at_step: int


class TimelineEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    title: str
    available_at_step: int
    eligible_at_step: bool


class TimelineAction(BaseModel):
    model_config = ConfigDict(frozen=True)

    action_id: str
    title: str
    owner: str
    status: str
    due_at_step: int
    blocker: str | None


class TimelineEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str
    event_type: str
    effective_at_step: int
    observed_at_step: int
    summary: str
    cause: str
    affected_entity_ids: list[str]
    impacted_milestone_ids: list[str]


class BlockerPropagation(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_work_item_id: str
    source_work_item_title: str
    downstream_work_item_ids: list[str]
    downstream_work_item_titles: list[str]
    impacted_track_ids: list[str]
    impacted_milestone_ids: list[str]
    impacted_milestone_titles: list[str]
    reaches_decision_deadline: bool


class DevelopmentTimelineProjection(BaseModel):
    model_config = ConfigDict(frozen=True)

    projection_schema_version: str = "development-timeline.v1"
    case_id: str
    aggregate_version: int
    current_step: int
    reconstructed_at_step: int
    work_items: list[TimelineWorkItem]
    milestones: list[TimelineMilestone]
    evidence: list[TimelineEvidence]
    actions: list[TimelineAction]
    events: list[TimelineEvent]
    blocker_propagations: list[BlockerPropagation]


def reconstruct_case_at_step(case: ObservableCase, at_step: int) -> ObservableCase:
    if at_step < 0 or at_step > case.current_step:
        raise ValueError("DEVELOPMENT_STEP_OUT_OF_RANGE")

    work_states = {
        item.work_item_id: WorkItemDynamicState(
            status=item.status,
            blocker=item.blocker,
            planned_at_step=item.planned_at_step,
            dependency_ids=item.dependency_ids,
        )
        for item in case.work_items
    }
    milestone_states = {
        item.milestone_id: MilestoneDynamicState(planned_at_step=item.planned_at_step)
        for item in case.milestones
    }
    evidence_states = {
        item.evidence_id: EvidenceDynamicState(available_at_step=item.available_at_step)
        for item in case.evidence
    }
    action_states = {
        item.action_id: DevelopmentActionDynamicState(
            status=item.status,
            due_at_step=item.due_at_step,
            blocker=item.blocker,
        )
        for item in case.development_actions
    }
    events_to_reverse = sorted(
        (
            event
            for event in case.development_events
            if event.observed_at_step > at_step
        ),
        key=lambda item: (item.observed_at_step, item.event_id),
        reverse=True,
    )
    for event in events_to_reverse:
        for work_change in reversed(event.work_item_changes):
            work_states[work_change.work_item_id] = work_change.before
        for milestone_change in reversed(event.milestone_changes):
            milestone_states[milestone_change.milestone_id] = milestone_change.before
        for evidence_change in reversed(event.evidence_changes):
            evidence_states[evidence_change.evidence_id] = evidence_change.before
        for action_change in reversed(event.action_changes):
            action_states[action_change.action_id] = action_change.before

    return case.model_copy(
        update={
            "current_step": at_step,
            "work_items": [
                item.model_copy(
                    update=work_states[item.work_item_id].model_dump(mode="python")
                )
                for item in case.work_items
            ],
            "milestones": [
                item.model_copy(
                    update=milestone_states[item.milestone_id].model_dump(mode="python")
                )
                for item in case.milestones
            ],
            "evidence": [
                item.model_copy(
                    update=evidence_states[item.evidence_id].model_dump(mode="python")
                )
                for item in case.evidence
            ],
            "development_actions": [
                _reconstructed_action(item, action_states[item.action_id])
                for item in case.development_actions
            ],
        }
    )


def build_development_timeline(
    stored: StoredCase, *, at_step: int | None = None
) -> DevelopmentTimelineProjection:
    requested_step = stored.case.current_step if at_step is None else at_step
    case = reconstruct_case_at_step(stored.case, requested_step)
    visible_events = [
        event
        for event in stored.case.development_events
        if event.observed_at_step <= requested_step
    ]
    return DevelopmentTimelineProjection(
        case_id=case.case_id,
        aggregate_version=stored.aggregate_version,
        current_step=stored.case.current_step,
        reconstructed_at_step=requested_step,
        work_items=[
            TimelineWorkItem(
                work_item_id=item.work_item_id,
                track_id=item.track_id,
                title=item.title,
                status=item.status,
                blocker=item.blocker,
                planned_at_step=item.planned_at_step,
                dependency_ids=item.dependency_ids,
            )
            for item in case.work_items
        ],
        milestones=[
            TimelineMilestone(
                milestone_id=item.milestone_id,
                title=item.title,
                planned_at_step=item.planned_at_step,
            )
            for item in case.milestones
        ],
        evidence=[
            TimelineEvidence(
                evidence_id=item.evidence_id,
                title=item.title,
                available_at_step=item.available_at_step,
                eligible_at_step=item.available_at_step <= requested_step,
            )
            for item in case.evidence
        ],
        actions=[
            TimelineAction(
                action_id=item.action_id,
                title=item.title,
                owner=item.owner,
                status=item.status,
                due_at_step=item.due_at_step,
                blocker=item.blocker,
            )
            for item in case.development_actions
        ],
        events=[_event_projection(item) for item in visible_events],
        blocker_propagations=_blocker_propagations(case),
    )


def _reconstructed_action(
    action: DevelopmentAction, state: DevelopmentActionDynamicState
) -> DevelopmentAction:
    return action.model_copy(update=state.model_dump(mode="python"))


def _event_projection(event: DevelopmentEvent) -> TimelineEvent:
    affected = [item.work_item_id for item in event.work_item_changes]
    affected.extend(item.milestone_id for item in event.milestone_changes)
    affected.extend(item.evidence_id for item in event.evidence_changes)
    affected.extend(item.action_id for item in event.action_changes)
    return TimelineEvent(
        event_id=event.event_id,
        event_type=event.event_type,
        effective_at_step=event.effective_at_step,
        observed_at_step=event.observed_at_step,
        summary=event.summary,
        cause=event.cause,
        affected_entity_ids=affected,
        impacted_milestone_ids=event.impacted_milestone_ids,
    )


def _blocker_propagations(case: ObservableCase) -> list[BlockerPropagation]:
    downstream: dict[str, set[str]] = {item.work_item_id: set() for item in case.work_items}
    by_id = {item.work_item_id: item for item in case.work_items}
    tracks = {item.track_id: item for item in case.tracks}
    milestones = {item.milestone_id: item for item in case.milestones}
    deadline = next(
        item
        for item in case.milestones
        if item.milestone_id == case.decision_deadline_milestone_id
    )
    for item in case.work_items:
        for dependency_id in item.dependency_ids:
            downstream[dependency_id].add(item.work_item_id)

    def descendants(item_id: str) -> set[str]:
        result: set[str] = set()
        pending = list(downstream[item_id])
        while pending:
            current = pending.pop()
            if current in result:
                continue
            result.add(current)
            pending.extend(downstream[current])
        return result

    propagations = []
    for item in case.work_items:
        if item.blocker is None:
            continue
        affected = descendants(item.work_item_id)
        impacted_track_ids = {by_id[item_id].track_id for item_id in affected}
        if not affected:
            impacted_track_ids.add(item.track_id)
        milestone_ids: set[str] = set()
        for track_id in impacted_track_ids:
            milestone_id = tracks[track_id].next_milestone_id
            if milestone_id is not None:
                milestone_ids.add(milestone_id)
        sorted_affected = sorted(affected)
        sorted_milestone_ids = sorted(milestone_ids)
        propagations.append(
            BlockerPropagation(
                source_work_item_id=item.work_item_id,
                source_work_item_title=item.title,
                downstream_work_item_ids=sorted_affected,
                downstream_work_item_titles=[
                    by_id[item_id].title for item_id in sorted_affected
                ],
                impacted_track_ids=sorted(impacted_track_ids),
                impacted_milestone_ids=sorted_milestone_ids,
                impacted_milestone_titles=[
                    milestones[milestone_id].title
                    for milestone_id in sorted_milestone_ids
                ],
                reaches_decision_deadline=(
                    case.decision_deadline_milestone_id in milestone_ids
                    or item.planned_at_step <= deadline.planned_at_step
                    or any(
                        by_id[item_id].planned_at_step <= deadline.planned_at_step
                        for item_id in affected
                    )
                ),
            )
        )
    return propagations
