from soc_ot.agents.multi_role import (
    DecisionActionPlan,
    DecisionDossier,
    Safeguard,
    SimulatedDecision,
)
from soc_ot.application.packets import ObservableCasePacket
from soc_ot.domain.models import (
    GUARDRAIL_METRIC_UNITS,
    DecisionType,
    Quantity,
    QuantityMode,
)


def simulated_chair_decision(
    packet: ObservableCasePacket,
    dossier: DecisionDossier,
    allowed_decision_types: list[DecisionType],
) -> SimulatedDecision:
    operability = sorted(
        packet.option_operability,
        key=lambda item: (
            not item.reversible,
            {"high": 0, "medium": 1, "low": 2}[item.recoverability],
        ),
    )
    preferred_option = operability[0]
    future_steps = [
        item.available_at_step
        for item in packet.evidence_availability
        if item.available_at_step > packet.current_step
    ]
    evidence_after_deadline = (
        bool(future_steps)
        and min(future_steps) > packet.deadline_milestone.planned_at_step
    )
    safely_reversible = (
        preferred_option.reversible
        and preferred_option.recoverability == "high"
        and preferred_option.detectability != "unknown"
    )
    if safely_reversible and (packet.claims or evidence_after_deadline):
        preference = [
            DecisionType.APPROVE_WITH_GUARDRAILS,
            DecisionType.RUN_REVERSIBLE_TRIAL,
            DecisionType.APPROVE,
            DecisionType.COLLECT_MINIMUM_EVIDENCE,
            DecisionType.DEFER_UNTIL_TRIGGER,
            DecisionType.ESCALATE,
            DecisionType.REJECT,
        ]
    else:
        preference = [
            DecisionType.COLLECT_MINIMUM_EVIDENCE,
            DecisionType.DEFER_UNTIL_TRIGGER,
            DecisionType.ESCALATE,
            DecisionType.REJECT,
            DecisionType.RUN_REVERSIBLE_TRIAL,
            DecisionType.APPROVE_WITH_GUARDRAILS,
            DecisionType.APPROVE,
        ]
    candidate = next(item for item in preference if item in allowed_decision_types)
    option_required = candidate in {
        DecisionType.APPROVE,
        DecisionType.APPROVE_WITH_GUARDRAILS,
        DecisionType.RUN_REVERSIBLE_TRIAL,
    }
    safeguards = []
    if candidate in {
        DecisionType.APPROVE_WITH_GUARDRAILS,
        DecisionType.RUN_REVERSIBLE_TRIAL,
    }:
        safeguards = [
            Safeguard(
                safeguard_id="SG-POWER-STOP",
                metric_id="DDR_BANDWIDTH",
                operator="lte",
                threshold=Quantity(mode=QuantityMode.EXACT, unit="GB/s", value=20.0),
                check_at_step=max(packet.current_step + 1, 15),
                expires_at_step=max(packet.current_step + 2, 16),
                violation_action="rollback",
                condition="제한된 범위에서만 선택지를 실행한다.",
                rollback_trigger="관측 지표가 사전 합의 범위를 벗어나거나 blocker가 증가한다.",
                owner="program_risk",
                verification="다음 simulation step에서 측정 근거와 blocker 상태를 재검토한다.",
            )
        ]
    decision = SimulatedDecision(
        case_id=packet.case_id,
        decision_type=candidate,
        selected_option_id=preferred_option.option_id if option_required else None,
        rationale=(
            "다수결이 아니라 현재 근거, 다음 근거의 기한 이후 도착 여부, 선택지의 "
            "가역성·탐지 가능성·복구 가능성, 남은 dissent를 함께 적용한 모의 결정이다."
        ),
        safeguards=safeguards,
        action_plan=_build_action_plan(packet, candidate, preferred_option.option_id),
        dissent_acknowledged=[item.role_id for item in dossier.dissent],
        decision_source="simulated_chair",
    )
    validate_decision_policy(
        decision, allowed_decision_types, current_step=packet.current_step
    )
    return decision


def deterministic_core_decision(
    packet: ObservableCasePacket,
    dossier: DecisionDossier,
    allowed_decision_types: list[DecisionType],
) -> SimulatedDecision:
    chair_result = simulated_chair_decision(packet, dossier, allowed_decision_types)
    return chair_result.model_copy(
        update={
            "rationale": (
                "Agent Chair 없이 observable risk와 option operability 규칙만 적용한 "
                "deterministic 비교 기준이다."
            ),
            "dissent_acknowledged": [],
            "decision_source": "deterministic_core",
        }
    )


