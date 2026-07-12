from typing import Literal

from soc_ot.agents.multi_role import AblationResult
from soc_ot.agents.providers import ReplayProvider, ReviewProvider
from soc_ot.application.evaluation_manifest import PARTITIONS
from soc_ot.application.multi_role import Topology, run_ablation
from soc_ot.application.outcomes import OutcomeSnapshot, advance_outcome
from soc_ot.application.packets import build_observable_case_packet
from soc_ot.domain.models import ExpectedResult, ObservableCase, StrictModel
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
    passed: bool


class OutcomeEvaluation(StrictModel):
    rule_executed: bool
    evidence_revealed: bool
    risk_contained: bool
    passed: bool


class CaseEvaluation(StrictModel):
    schema_version: Literal["case-evaluation.v1"] = "case-evaluation.v1"
    case_id: str
    partition: str
    topology: Topology
    ablation: AblationResult
    outcome: OutcomeSnapshot
    process_evaluation: ProcessEvaluation
    outcome_evaluation: OutcomeEvaluation
    passed: bool


class EvaluationSummary(StrictModel):
    schema_version: Literal["evaluation-summary.v1"] = "evaluation-summary.v1"
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
) -> CaseEvaluation:
    case = fixtures.load_observable(case_id)
    hidden = fixtures.load_hidden(case_id)
    expected = fixtures.load_expected(case_id)
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
    partition = next(name for name, ids in PARTITIONS.items() if case_id in ids)
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


def run_evaluation(fixtures: FixtureRepository, *, topology: Topology = "B3") -> EvaluationSummary:
    results = [
        evaluate_case(fixtures, case_id, topology=topology)
        for case_id in fixtures.case_ids()
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
    checks = {
        "decision_acceptable": ablation.decision.decision_type
        in expected.acceptable_decision_types,
        "mandatory_claims_covered": required_claims <= claim_ids,
        "mandatory_dependencies_covered": set(expected.mandatory_dependency_ids) <= work_ids,
        "mandatory_guardrails_covered": required_metrics <= metric_ids,
        "required_roles_contributed": set(case.required_role_ids)
        <= {review.role_id for review in ablation.dossier.original_reviews},
        "role_differentiation": all(
            bool(review.unique_concern) != review.no_unique_concern
            for review in ablation.dossier.original_reviews
        ),
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
    }
    return ProcessEvaluation(**checks, passed=all(checks.values()))
