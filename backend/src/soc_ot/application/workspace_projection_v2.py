from collections import Counter
from datetime import UTC, datetime
from typing import Literal

from soc_ot.agents.contracts import RoleReview
from soc_ot.agents.multi_role import AblationResult, DecisionDossier, SimulatedDecision
from soc_ot.application.development_twin import (
    BlockerPropagation,
    DevelopmentTimelineProjection,
    TimelineEvent,
    build_development_timeline,
    reconstruct_case_at_step,
)
from soc_ot.application.evaluation import CaseEvaluation
from soc_ot.application.outcomes import OutcomeSnapshot, decision_id_for
from soc_ot.application.repositories import StoredCase
from soc_ot.application.workspace_contracts import (
    PRIMARY_ACTION_BY_PHASE,
    DecisionWorkspaceProjectionV2,
    WorkspaceActionPlanSummary,
    WorkspaceAlignmentGroup,
    WorkspaceAlternativesV2,
    WorkspaceAlternativeV2,
    WorkspaceBlockerImpact,
    WorkspaceCausalChain,
    WorkspaceCausalLink,
    WorkspaceChallengeChange,
    WorkspaceControls,
    WorkspaceCurrentBrief,
    WorkspaceDeadline,
    WorkspaceDecisionPosture,
    WorkspaceDeliberation,
    WorkspaceDetails,
    WorkspaceDevelopmentTwin,
    WorkspaceDissentSummary,
    WorkspaceEpistemicItem,
    WorkspaceExpectedOptionTransition,
    WorkspaceHeaderV2,
    WorkspaceObservedDecisionTransitions,
    WorkspaceOutcomeAndEvaluation,
    WorkspaceRoleReviewDetail,
    WorkspaceRoleRevision,
    WorkspaceSafeguardSummary,
    WorkspaceStateAtStep,
    WorkspaceStateTransition,
    WorkspaceTrackState,
    WorkspaceUxFixture,
    WorkspaceWorkflow,
)
from soc_ot.domain.models import (
    GUARDRAIL_METRIC_UNITS,
    AgentRunStatus,
    DecisionCaseStatus,
    DecisionType,
    DevelopmentActionStatus,
    EpistemicStatus,
    Milestone,
    ObservableCase,
    Quantity,
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

_DECISION_LABELS_KO: dict[DecisionType, str] = {
    DecisionType.APPROVE: "진행 승인",
    DecisionType.APPROVE_WITH_GUARDRAILS: "조건부 진행",
    DecisionType.RUN_REVERSIBLE_TRIAL: "가역적 시험",
    DecisionType.COLLECT_MINIMUM_EVIDENCE: "최소 근거 확보",
    DecisionType.DEFER_UNTIL_TRIGGER: "조건 충족까지 연기",
    DecisionType.REJECT: "진행하지 않음",
    DecisionType.ESCALATE: "상위 검토 필요",
}

_ROLE_LABELS_KO = {
    "ROLE-ARCH": "Architecture",
    "ROLE-HW": "HW/RTL",
    "ROLE-SW": "SW/FW/HAL",
    "ROLE-VERIF": "Verification/Measurement",
    "ROLE-PM": "Technical PM",
    "architecture_system": "Architecture",
    "hw_rtl": "HW/RTL",
    "sw": "SW/FW/HAL",
    "verification_measurement": "Verification/Measurement",
    "program_risk": "Technical PM",
    "evidence_owner": "근거 담당",
    "decision_chair": "가상 Decision Chair",
    "non_agent_baseline": "비 Agent 기준선",
}

_METRIC_LABELS_KO = {
    "DDR_BANDWIDTH": "DDR 대역폭",
    "THERMAL": "온도",
}

_OPERATOR_LABELS_KO = {
    "lt": "<",
    "lte": "≤",
    "gt": ">",
    "gte": "≥",
    "eq": "=",
}

_UNIT_LABELS_KO = {"degC": "°C"}

_STATE_LABELS_KO = {
    "PLANNED": "계획됨",
    "READY": "시작 가능",
    "IN_PROGRESS": "진행 중",
    "BLOCKED": "대기 중",
    "COMPLETED": "완료",
    "DONE": "완료",
    "VERIFIED": "검증 완료",
    "REWORK": "재작업",
    "CANCELLED": "취소됨",
}

_CONFIDENCE_LABELS_KO = {"low": "낮음", "medium": "중간", "high": "높음"}

_ACTION_STATUS_LABELS_KO = {
    "in_progress": "실행·관찰 중",
    "completed": "계획한 행동 완료",
    "blocked": "보호 조치 후 재검토 필요",
    "cancelled": "Rollback으로 중단",
}

_VIOLATION_ACTION_LABELS_KO = {
    "rollback": "되돌리기",
    "pause": "일시 중지",
    "escalate": "상위 검토",
    "re_review": "재검토",
}


def build_workspace_projection_v2(
    stored: StoredCase,
    *,
    at_step: int | None = None,
    content: WorkspaceUxFixture | None = None,
    dossier: DecisionDossier | None = None,
    dossier_run_status: AgentRunStatus | None = None,
    dossier_run_id: str | None = None,
    decision_result: AblationResult | None = None,
    outcome: OutcomeSnapshot | None = None,
    evaluation: CaseEvaluation | None = None,
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
    visible_dossier = None if historical else dossier
    visible_decision = None if historical else decision_result
    visible_outcome = None if historical else outcome
    visible_evaluation = None if historical else evaluation
    phase = (
        None
        if historical
        else _phase_for_status(
            current_case.status,
            dossier_run_status=dossier_run_status,
            dossier=visible_dossier,
            decision_result=visible_decision,
            outcome=visible_outcome,
            evaluation=visible_evaluation,
        )
    )
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
    template_epistemic = (
        template.deliberation.epistemic_items
        if model_content_available and template is not None and not historical
        else []
    )
    deliberation = _deliberation(
        selected_case,
        visible_dossier,
        next_evidence_step,
        template_epistemic=template_epistemic,
        historical=historical,
    )

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
                []
                if historical
                else template_brief.residual_risks_ko
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
        observed_decision_transitions=_observed_transitions(
            expected,
            visible_decision,
            visible_outcome,
        ),
        alternatives=WorkspaceAlternativesV2(
            comparison_dimensions_ko=[
                "기대 효과",
                "일정 영향",
                "실패 영향",
                "되돌리기와 전환 비용",
                "필요한 근거",
                "안전 조건",
                "남는 위험",
            ],
            items=_alternative_comparisons(
                selected_case,
                expected,
                visible_dossier,
                visible_decision.decision if visible_decision is not None else None,
                include_future_evidence=not historical,
            ),
        ),
        deliberation=deliberation,
        controls=_controls(
            selected_case,
            visible_decision,
            visible_outcome,
        ),
        outcome_and_evaluation=_outcome_and_evaluation(
            expected,
            visible_decision,
            visible_outcome,
            visible_evaluation,
        ),
        workflow=WorkspaceWorkflow(
            primary_action=primary_action,
            allowed_actions=[] if primary_action is None else [primary_action],
            dossier_run_id=None if historical else dossier_run_id,
        ),
        details=WorkspaceDetails(
            evidence_available=bool(selected_case.evidence),
            timeline_available=bool(timeline.events),
            impact_path_available=bool(timeline.blocker_propagations),
            role_originals_available=visible_dossier is not None,
        ),
    )


def _alternative_comparisons(
    case: ObservableCase,
    expected_transitions: list[WorkspaceExpectedOptionTransition],
    dossier: DecisionDossier | None,
    decision: SimulatedDecision | None,
    *,
    include_future_evidence: bool,
) -> list[WorkspaceAlternativeV2]:
    expected_by_option = {item.option_id: item for item in expected_transitions}
    claims = {item.claim_id: item for item in case.claims}
    evidence = {item.evidence_id: item for item in case.evidence}
    reviews = _effective_reviews(dossier)
    recommended_option = _recommended_option(reviews)
    items: list[WorkspaceAlternativeV2] = []
    for option in case.alternatives:
        transition = expected_by_option[option.option_id]
        required_evidence = sorted(
            {
                evidence[source_ref].title
                for claim_id in option.claim_ids
                if claim_id in claims
                for source_ref in claims[claim_id].source_refs
                if source_ref in evidence
                and (
                    include_future_evidence
                    or evidence[source_ref].available_at_step <= case.current_step
                )
            }
        )
        schedule_impact = [
            f"{change.entity_title}: {change.from_state} → {change.to_state}"
            for change in transition.state_changes
            if change.entity_type in {"action", "work_item", "milestone"}
        ]
        recommending_roles = [
            _role_label(review.role_id)
            for review in reviews
            if review.recommended_option_id == option.option_id
        ]
        is_recommended = recommended_option == option.option_id
        items.append(
            WorkspaceAlternativeV2(
                option_id=option.option_id,
                title=option.title,
                description=option.description,
                reversible=option.reversible,
                switching_cost=option.switching_cost,
                expected_effect_ko=option.description,
                schedule_impact_ko=schedule_impact,
                failure_impact_ko=[
                    f"실패 또는 지연 시 상실: {title}"
                    for title in transition.lost_options_ko
                ],
                reversibility_ko=(
                    f"되돌릴 수 있음 · 전환 비용 {_quantity_ko(option.switching_cost)}"
                    if option.reversible
                    else f"되돌리기 어려움 · 전환 비용 {_quantity_ko(option.switching_cost)}"
                ),
                required_evidence_ko=required_evidence,
                safety_conditions_ko=(
                    [
                        f"{guard.condition} · 위반 시 {guard.rollback_trigger}"
                        for guard in decision.safeguards
                    ]
                    if decision is not None
                    and decision.selected_option_id == option.option_id
                    else []
                ),
                residual_risks_ko=transition.unknown_impacts_ko,
                recommended=is_recommended,
                recommendation_reason_ko=(
                    f"{', '.join(recommending_roles)} 관점이 이 선택지를 권고했습니다."
                    if is_recommended and recommending_roles
                    else None
                ),
            )
        )
    return items


def _controls(
    case: ObservableCase,
    decision_result: AblationResult | None,
    outcome: OutcomeSnapshot | None,
) -> WorkspaceControls:
    if decision_result is None:
        return WorkspaceControls(safeguards=[], action_plan=None)
    decision = decision_result.decision
    action_status = _action_status(outcome)
    option_titles = {item.option_id: item.title for item in case.alternatives}
    selected_option_title = (
        option_titles.get(decision.selected_option_id)
        if decision.selected_option_id is not None
        else None
    )
    rationale_ko = _decision_rationale_ko(decision, selected_option_title)
    evidence_titles = {item.evidence_id: item.title for item in case.evidence}
    return WorkspaceControls(
        safeguards=[
            WorkspaceSafeguardSummary(
                safeguard_id=guard.safeguard_id,
                cause_ko=rationale_ko,
                metric_id=guard.metric_id,
                metric_label_ko=_metric_label_ko(guard.metric_id),
                operator=guard.operator,
                operator_ko=_OPERATOR_LABELS_KO[guard.operator],
                threshold_ko=_quantity_ko(guard.threshold),
                check_at_step=guard.check_at_step,
                expires_at_step=guard.expires_at_step,
                condition_ko=guard.condition,
                rollback_trigger_ko=guard.rollback_trigger,
                owner=_role_label(guard.owner),
                verification_ko=guard.verification,
                violation_action_ko=_VIOLATION_ACTION_LABELS_KO[guard.violation_action],
            )
            for guard in decision.safeguards
        ],
        action_plan=WorkspaceActionPlanSummary(
            action_type=decision.action_plan.action_type,
            decision_type_ko=_DECISION_LABELS_KO[decision.decision_type],
            selected_option_title=selected_option_title,
            decision_rationale_ko=rationale_ko,
            owner=_role_label(decision.action_plan.owner),
            action_ko=_replace_option_id(
                decision.action_plan.action,
                decision.selected_option_id,
                selected_option_title,
            ),
            due_at_step=decision.action_plan.due_at_step,
            trigger_ko=decision.action_plan.trigger,
            verification_ko=decision.action_plan.verification,
            fallback_action_ko=decision.action_plan.fallback_action,
            status=action_status,
            status_ko=_ACTION_STATUS_LABELS_KO[action_status],
            evidence_required_ko=[
                evidence_titles.get(item, item)
                for item in decision.action_plan.evidence_required
            ],
            escalation_target_ko=(
                _role_label(decision.action_plan.escalation_target)
                if decision.action_plan.escalation_target
                else None
            ),
            questions_to_resolve_ko=decision.action_plan.questions_to_resolve,
            reopen_condition_ko=decision.action_plan.reopen_condition,
        ),
    )


def _observed_transitions(
    expected: list[WorkspaceExpectedOptionTransition],
    decision_result: AblationResult | None,
    outcome: OutcomeSnapshot | None,
) -> WorkspaceObservedDecisionTransitions:
    if decision_result is None:
        return WorkspaceObservedDecisionTransitions(available=False)
    decision = decision_result.decision
    decision_id = decision_id_for(decision)
    selected = next(
        (
            item
            for item in expected
            if item.option_id == decision.selected_option_id
        ),
        None,
    )
    action_title = _replace_option_id(
        decision.action_plan.action,
        decision.selected_option_id,
        selected.option_title if selected is not None else None,
    )
    if outcome is None:
        return WorkspaceObservedDecisionTransitions(
            available=True,
            decision_id=decision_id,
            state_changes=[
                WorkspaceStateTransition(
                    provenance="observed_event",
                    entity_type="action",
                    entity_id=f"{decision_id}:action",
                    entity_title=action_title,
                    from_state="PLANNED",
                    to_state="IN_PROGRESS",
                    basis_refs=[decision_id],
                )
            ],
        )

    final_action_state = {
        "completed": "COMPLETED",
        "cancelled": "CANCELLED",
        "blocked": "BLOCKED",
        "in_progress": "IN_PROGRESS",
    }[_action_status(outcome)]
    changes: list[WorkspaceStateTransition] = []
    action_linked = False
    for change in selected.state_changes if selected is not None else []:
        if change.entity_type == "action":
            action_linked = True
            if change.to_state == final_action_state:
                continue
            from_state = change.to_state
            to_state = final_action_state
        else:
            from_state = change.from_state
            to_state = change.to_state
        changes.append(
            WorkspaceStateTransition(
                provenance="observed_event",
                entity_type=change.entity_type,
                entity_id=change.entity_id,
                entity_title=change.entity_title,
                from_state=from_state,
                to_state=to_state,
                basis_refs=outcome.event_ids,
            )
        )
    if not action_linked or not any(item.entity_type == "action" for item in changes):
        changes.append(
            WorkspaceStateTransition(
                provenance="observed_event",
                entity_type="action",
                entity_id=f"{decision_id}:action",
                entity_title=action_title,
                from_state="IN_PROGRESS",
                to_state=final_action_state,
                basis_refs=outcome.event_ids,
            )
        )
    return WorkspaceObservedDecisionTransitions(
        available=True,
        decision_id=decision_id,
        state_changes=changes,
        guardrail_events_ko=_guardrail_results(decision, outcome),
    )


def _outcome_and_evaluation(
    expected: list[WorkspaceExpectedOptionTransition],
    decision_result: AblationResult | None,
    outcome: OutcomeSnapshot | None,
    evaluation: CaseEvaluation | None,
) -> WorkspaceOutcomeAndEvaluation:
    if decision_result is None:
        return WorkspaceOutcomeAndEvaluation(
            outcome_state="not_available",
            hidden_until_step_advance=True,
        )
    if outcome is None:
        return WorkspaceOutcomeAndEvaluation(
            outcome_state="running",
            hidden_until_step_advance=True,
        )
    decision = decision_result.decision
    selected = next(
        (
            item
            for item in expected
            if item.option_id == decision.selected_option_id
        ),
        None,
    )
    expected_ko = [] if selected is None else [
        *(
            (
                f"{item.entity_title}: {_state_label_ko(item.from_state)} → "
                f"{_state_label_ko(item.to_state)}"
            )
            for item in selected.state_changes
        ),
        *(f"확인 전 위험: {item}" for item in selected.unknown_impacts_ko),
    ]
    actual_ko = _actual_outcome(decision, outcome)
    process_evaluation_ko = None
    outcome_evaluation_ko = None
    lessons: list[str] = []
    if evaluation is not None:
        process_evaluation_ko = (
            "당시 이용 가능한 근거에서 의존성, 이견, 안전 조건과 다음 행동을 모두 갖췄습니다."
            if evaluation.process_evaluation.passed
            else "판단 당시 과정 계약에서 보완할 항목이 확인되었습니다."
        )
        outcome_evaluation_ko = (
            "공개된 위험 신호에 필요한 보호 조치가 실행되어 위험을 제한했습니다."
            if evaluation.outcome_evaluation.passed
            else "공개된 결과에서 위험을 충분히 제한하지 못했습니다."
        )
        lessons = [
            *(
                f"{item}를 다음 유사 결정에서는 decision window 전에 확인합니다."
                for item in outcome.revealed_evidence
            ),
            *(
                f"{item} fallback을 재사용 가능한 안전 조건으로 유지합니다."
                for item in outcome.executed_actions
            ),
        ]
    return WorkspaceOutcomeAndEvaluation(
        outcome_state="available",
        hidden_until_step_advance=False,
        expectation_vs_actual_ko=[
            *(f"예상: {item}" for item in expected_ko),
            *(f"실제: {item}" for item in actual_ko),
        ],
        expected_ko=expected_ko,
        actual_ko=actual_ko,
        guardrail_results_ko=_guardrail_results(decision, outcome),
        process_evaluation_ko=process_evaluation_ko,
        outcome_evaluation_ko=outcome_evaluation_ko,
        lessons_ko=_unique(lessons),
    )


def _action_status(
    outcome: OutcomeSnapshot | None,
) -> Literal["in_progress", "completed", "blocked", "cancelled"]:
    if outcome is None:
        return "in_progress"
    if "rollback" in outcome.executed_actions:
        return "cancelled"
    if outcome.executed_actions:
        return "blocked"
    return "completed"


def _actual_outcome(
    decision: SimulatedDecision,
    outcome: OutcomeSnapshot,
) -> list[str]:
    metric_units = GUARDRAIL_METRIC_UNITS
    return _unique(
        [
            *(
                f"공개 근거: {_replace_metric_codes(item)}"
                for item in outcome.revealed_evidence
            ),
            *(
                (
                    f"측정: {_metric_label_ko(metric_id)} {value:g} "
                    f"{_unit_label_ko(metric_units.get(metric_id, ''))}"
                ).rstrip()
                for metric_id, value in outcome.metrics.items()
            ),
            *(_replace_metric_codes(item) for item in outcome.consequences),
            *(f"실행된 보호 조치: {item}" for item in outcome.executed_actions),
        ]
    )


def _guardrail_results(
    decision: SimulatedDecision,
    outcome: OutcomeSnapshot,
) -> list[str]:
    if outcome.guardrail_state == "triggered":
        return [
            f"안전 조건 위반 감지 · 보호 조치 {', '.join(outcome.executed_actions)} 실행"
        ]
    if outcome.guardrail_state == "monitoring":
        return ["측정값이 등록된 Guardrail 범위 안에 있어 계속 관찰합니다."]
    if decision.safeguards:
        return ["현재 Step에는 적용할 Guardrail 측정이 없습니다."]
    return ["이 판단에는 실행형 Guardrail이 없습니다."]


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _metric_label_ko(metric_id: str) -> str:
    return _METRIC_LABELS_KO.get(metric_id, metric_id.replace("_", " "))


def _unit_label_ko(unit: str) -> str:
    return _UNIT_LABELS_KO.get(unit, unit)


def _state_label_ko(state: str) -> str:
    return _STATE_LABELS_KO.get(state, state)


def _replace_metric_codes(value: str) -> str:
    for metric_id, label in _METRIC_LABELS_KO.items():
        value = value.replace(metric_id, label)
    return value


def _replace_option_id(
    value: str,
    option_id: str | None,
    option_title: str | None,
) -> str:
    if option_id is None or option_title is None:
        return value
    return value.replace(option_id, option_title)


def _decision_rationale_ko(
    decision: SimulatedDecision,
    selected_option_title: str | None,
) -> str:
    if decision.decision_source != "deterministic_core":
        return decision.rationale
    subject = (
        f"‘{selected_option_title}’ 선택지"
        if selected_option_title is not None
        else "현재 선택지"
    )
    return (
        f"관측 가능한 위험과 선택지의 가역성 규칙으로 {subject}를 비교한 "
        "결정론적 가상 판단입니다."
    )


def _deliberation(
    case: ObservableCase,
    dossier: DecisionDossier | None,
    next_evidence_step: int | None,
    *,
    template_epistemic: list[WorkspaceEpistemicItem],
    historical: bool,
) -> WorkspaceDeliberation:
    epistemic_items = _epistemic_items(
        case,
        next_evidence_step,
        include_unversioned=not historical,
    )
    statements = {item.statement_ko for item in epistemic_items}
    epistemic_items.extend(
        item for item in template_epistemic if item.statement_ko not in statements
    )
    assumptions = [
        item.statement_ko
        for item in epistemic_items
        if item.epistemic_status == "assumption"
    ]
    unknowns = [
        item.statement_ko
        for item in epistemic_items
        if item.epistemic_status == "unknown"
    ]
    if dossier is None:
        return WorkspaceDeliberation(
            agreement_ko=[],
            dissent_ko=[],
            needs_confirmation_ko=[] if historical else case.uncertainties,
            changed_after_challenge_ko=[],
            key_assumptions_ko=assumptions,
            key_unknowns_ko=unknowns,
            epistemic_items=epistemic_items,
        )

    agreement_groups = [
        WorkspaceAlignmentGroup(
            recommendation=group.recommendation,
            recommendation_ko=_DECISION_LABELS_KO[group.recommendation],
            role_labels_ko=[_role_label(role_id) for role_id in group.role_ids],
            summary_ko=(
                f"{', '.join(_role_label(role_id) for role_id in group.role_ids)} 관점이 "
                f"{_DECISION_LABELS_KO[group.recommendation]} 방향에 일치합니다."
            ),
        )
        for group in dossier.agreement_groups
    ]
    dissent_items = [
        WorkspaceDissentSummary(
            role_label_ko=_role_label(item.role_id),
            recommendation=item.recommendation,
            recommendation_ko=_DECISION_LABELS_KO[item.recommendation],
            rationale_ko=item.rationale,
        )
        for item in dossier.dissent
    ]
    original_by_role = {item.role_id: item for item in dossier.original_reviews}
    revised_by_role = {item.role_id: item for item in dossier.revised_reviews}
    challenge_changes = [
        WorkspaceChallengeChange(
            role_label_ko=_role_label(role_id),
            before_recommendation_ko=_DECISION_LABELS_KO[original_by_role[role_id].recommendation],
            after_recommendation_ko=_DECISION_LABELS_KO[revision.recommendation],
            summary_ko=(
                "반론 후 권고 방향이 바뀌었습니다."
                if revision.recommendation != original_by_role[role_id].recommendation
                else "반론 후 권고 이유와 조건이 보강되었습니다."
            ),
        )
        for role_id, revision in revised_by_role.items()
        if role_id in original_by_role and revision != original_by_role[role_id]
    ]
    option_titles = {item.option_id: item.title for item in case.alternatives}
    role_reviews = [
        _role_review_detail(
            review,
            revised_by_role.get(review.role_id),
            option_titles,
        )
        for review in dossier.original_reviews
    ]
    return WorkspaceDeliberation(
        agreement_ko=[item.summary_ko for item in agreement_groups],
        dissent_ko=[
            f"{item.role_label_ko}: {item.recommendation_ko} — {item.rationale_ko}"
            for item in dissent_items
        ],
        needs_confirmation_ko=dossier.unresolved_uncertainties,
        changed_after_challenge_ko=[item.summary_ko for item in challenge_changes],
        key_assumptions_ko=assumptions,
        key_unknowns_ko=unknowns,
        alignment_available=bool(agreement_groups or dissent_items or role_reviews),
        agreement_groups=agreement_groups,
        dissent_items=dissent_items,
        challenge_changes=challenge_changes,
        role_reviews=role_reviews,
        epistemic_items=epistemic_items,
    )


def _role_review_detail(
    review: RoleReview,
    revision: RoleReview | None,
    option_titles: dict[str, str],
) -> WorkspaceRoleReviewDetail:
    return WorkspaceRoleReviewDetail(
        role_label_ko=_role_label(review.role_id),
        recommendation_ko=_DECISION_LABELS_KO[review.recommendation],
        recommended_option_title=(
            option_titles.get(review.recommended_option_id)
            if review.recommended_option_id
            else None
        ),
        rationale_ko=review.rationale,
        risks_ko=[
            f"{risk.statement} · 대응: {risk.mitigation}" for risk in review.risks
        ],
        information_gaps_ko=review.information_gaps,
        unique_concern_ko=review.unique_concern,
        confidence_ko=_CONFIDENCE_LABELS_KO[review.confidence],
        revision=(
            WorkspaceRoleRevision(
                recommendation_ko=_DECISION_LABELS_KO[revision.recommendation],
                rationale_ko=revision.rationale,
            )
            if revision is not None and revision != review
            else None
        ),
    )


def _epistemic_items(
    case: ObservableCase,
    next_evidence_step: int | None,
    *,
    include_unversioned: bool,
) -> list[WorkspaceEpistemicItem]:
    evidence = {item.evidence_id: item for item in case.evidence}
    eligible_ids = {
        item.evidence_id
        for item in case.evidence
        if item.available_at_step <= case.current_step
    }
    items: list[WorkspaceEpistemicItem] = []
    for claim in case.claims:
        if claim.epistemic_status in {EpistemicStatus.FACT, EpistemicStatus.INFERENCE}:
            if not set(claim.source_refs) <= eligible_ids:
                continue
        elif not include_unversioned:
            continue
        source_evidence = [evidence[item] for item in claim.source_refs if item in evidence]
        items.append(
            WorkspaceEpistemicItem(
                epistemic_status=claim.epistemic_status,
                statement_ko=claim.statement,
                source_titles_ko=[item.title for item in source_evidence],
                observed_at_step=(
                    max(item.available_at_step for item in source_evidence)
                    if source_evidence
                    else None
                ),
                inference_basis_ko=(
                    [f"등록된 추론 규칙 {len(claim.inference_basis)}개로 연결했습니다."]
                    if claim.epistemic_status is EpistemicStatus.INFERENCE
                    else []
                ),
                owner_ko=_role_label(claim.owner) if claim.owner else None,
                expires_at_step=claim.expires_at_step,
                unknown_reason_ko=(
                    "현재 observable source로는 확인할 수 없습니다."
                    if claim.epistemic_status is EpistemicStatus.UNKNOWN
                    else None
                ),
                expected_confirmation_step=(
                    next_evidence_step
                    if claim.epistemic_status is EpistemicStatus.UNKNOWN
                    else None
                ),
            )
        )
    if include_unversioned:
        known_statements = {item.statement_ko for item in items}
        items.extend(
            WorkspaceEpistemicItem(
                epistemic_status="unknown",
                statement_ko=statement,
                unknown_reason_ko="현재 observable source가 이 질문에 답하지 못합니다.",
                expected_confirmation_step=next_evidence_step,
            )
            for statement in case.uncertainties
            if statement not in known_statements
        )
    return items


def _effective_reviews(dossier: DecisionDossier | None) -> list[RoleReview]:
    if dossier is None:
        return []
    revised = {item.role_id: item for item in dossier.revised_reviews}
    return [revised.get(item.role_id, item) for item in dossier.original_reviews]


def _recommended_option(reviews: list[RoleReview]) -> str | None:
    counts = Counter(
        review.recommended_option_id
        for review in reviews
        if review.recommended_option_id is not None
    )
    if not counts:
        return None
    ordered = counts.most_common()
    if len(ordered) > 1 and ordered[0][1] == ordered[1][1]:
        return None
    return ordered[0][0]


def _role_label(role_id: str) -> str:
    return _ROLE_LABELS_KO.get(role_id, role_id.removeprefix("ROLE-").replace("_", " "))


def _quantity_ko(quantity: Quantity) -> str:
    unit = _unit_label_ko(quantity.unit)
    if quantity.mode.value == "exact":
        return (
            f"{quantity.value:g} {unit}"
            if quantity.value is not None
            else unit
        )
    if quantity.mode.value == "range":
        return f"{quantity.lower_bound:g}–{quantity.upper_bound:g} {unit}"
    if quantity.mode.value == "qualitative":
        return f"{quantity.qualitative} 수준"
    return "아직 정량화되지 않음"


def _phase_for_status(
    status: DecisionCaseStatus,
    *,
    dossier_run_status: AgentRunStatus | None = None,
    dossier: DecisionDossier | None = None,
    decision_result: AblationResult | None = None,
    outcome: OutcomeSnapshot | None = None,
    evaluation: CaseEvaluation | None = None,
) -> WorkspacePhase:
    if status in {DecisionCaseStatus.DRAFT, DecisionCaseStatus.CONTEXT_BUILDING}:
        return WorkspacePhase.CONTEXT_PREPARATION
    if evaluation is not None:
        return WorkspacePhase.CLOSED
    if outcome is not None:
        return WorkspacePhase.EVALUATION_READY
    if decision_result is not None:
        return WorkspacePhase.OUTCOME_RUNNING
    if dossier_run_status in {
        AgentRunStatus.QUEUED,
        AgentRunStatus.RUNNING,
        AgentRunStatus.PARTIALLY_COMPLETED,
    }:
        return WorkspacePhase.REVIEW_RUNNING
    if dossier_run_status is AgentRunStatus.COMPLETED and dossier is not None:
        return WorkspacePhase.DOSSIER_READY
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
