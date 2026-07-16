from datetime import UTC, datetime

from soc_ot.application.development_twin import (
    BlockerPropagation,
    DevelopmentTimelineProjection,
    TimelineEvent,
    build_development_timeline,
    reconstruct_case_at_step,
)
from soc_ot.application.repositories import StoredCase
from soc_ot.application.workspace_contracts import (
    PRIMARY_ACTION_BY_PHASE,
    DecisionWorkspaceProjectionV2,
    WorkspaceAlternativesV2,
    WorkspaceAlternativeV2,
    WorkspaceBlockerImpact,
    WorkspaceCausalChain,
    WorkspaceCausalLink,
    WorkspaceControls,
    WorkspaceCurrentBrief,
    WorkspaceDeadline,
    WorkspaceDecisionPosture,
    WorkspaceDetails,
    WorkspaceDevelopmentTwin,
    WorkspaceExpectedOptionTransition,
    WorkspaceHeaderV2,
    WorkspaceObservedDecisionTransitions,
    WorkspaceOutcomeAndEvaluation,
    WorkspaceStateAtStep,
    WorkspaceTrackState,
    WorkspaceUxFixture,
    WorkspaceWorkflow,
)
from soc_ot.domain.models import (
    DecisionCaseStatus,
    DevelopmentActionStatus,
    EpistemicStatus,
    Milestone,
    ObservableCase,
    WorkItem,
    WorkItemStatus,
    WorkspacePhase,
)

_DEFAULT_PHASE_COPY: dict[WorkspacePhase, tuple[str, str]] = {
    WorkspacePhase.CONTEXT_PREPARATION: (
        "결정에 필요한 개발 상태를 구성하고 있습니다.",
        "누락된 개발 상태, 의존성과 기한을 먼저 확인합니다.",
    ),
    WorkspacePhase.READY_FOR_REVIEW: (
        "현재 개발 상태와 선택지가 준비되었습니다.",
        "가상 역할 검토로 이견과 안전 조건을 확인할 수 있습니다.",
    ),
    WorkspacePhase.REVIEW_RUNNING: (
        "역할별 관점에서 현재 상황을 검토하고 있습니다.",
        "완료된 관점과 실패한 관점을 확인합니다.",
    ),
    WorkspacePhase.DOSSIER_READY: (
        "역할별 의견 종합이 준비되었습니다.",
        "일치, 핵심 이견과 확인 필요 항목을 검토합니다.",
    ),
    WorkspacePhase.DECISION_REQUIRED: (
        "권고와 안전 조건이 준비되어 가상 판단이 필요합니다.",
        "가정, 잔여 위험과 되돌리기 조건을 확인합니다.",
    ),
    WorkspacePhase.OUTCOME_RUNNING: (
        "가상 판단 이후 개발 상태 변화를 관찰하고 있습니다.",
        "다음 확인 Step과 중단 조건을 추적합니다.",
    ),
    WorkspacePhase.EVALUATION_READY: (
        "가상 결과와 판단 품질 평가를 확인할 수 있습니다.",
        "예상과 관측, 과정과 결과를 분리해 확인합니다.",
    ),
    WorkspacePhase.CLOSED: (
        "결정, 실행, 결과와 평가가 종료되었습니다.",
        "다음 판단에 재사용할 학습을 확인합니다.",
    ),
}

_WORK_PRIORITY: dict[WorkItemStatus, int] = {
    WorkItemStatus.BLOCKED: 0,
    WorkItemStatus.REWORK: 1,
    WorkItemStatus.IN_PROGRESS: 2,
    WorkItemStatus.READY: 3,
    WorkItemStatus.PLANNED: 4,
    WorkItemStatus.DONE: 5,
    WorkItemStatus.VERIFIED: 6,
    WorkItemStatus.CANCELLED: 7,
}