def validate_decision_policy(
    decision: SimulatedDecision,
    allowed_decision_types: list[DecisionType],
    *,
    current_step: int | None = None,
) -> None:
    if decision.decision_type not in allowed_decision_types:
        raise ValueError("DECISION_TYPE_NOT_ALLOWED")
    if decision.decision_type in {
        DecisionType.APPROVE_WITH_GUARDRAILS,
        DecisionType.RUN_REVERSIBLE_TRIAL,
    } and not decision.safeguards:
        raise ValueError("CONDITIONAL_DECISION_REQUIRES_SAFEGUARD")
    if current_step is not None and decision.action_plan.due_at_step < current_step:
        raise ValueError("ACTION_PLAN_DUE_STEP_IN_PAST")
    for safeguard in decision.safeguards:
        if not all(
            [
                safeguard.condition,
                safeguard.metric_id,
                safeguard.operator,
                safeguard.threshold,
                safeguard.check_at_step,
                safeguard.expires_at_step,
                safeguard.violation_action,
                safeguard.rollback_trigger,
                safeguard.owner,
                safeguard.verification,
            ]
        ):
            raise ValueError("INCOMPLETE_SAFEGUARD")
        expected_unit = GUARDRAIL_METRIC_UNITS.get(safeguard.metric_id)
        if expected_unit is None:
            raise ValueError("UNSUPPORTED_GUARDRAIL_METRIC")
        if safeguard.threshold.unit != expected_unit:
            raise ValueError("GUARDRAIL_UNIT_MISMATCH")
        if safeguard.threshold.mode is not QuantityMode.EXACT:
            raise ValueError("GUARDRAIL_THRESHOLD_NOT_EXACT")


def _build_action_plan(
    packet: ObservableCasePacket,
    decision_type: DecisionType,
    preferred_option_id: str,
) -> DecisionActionPlan:
    future_evidence = [
        item
        for item in packet.evidence_availability
        if item.available_at_step > packet.current_step
    ]
    future_evidence.sort(key=lambda item: (item.available_at_step, item.evidence_id))
    next_evidence_step = (
        future_evidence[0].available_at_step
        if future_evidence
        else packet.current_step + 1
    )
    evidence_required = [item.evidence_id for item in future_evidence]
    if not evidence_required:
        evidence_required = packet.uncertainties or ["현재 미해결 위험의 최소 확인 근거"]

    if decision_type in {
        DecisionType.APPROVE,
        DecisionType.APPROVE_WITH_GUARDRAILS,
        DecisionType.RUN_REVERSIBLE_TRIAL,
    }:
        return DecisionActionPlan(
            action_type="execute",
            owner="program_risk",
            action=f"{preferred_option_id} 선택지를 승인된 범위에서 실행한다.",
            due_at_step=packet.current_step + 1,
            trigger="모의 결정이 기록되고 실행 조건이 충족된다.",
            verification="다음 simulation step에서 진행 상태와 guardrail을 확인한다.",
            fallback_action="조건 위반 시 실행을 중지하고 rollback 또는 재검토한다.",
        )
    if decision_type is DecisionType.COLLECT_MINIMUM_EVIDENCE:
        return DecisionActionPlan(
            action_type="collect_evidence",
            owner="evidence_owner",
            action="결정에 필요한 최소 근거만 수집하고 즉시 재검토한다.",
            due_at_step=next_evidence_step,
            trigger="명시한 최소 근거가 관측 가능해진다.",
            verification="필수 근거가 packet에 포함되었는지 확인한다.",
            fallback_action="기한까지 근거가 없으면 defer 또는 권한자 escalation을 검토한다.",
            evidence_required=evidence_required,
        )
    if decision_type is DecisionType.DEFER_UNTIL_TRIGGER:
        return DecisionActionPlan(
            action_type="defer",
            owner="decision_chair",
            action="새 근거 또는 결정 기한 trigger까지 결정을 보류한다.",
            due_at_step=max(
                packet.current_step,
                min(next_evidence_step, packet.deadline_milestone.planned_at_step),
            ),
            trigger="다음 근거가 도착하거나 결정 기한에 도달한다.",
            verification="trigger 시점에 동일 packet contract로 결정을 재실행한다.",
            fallback_action="trigger 미충족 상태로 기한에 도달하면 escalation한다.",
        )
    if decision_type is DecisionType.ESCALATE:
        questions = packet.uncertainties or [packet.decision_question]
        return DecisionActionPlan(
            action_type="escalate",
            owner="decision_chair",
            action="현재 역할의 통제 범위를 넘는 결정을 program owner에게 요청한다.",
            due_at_step=packet.current_step + 1,
            trigger="권한 또는 비가역 위험이 현재 역할의 통제 범위를 넘는다.",
            verification="대상 권한자의 답변과 결정 근거가 기록되었는지 확인한다.",
            fallback_action="응답 기한까지 답변이 없으면 실행을 보류하고 위험을 재평가한다.",
            escalation_target="program_owner",
            questions_to_resolve=questions,
        )
    return DecisionActionPlan(
        action_type="reject",
        owner="decision_chair",
        action="현재 선택지를 채택하지 않고 근거와 이유를 기록한다.",
        due_at_step=packet.current_step + 1,
        trigger="현재 위험이 허용 범위를 넘고 안전한 실행 조건이 없다.",
        verification="거절된 선택지가 후속 실행 계획에 포함되지 않았는지 확인한다.",
        fallback_action="새 선택지 또는 새 근거가 생길 때까지 거절 상태를 유지한다.",
        reopen_condition="새로운 관측 근거 또는 위험을 낮춘 수정 선택지가 확보된다.",
    )
