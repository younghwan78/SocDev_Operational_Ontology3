from typing import Literal

from soc_ot.agents.multi_role import AblationResult, SimulatedDecision
from soc_ot.agents.providers import ReplayProvider, ReviewProvider
from soc_ot.application.development_twin import (
    build_development_timeline,
    reconstruct_case_at_step,
)
from soc_ot.application.evaluation_manifest import (
    V2_CASE_SOURCES,
    EvaluationCaseSource,
    EvaluationManifest,
    manifest_case_source,
)
from soc_ot.application.multi_role import Topology, run_ablation
from soc_ot.application.outcomes import OutcomeSnapshot, advance_outcome
from soc_ot.application.packets import build_observable_case_packet
from soc_ot.application.repositories import StoredCase
from soc_ot.domain.models import DecisionType, ExpectedResult, ObservableCase, StrictModel
from soc_ot.infrastructure.fixtures import FixtureRepository


class ProcessEvaluation(StrictModel):
    decision_acceptable: bool
    mandatory_claims_covered: bool
    mandatory_dependencies_covered: bool
    mandatory_guardrails_covered: bool
    required_roles_contributed: bool
    role_differentiation: bool
    unresolved_uncertainty_visible: bool
    conditional_control_complete: bool
    decision_action_complete: bool
    decision_action_type_complete: bool = True
    development_history_reconstructable: bool = True
    historical_packet_boundary_preserved: bool = True
    blocker_impact_traceable: bool = True
    passed: bool


class OutcomeEvaluation(StrictModel):
    rule_executed: bool
    evidence_revealed: bool
    risk_contained: bool
    passed: bool


class CaseEvaluation(StrictModel):
    schema_version: Literal["case-evaluation.v1", "case-evaluation.v2"] = (
        "case-evaluation.v2"
    )
    case_id: str
    partition: str
    topology: Topology
    ablation: AblationResult
    outcome: OutcomeSnapshot
    process_evaluation: ProcessEvaluation
    outcome_evaluation: OutcomeEvaluation
    passed: bool


class EvaluationSummary(StrictModel):
    schema_version: Literal["evaluation-summary.v1", "evaluation-summary.v2"] = (
        "evaluation-summary.v2"
    )
    provider: str = "replay"
    topology: Topology
    results: list[CaseEvaluation]
    total: int
    passed: int


def evaluate_case(
    fixtures: FixtureRepository,
    case_id: str,
    *,
    topology: Topology = "B3",
    provider: ReviewProvider | None = None,
    source: EvaluationCaseSource | None = None,
) -> CaseEvaluation:
    if source is None:
        case = fixtures.load_observable(case_id)
        hidden = fixtures.load_hidden(case_id)
        expected = fixtures.load_expected(case_id)
        partition = next(
            item.partition for item in V2_CASE_SOURCES if item.case_id == case_id
        )
    else:
        case, hidden, expected = fixtures.validate_evaluation_case(
            case_id,
            observable_path=source.observable_path,
            hidden_path=source.hidden_path,
            expected_path=source.expected_path,
        )
        partition = source.partition
    packet = build_observable_case_packet(case)
    ablation = run_ablation(
        packet,
        provider or ReplayProvider(),
        topology,
        allowed_decision_types=case.allowed_decision_types,
    )
    target_step = _target_step(case, hidden)
    outcome = advance_outcome(case, hidden, ablation.decision, target_step=target_step)
    process = _evaluate_process(case, expected, ablation)
    outcome_evaluation = OutcomeEvaluation(
        rule_executed=outcome.rule_id in {
            "guarded_sw_eis_path.v1",
            "deferred_eis_path.v1",
        },
        evidence_revealed=bool(outcome.revealed_evidence or outcome.consequences),
        risk_contained=(
            outcome.guardrail_state != "triggered" or bool(outcome.executed_actions)
        ),
        passed=bool(outcome.revealed_evidence or outcome.consequences)
        and (outcome.guardrail_state != "triggered" or bool(outcome.executed_actions)),
    )
    return CaseEvaluation(
        case_id=case_id,
        partition=partition,
        topology=topology,
        ablation=ablation,
        outcome=outcome,
        process_evaluation=process,
        outcome_evaluation=outcome_evaluation,
        passed=process.passed and outcome_evaluation.passed,
    )


def run_evaluation(
    fixtures: FixtureRepository,
    *,
    topology: Topology = "B3",
    manifest: EvaluationManifest | None = None,
) -> EvaluationSummary:
    sources: list[EvaluationCaseSource] = (
        [manifest_case_source(item) for item in manifest.cases]
        if manifest is not None
        else V2_CASE_SOURCES
    )
    results = [
        evaluate_case(fixtures, source.case_id, topology=topology, source=source)
        for source in sources
    ]
    return EvaluationSummary(
        topology=topology,
        results=results,
        total=len(results),
        passed=sum(result.passed for result in results),
    )


def _target_step(case: ObservableCase, hidden: object) -> int:
    from soc_ot.domain.models import HiddenCase

    typed = hidden if isinstance(hidden, HiddenCase) else HiddenCase.model_validate(hidden)
    reveal_steps = [
        int(path.parameters.get("reveal_measurement_at_step", case.current_step + 1))
        for path in typed.outcome_paths
    ]
    return max(case.current_step + 1, max(reveal_steps))