def build_workspace_projection_v2(
    stored: StoredCase,
    *,
    at_step: int | None = None,
    content: WorkspaceUxFixture | None = None,
) -> DecisionWorkspaceProjectionV2:
    current_case = stored.case
    selected_step = current_case.current_step if at_step is None else at_step
    template = _compatible_template(content, current_case)
    earliest_step = (
        template.time_context.earliest_available_step
        if template is not None
        else min(
            (item.observed_at_step for item in current_case.development_events),
            default=current_case.current_step,
        )
    )
    if selected_step < earliest_step or selected_step > current_case.current_step:
        raise ValueError("DEVELOPMENT_STEP_OUT_OF_RANGE")
    selected_case = reconstruct_case_at_step(current_case, selected_step)
    timeline = build_development_timeline(stored, at_step=selected_step)
    historical = selected_step != current_case.current_step
    phase = None if historical else _phase_for_status(current_case.status)
    model_content_available = (
        template is not None and selected_step >= template.time_context.selected_step
    )
    deadline = next(
        item
        for item in selected_case.milestones
        if item.milestone_id == selected_case.decision_deadline_milestone_id
    )
    remaining_steps = deadline.planned_at_step - selected_step
    why_now = _why_now_at_step(deadline.title, remaining_steps, timeline.blocker_propagations)
    phase_summary, phase_guidance = _phase_copy(phase, content)
    primary_action = PRIMARY_ACTION_BY_PHASE[phase] if phase is not None else None
    next_evidence_step = min(
        (
            item.available_at_step
            for item in selected_case.evidence
            if item.available_at_step > selected_step
        ),
        default=None,
    )
    expected = (
        template.expected_option_transitions
        if model_content_available and template is not None
        else _unknown_expected_transitions(selected_case)
    )
    commitments = (
        template.development_twin.commitment_windows
        if model_content_available and template is not None
        else []
    )
    template_brief = template.current_brief if model_content_available and template else None

    return DecisionWorkspaceProjectionV2(
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        aggregate_version=stored.aggregate_version,
        case_id=current_case.case_id,
        fixture_version=current_case.fixture_version,
        stale=False,
        time_context={
            "current_step": current_case.current_step,
            "selected_step": selected_step,
            "mode": "historical" if historical else "current",
            "earliest_available_step": earliest_step,
            "latest_observable_step": current_case.current_step,
            "next_expected_evidence_step": next_evidence_step,
            "commands_allowed_at_selected_step": not historical,
        },
        header=WorkspaceHeaderV2(
            title_ko=current_case.title_ko,
            decision_question=current_case.decision_question,
            workspace_phase=phase,
            case_status=None if historical else current_case.status,
            deadline=WorkspaceDeadline(
                milestone_id=current_case.decision_deadline_milestone_id,
                title=deadline.title,
                at_step=deadline.planned_at_step,
                remaining_steps=remaining_steps,
            ),
        ),
        current_brief=WorkspaceCurrentBrief(
            state_or_recommendation_ko=(
                "선택한 Step의 당시 개발 상태" if historical else phase_summary
            ),
            one_line_reason_ko=(
                "이 시점 이후에 알려진 검토·판단·결과는 포함하지 않습니다."
                if historical
                else phase_guidance
            ),
            why_now_ko=why_now,
            key_conditions_ko=(template_brief.key_conditions_ko if template_brief else []),
            residual_risks_ko=(
                template_brief.residual_risks_ko
                if template_brief
                else selected_case.uncertainties[:2]
            ),
        ),
        decision_posture=_decision_posture(
            selected_case,
            timeline,
            remaining_steps,
            template.decision_posture if model_content_available and template else None,
        ),
        development_twin=WorkspaceDevelopmentTwin(
            state_at_selected_step=_state_at_step(selected_case),
            causal_chains=_causal_chains(timeline),
            blocker_impacts=_blocker_impacts(selected_case, timeline.blocker_propagations),
            commitment_windows=commitments,
            delay_summary_ko=why_now,
            recent_decision_relevant_event_ids=[
                item.event_id for item in timeline.events[-3:]
            ],
        ),
        expected_option_transitions=expected,
        observed_decision_transitions=WorkspaceObservedDecisionTransitions(available=False),
        alternatives=WorkspaceAlternativesV2(
            comparison_dimensions_ko=[
                "기대 효과",
                "일정 영향",
                "되돌리기와 전환 비용",
                "아직 모르는 영향",
            ],
            items=[
                WorkspaceAlternativeV2(
                    option_id=item.option_id,
                    title=item.title,
                    description=item.description,
                    reversible=item.reversible,
                    switching_cost=item.switching_cost,
                )
                for item in selected_case.alternatives
            ],
        ),
        deliberation={
            "agreement_ko": [],
            "dissent_ko": [],
            "needs_confirmation_ko": selected_case.uncertainties,
            "changed_after_challenge_ko": [],
            "key_assumptions_ko": [
                item.statement
                for item in selected_case.claims
                if item.epistemic_status is EpistemicStatus.ASSUMPTION
            ],
            "key_unknowns_ko": selected_case.uncertainties,
        },
        controls=WorkspaceControls(safeguards=[], action_plan=None),
        outcome_and_evaluation=WorkspaceOutcomeAndEvaluation(
            outcome_state="not_available",
            hidden_until_step_advance=True,
        ),
        workflow=WorkspaceWorkflow(
            primary_action=primary_action,
            allowed_actions=[] if primary_action is None else [primary_action],
        ),
        details=WorkspaceDetails(
            evidence_available=bool(selected_case.evidence),
            timeline_available=bool(timeline.events),
            impact_path_available=bool(timeline.blocker_propagations),
            role_originals_available=False,
        ),
    )


