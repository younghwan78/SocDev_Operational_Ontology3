from soc_ot.agents.multi_role import DecisionDossier, Safeguard, SimulatedDecision
from soc_ot.application.packets import ObservableCasePacket
from soc_ot.domain.models import DecisionType, Quantity, QuantityMode


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
        dissent_acknowledged=[item.role_id for item in dossier.dissent],
        decision_source="simulated_chair",
    )
    validate_decision_policy(decision, allowed_decision_types)
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
    decision: SimulatedDecision, allowed_decision_types: list[DecisionType]
) -> None:
    if decision.decision_type not in allowed_decision_types:
        raise ValueError("DECISION_TYPE_NOT_ALLOWED")
    if decision.decision_type in {
        DecisionType.APPROVE_WITH_GUARDRAILS,
        DecisionType.RUN_REVERSIBLE_TRIAL,
    } and not decision.safeguards:
        raise ValueError("CONDITIONAL_DECISION_REQUIRES_SAFEGUARD")
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
