import hashlib
import json
from typing import Literal, Protocol

from soc_ot.agents.multi_role import Safeguard, SimulatedDecision
from soc_ot.domain.models import (
    GUARDRAIL_METRIC_UNITS,
    HiddenCase,
    ObservableCase,
    OutcomePath,
    StrictModel,
)

METRIC_UNITS = GUARDRAIL_METRIC_UNITS


class OutcomeSnapshot(StrictModel):
    schema_version: Literal["outcome-snapshot.v1"] = "outcome-snapshot.v1"
    case_id: str
    decision_id: str
    selected_option_id: str
    advanced_from_step: int
    current_step: int
    rule_id: str
    outcome_rule_version: str
    event_ids: list[str]
    revealed_evidence: list[str]
    metrics: dict[str, float]
    consequences: list[str]
    guardrail_state: Literal["not_applicable", "monitoring", "triggered"]
    executed_actions: list[str]


class OutcomeRule(Protocol):
    rule_id: str

    def validate(self, parameters: dict[str, str | int | float | bool]) -> None: ...

    def apply(
        self,
        case: ObservableCase,
        path: OutcomePath,
        decision_id: str,
        target_step: int,
    ) -> OutcomeSnapshot: ...


class GuardedSwEisRule:
    rule_id = "guarded_sw_eis_path.v1"

    def validate(self, parameters: dict[str, str | int | float | bool]) -> None:
        required = {"reveal_measurement_at_step", "bandwidth_gb_s", "thermal_deg_c"}
        if not required <= parameters.keys():
            raise ValueError("OUTCOME_RULE_PARAMETERS_INVALID")

    def apply(
        self,
        case: ObservableCase,
        path: OutcomePath,
        decision_id: str,
        target_step: int,
    ) -> OutcomeSnapshot:
        reveal_step = int(path.parameters["reveal_measurement_at_step"])
        revealed = target_step >= reveal_step
        metrics = (
            {
                "DDR_BANDWIDTH": float(path.parameters["bandwidth_gb_s"]),
                "THERMAL": float(path.parameters["thermal_deg_c"]),
            }
            if revealed
            else {}
        )
        return _snapshot(
            case,
            path,
            decision_id,
            target_step,
            revealed_evidence=["DDR bandwidth 측정", "thermal 측정"] if revealed else [],
            metrics=metrics,
            consequences=["EIS 경로의 burst DDR traffic이 확인됨"] if revealed else [],
        )


class DeferredEisRule:
    rule_id = "deferred_eis_path.v1"

    def validate(self, parameters: dict[str, str | int | float | bool]) -> None:
        if "milestone_delay_steps" not in parameters:
            raise ValueError("OUTCOME_RULE_PARAMETERS_INVALID")

    def apply(
        self,
        case: ObservableCase,
        path: OutcomePath,
        decision_id: str,
        target_step: int,
    ) -> OutcomeSnapshot:
        delay = int(path.parameters["milestone_delay_steps"])
        return _snapshot(
            case,
            path,
            decision_id,
            target_step,
            revealed_evidence=[],
            metrics={},
            consequences=[f"통합 milestone이 {delay} step 지연됨"],
        )


OUTCOME_RULES: dict[str, OutcomeRule] = {
    GuardedSwEisRule.rule_id: GuardedSwEisRule(),
    DeferredEisRule.rule_id: DeferredEisRule(),
}


def advance_outcome(
    case: ObservableCase,
    hidden: HiddenCase,
    decision: SimulatedDecision,
    *,
    target_step: int,
) -> OutcomeSnapshot:
    if target_step <= case.current_step:
        raise ValueError("TARGET_STEP_MUST_ADVANCE")
    paths = _matching_paths(hidden, decision.selected_option_id)
    if not paths:
        raise ValueError("OUTCOME_PATH_UNDEFINED")
    if len(paths) > 1:
        raise ValueError("OUTCOME_RULE_CONFLICT")
    path = paths[0]
    rule = OUTCOME_RULES.get(path.rule_id)
    if rule is None:
        raise ValueError("OUTCOME_RULE_NOT_REGISTERED")
    rule.validate(path.parameters)
    decision_id = _decision_id(decision)
    snapshot = rule.apply(case, path, decision_id, target_step)
    return _apply_guardrails(snapshot, decision.safeguards)


def _matching_paths(hidden: HiddenCase, option_id: str | None) -> list[OutcomePath]:
    if option_id is None:
        return [
            item for item in hidden.outcome_paths if item.rule_id == DeferredEisRule.rule_id
        ]
    return [item for item in hidden.outcome_paths if item.option_id == option_id]


def _snapshot(
    case: ObservableCase,
    path: OutcomePath,
    decision_id: str,
    target_step: int,
    *,
    revealed_evidence: list[str],
    metrics: dict[str, float],
    consequences: list[str],
) -> OutcomeSnapshot:
    event_seed = (
        f"{case.case_id}:{case.current_step}:{target_step}:{decision_id}:{path.rule_id}"
    )
    event_id = "EVT-" + hashlib.sha256(event_seed.encode()).hexdigest()[:20]
    return OutcomeSnapshot(
        case_id=case.case_id,
        decision_id=decision_id,
        selected_option_id=path.option_id,
        advanced_from_step=case.current_step,
        current_step=target_step,
        rule_id=path.rule_id,
        outcome_rule_version=path.rule_id,
        event_ids=[event_id],
        revealed_evidence=revealed_evidence,
        metrics=metrics,
        consequences=consequences,
        guardrail_state="not_applicable",
        executed_actions=[],
    )


def _apply_guardrails(
    snapshot: OutcomeSnapshot, safeguards: list[Safeguard]
) -> OutcomeSnapshot:
    state: Literal["not_applicable", "monitoring", "triggered"] = "not_applicable"
    actions: list[str] = []
    consequences = list(snapshot.consequences)
    for safeguard in safeguards:
        metric = snapshot.metrics.get(safeguard.metric_id)
        if metric is None or snapshot.current_step < safeguard.check_at_step:
            state = "monitoring"
            continue
        if METRIC_UNITS.get(safeguard.metric_id) != safeguard.threshold.unit:
            raise ValueError("GUARDRAIL_UNIT_MISMATCH")
        threshold = safeguard.threshold.value
        if threshold is None:
            raise ValueError("GUARDRAIL_THRESHOLD_NOT_EXACT")
        if not _compare(metric, safeguard.operator, threshold):
            state = "triggered"
            actions.append(safeguard.violation_action)
            consequences.append(
                f"{safeguard.metric_id} guardrail 위반으로 {safeguard.violation_action} 실행"
            )
        elif state != "triggered":
            state = "monitoring"
    return snapshot.model_copy(
        update={
            "guardrail_state": state,
            "executed_actions": actions,
            "consequences": consequences,
        }
    )


def _compare(value: float, operator: str, threshold: float) -> bool:
    comparisons = {
        "lt": value < threshold,
        "lte": value <= threshold,
        "gt": value > threshold,
        "gte": value >= threshold,
        "eq": value == threshold,
    }
    return comparisons[operator]


def _decision_id(decision: SimulatedDecision) -> str:
    canonical = json.dumps(
        decision.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "DEC-" + hashlib.sha256(canonical.encode()).hexdigest()[:20]