def _phase_for_status(status: DecisionCaseStatus) -> WorkspacePhase:
    if status in {DecisionCaseStatus.DRAFT, DecisionCaseStatus.CONTEXT_BUILDING}:
        return WorkspacePhase.CONTEXT_PREPARATION
    if status in {
        DecisionCaseStatus.OPTIONS_READY,
        DecisionCaseStatus.DECISION_REQUIRED,
        DecisionCaseStatus.REOPENED,
    }:
        return WorkspacePhase.READY_FOR_REVIEW
    if status in {DecisionCaseStatus.DECIDED, DecisionCaseStatus.ACTIONING}:
        return WorkspacePhase.OUTCOME_RUNNING
    if status is DecisionCaseStatus.VERIFIED:
        return WorkspacePhase.EVALUATION_READY
    return WorkspacePhase.CLOSED


def _why_now_at_step(
    deadline_title: str,
    remaining_steps: int,
    propagations: list[BlockerPropagation],
) -> str:
    if remaining_steps < 0:
        deadline_reason = f"{deadline_title} 기한이 {abs(remaining_steps)} Step 지났습니다."
    elif remaining_steps == 0:
        deadline_reason = f"{deadline_title}가 현재 Step입니다."
    else:
        deadline_reason = f"{deadline_title}까지 {remaining_steps} Step 남았습니다."
    if not propagations:
        return deadline_reason
    critical = min(
        propagations,
        key=lambda item: (
            0 if item.reaches_decision_deadline else 1,
            -len(item.downstream_work_item_ids),
            item.source_work_item_id,
        ),
    )
    if not critical.downstream_work_item_titles:
        return f"{deadline_reason} 확인 필요: {critical.source_work_item_title}."
    return (
        f"{deadline_reason} 대기 원인: {critical.source_work_item_title}. "
        f"영향 작업: {', '.join(critical.downstream_work_item_titles[:2])}."
    )


def _phase_copy(
    phase: WorkspacePhase | None,
    content: WorkspaceUxFixture | None,
) -> tuple[str, str]:
    if phase is None:
        return (
            "선택한 Step의 당시 개발 상태",
            "이후에 알려진 정보는 포함하지 않습니다.",
        )
    if content is not None:
        match = next((item for item in content.phase_contents if item.phase is phase), None)
        if match is not None:
            return match.state_summary_ko, match.guidance_ko
    return _DEFAULT_PHASE_COPY[phase]


def _compatible_template(
    content: WorkspaceUxFixture | None,
    case: ObservableCase,
) -> DecisionWorkspaceProjectionV2 | None:
    if content is None or content.case_id != case.case_id:
        return None
    template = content.workspace_example
    if template.fixture_version != case.fixture_version:
        return None
    if {item.option_id for item in template.alternatives.items} != {
        item.option_id for item in case.alternatives
    }:
        return None
    return template


def _state_at_step(case: ObservableCase) -> WorkspaceStateAtStep:
    milestones = {item.milestone_id: item for item in case.milestones}
    tracks: list[WorkspaceTrackState] = []
    for track in case.tracks:
        candidates = [item for item in case.work_items if item.track_id == track.track_id]
        if not candidates:
            continue
        work = min(
            candidates,
            key=lambda item: (_WORK_PRIORITY[item.status], item.planned_at_step, item.work_item_id),
        )
        milestone = milestones.get(track.next_milestone_id) if track.next_milestone_id else None
        tracks.append(_track_state(track.name, work, milestone))
    return WorkspaceStateAtStep(
        reconstructed_at_step=case.current_step,
        tracks=tracks,
        eligible_evidence_ids=[
            item.evidence_id
            for item in case.evidence
            if item.available_at_step <= case.current_step
        ],
        unavailable_evidence_ids=[
            item.evidence_id
            for item in case.evidence
            if item.available_at_step > case.current_step
        ],
        active_action_ids=[
            item.action_id
            for item in case.development_actions
            if item.status
            not in {DevelopmentActionStatus.COMPLETED, DevelopmentActionStatus.CANCELLED}
        ],
    )


def _track_state(
    name: str, work: WorkItem, milestone: Milestone | None
) -> WorkspaceTrackState:
    return WorkspaceTrackState(
        track_id=work.track_id,
        name=name,
        status=work.status,
        current_work_item_id=work.work_item_id,
        current_work_item_title=work.title,
        owner=work.owner,
        blocker=work.blocker,
        next_milestone_id=milestone.milestone_id if milestone else None,
        next_milestone_title=milestone.title if milestone else None,
        next_milestone_step=milestone.planned_at_step if milestone else None,
    )