def _evaluate_process(
    case: ObservableCase, expected: ExpectedResult, ablation: AblationResult
) -> ProcessEvaluation:
    claim_ids = {
        claim_id
        for review in ablation.dossier.original_reviews
        for claim_id in (
            review.rationale_claim_ids
            + [claim for risk in review.risks for claim in risk.claim_ids]
        )
    }
    work_ids = {item.work_item_id for item in case.work_items}
    metric_ids = {item.metric_id for item in ablation.decision.safeguards}
    eligible_evidence = {
        item.evidence_id for item in case.evidence if item.available_at_step <= case.current_step
    }
    eligible_claims = {
        item.claim_id for item in case.claims if set(item.source_refs) <= eligible_evidence
    }
    required_claims = set(expected.mandatory_claim_ids) & eligible_claims
    required_metrics = (
        set(expected.mandatory_guardrail_metric_ids)
        if ablation.decision.safeguards
        else set()
    )
    history_checks = _evaluate_development_history(case)
    review_role_ids = {
        review.role_id for review in ablation.dossier.original_reviews
    }
    if ablation.topology == "B0":
        required_roles_contributed = ablation.role_count == 0
        role_differentiation = True
    elif ablation.topology == "B1":
        required_roles_contributed = (
            ablation.role_count == 1
            and bool(review_role_ids & set(case.required_role_ids))
        )
        role_differentiation = all(
            bool(review.unique_concern) != review.no_unique_concern
            for review in ablation.dossier.original_reviews
        )
    else:
        required_roles_contributed = set(case.required_role_ids) <= review_role_ids
        role_differentiation = all(
            bool(review.unique_concern) != review.no_unique_concern
            for review in ablation.dossier.original_reviews
        )
    checks = {
        "decision_acceptable": ablation.decision.decision_type
        in expected.acceptable_decision_types,
        "mandatory_claims_covered": required_claims <= claim_ids,
        "mandatory_dependencies_covered": set(expected.mandatory_dependency_ids) <= work_ids,
        "mandatory_guardrails_covered": required_metrics <= metric_ids,
        "required_roles_contributed": required_roles_contributed,
        "role_differentiation": role_differentiation,
        "unresolved_uncertainty_visible": set(case.uncertainties)
        <= set(ablation.dossier.unresolved_uncertainties),
        "conditional_control_complete": all(
            bool(
                safeguard.metric_id
                and safeguard.operator
                and safeguard.threshold
                and safeguard.check_at_step >= case.current_step
                and safeguard.expires_at_step >= safeguard.check_at_step
                and safeguard.violation_action
                and safeguard.owner
                and safeguard.verification
            )
            for safeguard in ablation.decision.safeguards
        ),
        "decision_action_complete": bool(
            ablation.decision.action_plan.owner
            and ablation.decision.action_plan.action
            and ablation.decision.action_plan.due_at_step >= case.current_step
            and ablation.decision.action_plan.trigger
            and ablation.decision.action_plan.verification
            and ablation.decision.action_plan.fallback_action
        ),
        "decision_action_type_complete": _action_plan_type_complete(
            ablation.decision, case
        ),
        **history_checks,
    }
    return ProcessEvaluation(**checks, passed=all(checks.values()))


def _action_plan_type_complete(
    decision: SimulatedDecision, case: ObservableCase
) -> bool:
    plan = decision.action_plan
    if decision.decision_type in {
        DecisionType.APPROVE,
        DecisionType.APPROVE_WITH_GUARDRAILS,
        DecisionType.RUN_REVERSIBLE_TRIAL,
    }:
        return bool(
            plan.action_type == "execute"
            and decision.selected_option_id
            and (
                decision.decision_type is DecisionType.APPROVE
                or decision.safeguards
            )
        )
    if decision.decision_type is DecisionType.COLLECT_MINIMUM_EVIDENCE:
        return plan.action_type == "collect_evidence" and bool(plan.evidence_required)
    if decision.decision_type is DecisionType.DEFER_UNTIL_TRIGGER:
        deadline = next(
            item
            for item in case.milestones
            if item.milestone_id == case.decision_deadline_milestone_id
        )
        return bool(
            plan.action_type == "defer"
            and decision.selected_option_id is None
            and plan.due_at_step <= deadline.planned_at_step
        )
    if decision.decision_type is DecisionType.ESCALATE:
        return bool(
            plan.action_type == "escalate"
            and decision.selected_option_id is None
            and plan.escalation_target
            and plan.questions_to_resolve
        )
    return bool(
        plan.action_type == "reject"
        and decision.selected_option_id is None
        and plan.reopen_condition
    )


def _evaluate_development_history(case: ObservableCase) -> dict[str, bool]:
    if not case.development_events:
        return {
            "development_history_reconstructable": True,
            "historical_packet_boundary_preserved": True,
            "blocker_impact_traceable": True,
        }
    observed_steps = sorted(
        {event.observed_at_step for event in case.development_events}
    )
    reconstructable = len(observed_steps) >= 3
    boundary_preserved = True
    checkpoints = [max(0, observed_steps[0] - 1), *observed_steps]
    try:
        for step in checkpoints:
            reconstructed = reconstruct_case_at_step(case, step)
            packet = build_observable_case_packet(case, at_step=step)
            reconstructable = reconstructable and reconstructed.current_step == step
            boundary_preserved = boundary_preserved and all(
                event.observed_at_step <= step
                for event in packet.development_events
            ) and all(
                evidence.available_at_step <= step
                for evidence in packet.eligible_evidence
            )
    except (KeyError, ValueError):
        reconstructable = False
        boundary_preserved = False

    timeline = build_development_timeline(StoredCase(case=case, aggregate_version=0))
    traced_blockers = {
        item.source_work_item_id
        for item in timeline.blocker_propagations
        if item.impacted_milestone_ids
    }
    blocker_ids = {item.work_item_id for item in case.work_items if item.blocker}
    return {
        "development_history_reconstructable": reconstructable,
        "historical_packet_boundary_preserved": boundary_preserved,
        "blocker_impact_traceable": blocker_ids <= traced_blockers,
    }