def _decision_posture(
    case: ObservableCase,
    timeline: DevelopmentTimelineProjection,
    remaining_steps: int,
    template: WorkspaceDecisionPosture | None,
) -> WorkspaceDecisionPosture:
    eligible_count = sum(item.available_at_step <= case.current_step for item in case.evidence)
    evidence_state = (
        "insufficient"
        if eligible_count == 0
        else "sufficient"
        if eligible_count == len(case.evidence)
        else "partial"
    )
    reversible_count = sum(item.reversible for item in case.alternatives)
    reversibility = (
        "high"
        if reversible_count == len(case.alternatives)
        else "medium"
        if reversible_count
        else "low"
    )
    detectability = (
        "observable_now"
        if eligible_count
        else "observable_later"
        if case.evidence
        else "unknown"
    )
    urgency = (
        "expired"
        if remaining_steps < 0
        else "high"
        if remaining_steps <= 2
        else "medium"
        if remaining_steps <= 5
        else "low"
    )
    blocked_tracks = len(
        {
            item.track_id
            for item in case.work_items
            if item.status is WorkItemStatus.BLOCKED or item.blocker is not None
        }
    )
    explanations = [
        f"현재 사용 가능한 근거는 {eligible_count}/{len(case.evidence)}개입니다.",
        f"되돌릴 수 있는 선택지는 {reversible_count}/{len(case.alternatives)}개입니다.",
        f"막힌 개발 track은 {blocked_tracks}개입니다.",
        (
            f"결정 기준점까지 {remaining_steps} Step 남았습니다."
            if remaining_steps >= 0
            else f"결정 기준점이 {abs(remaining_steps)} Step 지났습니다."
        ),
    ]
    return WorkspaceDecisionPosture(
        evidence_state=evidence_state,
        reversibility=reversibility,
        detectability=detectability,
        recoverability=reversibility,
        downside=template.downside if template else "unknown",
        blast_radius=(
            template.blast_radius
            if template
            else "cross_track"
            if any(len(item.impacted_track_ids) > 1 for item in timeline.blocker_propagations)
            else "unknown"
        ),
        urgency=urgency,
        explanations_ko=explanations,
    )


def _causal_chains(timeline: DevelopmentTimelineProjection) -> list[WorkspaceCausalChain]:
    return [
        _causal_chain(item, timeline.blocker_propagations)
        for item in timeline.events[-3:]
    ]


def _blocker_impacts(
    case: ObservableCase,
    propagations: list[BlockerPropagation],
) -> list[WorkspaceBlockerImpact]:
    work_items = {item.work_item_id: item for item in case.work_items}
    return [
        WorkspaceBlockerImpact(
            source_work_item_title=item.source_work_item_title,
            blocker_ko=work_items[item.source_work_item_id].blocker or "대기 원인 확인 필요",
            downstream_work_item_titles=item.downstream_work_item_titles,
            impacted_milestone_titles=item.impacted_milestone_titles,
            reaches_decision_deadline=item.reaches_decision_deadline,
        )
        for item in propagations
    ]


def _causal_chain(
    event: TimelineEvent,
    propagations: list[BlockerPropagation],
) -> WorkspaceCausalChain:
    related = [
        item
        for item in propagations
        if item.source_work_item_id in event.affected_entity_ids
    ]
    links = [
        WorkspaceCausalLink(
            relation_kind="observed",
            statement_ko=f"{event.summary} 원인: {event.cause}",
            source_refs=[event.event_id],
        )
    ]
    for impact in related:
        if not impact.downstream_work_item_titles:
            continue
        links.append(
            WorkspaceCausalLink(
                relation_kind="inferred",
                statement_ko=(
                    f"{impact.source_work_item_title}의 대기가 "
                    f"{', '.join(impact.downstream_work_item_titles)}에 전파됩니다."
                ),
                source_refs=[
                    impact.source_work_item_id,
                    *impact.downstream_work_item_ids,
                ],
                inference_basis=[
                    f"DEPENDENCY:{item}->{impact.source_work_item_id}"
                    for item in impact.downstream_work_item_ids
                ],
            )
        )
    impacted = set(event.impacted_milestone_ids)
    for item in related:
        impacted.update(item.impacted_milestone_ids)
    return WorkspaceCausalChain(
        source_event_id=event.event_id,
        observed_at_step=event.observed_at_step,
        title_ko=event.summary,
        links=links,
        impacted_milestone_ids=sorted(impacted),
    )


def _unknown_expected_transitions(
    case: ObservableCase,
) -> list[WorkspaceExpectedOptionTransition]:
    return [
        WorkspaceExpectedOptionTransition(
            option_id=item.option_id,
            option_title=item.title,
            state_changes=[],
            preserved_options_ko=[],
            lost_options_ko=[],
            model_basis=[],
            unknown_impacts_ko=["선택한 Step에서 검증된 상태 전이 모델이 없습니다."],
        )
        for item in case.alternatives
    ]
