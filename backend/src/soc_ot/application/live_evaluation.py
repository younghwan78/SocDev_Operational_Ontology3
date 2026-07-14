from concurrent.futures import ThreadPoolExecutor
from math import ceil
from typing import Literal

from pydantic import Field

from soc_ot.agents.providers import ReviewProvider
from soc_ot.application.evaluation import CaseEvaluation, evaluate_case
from soc_ot.application.evaluation_manifest import (
    V2_CASE_SOURCES,
    EvaluationCaseSource,
    EvaluationManifest,
    manifest_case_source,
)
from soc_ot.application.multi_role import Topology
from soc_ot.domain.models import StrictModel
from soc_ot.infrastructure.fixtures import FixtureRepository


class LiveBatchEstimate(StrictModel):
    run_count: int
    semantic_call_count: int
    timeout_envelope_seconds: int
    maximum_cost_usd: float
    within_budget: bool


class TopologyDeltaEvaluation(StrictModel):
    baseline_topology: Topology
    candidate_topology: Topology
    required_marginal_cases: int
    marginal_case_ids: list[str]
    quality_regression_case_ids: list[str]
    policy_failure_case_ids: list[str]
    gate_passed: bool


class AblationEvaluation(StrictModel):
    schema_version: Literal["ablation-evaluation.v2"] = "ablation-evaluation.v2"
    provider: str
    results: list[CaseEvaluation]
    total_runs: int
    marginal_value_cases: int
    marginal_gate_passed: bool
    b1_over_b0: TopologyDeltaEvaluation
    b2_over_b1: TopologyDeltaEvaluation
    b3_over_b2: TopologyDeltaEvaluation
    selected_topology: Topology
    stop_rule: Literal["keep_b3", "release_b2", "release_b1", "release_b0"]
    release_gate_passed: bool
    estimated_cost_usd: float = Field(ge=0)


class LiveEvaluationFailure(StrictModel):
    case_id: str
    topology: Topology
    error_code: str


class StabilityEvaluation(StrictModel):
    provider: str
    partition: Literal["validation", "sealed-unseen"]
    repeats: int
    results: list[CaseEvaluation]
    failures: list[LiveEvaluationFailure] = Field(default_factory=list)
    total_runs: int
    acceptable_runs: int
    policy_compliant_runs: int
    stability_gate_passed: bool
    estimated_cost_usd: float = Field(ge=0)
    within_cost_envelope: bool


def estimate_ablation_batch(
    *, max_case_cost_usd: float, max_evaluation_cost_usd: float,
    case_timeout_seconds: int, manifest: EvaluationManifest | None = None,
) -> LiveBatchEstimate:
    case_count = len(_release_sources(manifest, {"validation", "sealed-unseen"}))
    run_count = case_count * 4
    calls_per_case = 0 + 1 + 4 + 8
    return _estimate(
        run_count,
        case_count * calls_per_case,
        max_case_cost_usd,
        max_evaluation_cost_usd,
        case_timeout_seconds,
    )


def estimate_stability_batch(
    partition: Literal["validation", "sealed-unseen"],
    repeats: int,
    *,
    max_case_cost_usd: float,
    max_evaluation_cost_usd: float,
    case_timeout_seconds: int,
    manifest: EvaluationManifest | None = None,
) -> LiveBatchEstimate:
    run_count = len(_release_sources(manifest, {partition})) * repeats
    return _estimate(
        run_count,
        run_count * 8,
        max_case_cost_usd,
        max_evaluation_cost_usd,
        case_timeout_seconds,
    )


def run_live_ablation(
    fixtures: FixtureRepository,
    provider: ReviewProvider,
    *,
    max_cost_usd: float,
    max_workers: int = 1,
    manifest: EvaluationManifest | None = None,
) -> AblationEvaluation:
    if provider.name == "replay":
        raise ValueError("LIVE_PROVIDER_REQUIRED")
    case_sources = _release_sources(manifest, {"validation", "sealed-unseen"})
    case_ids = [item.case_id for item in case_sources]
    topologies: tuple[Topology, ...] = ("B0", "B1", "B2", "B3")
    jobs: list[tuple[EvaluationCaseSource, Topology]] = [
        (source, topology)
        for source in case_sources
        for topology in topologies
    ]
    results = _run_jobs(fixtures, provider, jobs, max_workers)
    _enforce_actual_cost(results, max_cost_usd)
    return classify_ablation_results(provider.name, results, case_ids)


def classify_ablation_results(
    provider: str,
    results: list[CaseEvaluation],
    case_ids: list[str],
) -> AblationEvaluation:
    if not case_ids:
        raise ValueError("ABLATION_CASES_REQUIRED")
    multi_role_threshold = ceil(len(case_ids) * 0.75)
    b1_over_b0 = _evaluate_topology_delta(
        results, case_ids, "B0", "B1", required_marginal_cases=1
    )
    b2_over_b1 = _evaluate_topology_delta(
        results,
        case_ids,
        "B1",
        "B2",
        required_marginal_cases=multi_role_threshold,
    )
    b3_over_b2 = _evaluate_topology_delta(
        results,
        case_ids,
        "B2",
        "B3",
        required_marginal_cases=multi_role_threshold,
    )
    if b3_over_b2.gate_passed:
        selected_topology: Topology = "B3"
        stop_rule: Literal[
            "keep_b3", "release_b2", "release_b1", "release_b0"
        ] = "keep_b3"
    elif b2_over_b1.gate_passed:
        selected_topology = "B2"
        stop_rule = "release_b2"
    elif b1_over_b0.gate_passed:
        selected_topology = "B1"
        stop_rule = "release_b1"
    else:
        selected_topology = "B0"
        stop_rule = "release_b0"
    release_gate_passed = all(
        _policy_compliant(_by_topology(results, case_id, selected_topology))
        for case_id in case_ids
    )
    return AblationEvaluation(
        provider=provider,
        results=results,
        total_runs=len(results),
        marginal_value_cases=len(b2_over_b1.marginal_case_ids),
        marginal_gate_passed=b2_over_b1.gate_passed,
        b1_over_b0=b1_over_b0,
        b2_over_b1=b2_over_b1,
        b3_over_b2=b3_over_b2,
        selected_topology=selected_topology,
        stop_rule=stop_rule,
        release_gate_passed=release_gate_passed,
        estimated_cost_usd=_actual_cost(results),
    )


def run_live_stability(
    fixtures: FixtureRepository,
    provider: ReviewProvider,
    *,
    partition: Literal["validation", "sealed-unseen"],
    repeats: int,
    max_cost_usd: float,
    max_workers: int = 1,
    manifest: EvaluationManifest | None = None,
) -> StabilityEvaluation:
    if provider.name == "replay":
        raise ValueError("LIVE_PROVIDER_REQUIRED")
    case_sources = _release_sources(manifest, {partition})
    jobs: list[tuple[EvaluationCaseSource, Topology]] = [
        (source, "B3")
        for _ in range(repeats)
        for source in case_sources
    ]
    results, failures = _run_jobs_capturing_failures(
        fixtures, provider, jobs, max_workers
    )
    _enforce_actual_cost(results, max_cost_usd)
    acceptable = sum(item.process_evaluation.decision_acceptable for item in results)
    policy_compliant = sum(_policy_compliant(item) for item in results)
    required_acceptable = 4 if partition == "validation" else 2
    per_case_stable = all(
        sum(
            result.process_evaluation.decision_acceptable
            for result in results
            if result.case_id == case_id
        )
        >= required_acceptable
        for case_id in (item.case_id for item in case_sources)
    )
    gate_passed = not failures and per_case_stable and policy_compliant == len(results)
    actual_cost = _actual_cost(results)
    return StabilityEvaluation(
        provider=provider.name,
        partition=partition,
        repeats=repeats,
        results=results,
        failures=failures,
        total_runs=len(jobs),
        acceptable_runs=acceptable,
        policy_compliant_runs=policy_compliant,
        stability_gate_passed=gate_passed,
        estimated_cost_usd=actual_cost,
        within_cost_envelope=actual_cost <= max_cost_usd,
    )


def _estimate(
    run_count: int,
    semantic_call_count: int,
    max_case_cost_usd: float,
    max_evaluation_cost_usd: float,
    case_timeout_seconds: int,
) -> LiveBatchEstimate:
    maximum_cost = run_count * max_case_cost_usd
    return LiveBatchEstimate(
        run_count=run_count,
        semantic_call_count=semantic_call_count,
        timeout_envelope_seconds=run_count * case_timeout_seconds,
        maximum_cost_usd=maximum_cost,
        within_budget=maximum_cost <= max_evaluation_cost_usd,
    )


def _evaluate_topology_delta(
    results: list[CaseEvaluation],
    case_ids: list[str],
    baseline_topology: Topology,
    candidate_topology: Topology,
    *,
    required_marginal_cases: int,
) -> TopologyDeltaEvaluation:
    marginal_case_ids: list[str] = []
    quality_regression_case_ids: list[str] = []
    policy_failure_case_ids: list[str] = []
    for case_id in case_ids:
        baseline = _by_topology(results, case_id, baseline_topology)
        candidate = _by_topology(results, case_id, candidate_topology)
        regressed = _quality_regressed(baseline, candidate)
        policy_failed = not _policy_compliant(candidate)
        if regressed:
            quality_regression_case_ids.append(case_id)
        if policy_failed:
            policy_failure_case_ids.append(case_id)
        if (
            not regressed
            and not policy_failed
            and _adds_incremental_value(baseline, candidate)
        ):
            marginal_case_ids.append(case_id)
    return TopologyDeltaEvaluation(
        baseline_topology=baseline_topology,
        candidate_topology=candidate_topology,
        required_marginal_cases=required_marginal_cases,
        marginal_case_ids=marginal_case_ids,
        quality_regression_case_ids=quality_regression_case_ids,
        policy_failure_case_ids=policy_failure_case_ids,
        gate_passed=(
            len(marginal_case_ids) >= required_marginal_cases
            and not quality_regression_case_ids
            and not policy_failure_case_ids
        ),
    )


def _adds_incremental_value(
    baseline: CaseEvaluation, candidate: CaseEvaluation
) -> bool:
    baseline_roles = {
        item.role_id
        for item in baseline.ablation.dossier.original_reviews
        if item.unique_concern
    }
    candidate_roles = {
        item.role_id
        for item in candidate.ablation.dossier.original_reviews
        if item.unique_concern
    }
    baseline_safeguards = {
        item.metric_id for item in baseline.ablation.decision.safeguards
    }
    candidate_safeguards = {
        item.metric_id for item in candidate.ablation.decision.safeguards
    }
    challenger = candidate.ablation.dossier.challenger
    challenger_added_value = bool(
        challenger
        and challenger.objections
        and baseline.ablation.dossier.challenger is None
    )
    return bool(
        (candidate_roles - baseline_roles)
        or (candidate_safeguards - baseline_safeguards)
        or challenger_added_value
        or _quality_improved(baseline, candidate)
    )


def _quality_improved(
    baseline: CaseEvaluation, candidate: CaseEvaluation
) -> bool:
    return any(
        not getattr(baseline.process_evaluation, field)
        and getattr(candidate.process_evaluation, field)
        for field in _PROCESS_QUALITY_FIELDS
    )


def _quality_regressed(
    baseline: CaseEvaluation, candidate: CaseEvaluation
) -> bool:
    return any(
        getattr(baseline.process_evaluation, field)
        and not getattr(candidate.process_evaluation, field)
        for field in _PROCESS_QUALITY_FIELDS
    )


def _by_topology(
    results: list[CaseEvaluation], case_id: str, topology: Topology
) -> CaseEvaluation:
    return next(item for item in results if item.case_id == case_id and item.topology == topology)


def _policy_compliant(result: CaseEvaluation) -> bool:
    return result.process_evaluation.passed


_PROCESS_QUALITY_FIELDS = (
    "decision_acceptable",
    "mandatory_claims_covered",
    "mandatory_dependencies_covered",
    "mandatory_guardrails_covered",
    "required_roles_contributed",
    "role_differentiation",
    "unresolved_uncertainty_visible",
    "conditional_control_complete",
    "decision_action_complete",
    "decision_action_type_complete",
    "development_history_reconstructable",
    "historical_packet_boundary_preserved",
    "blocker_impact_traceable",
)


def _actual_cost(results: list[CaseEvaluation]) -> float:
    return sum(item.ablation.estimated_cost_usd for item in results)


def _enforce_actual_cost(results: list[CaseEvaluation], max_cost_usd: float) -> None:
    if _actual_cost(results) > max_cost_usd:
        raise RuntimeError("LIVE_EVALUATION_COST_ENVELOPE_EXCEEDED")


def _run_jobs(
    fixtures: FixtureRepository,
    provider: ReviewProvider,
    jobs: list[tuple[EvaluationCaseSource, Topology]],
    max_workers: int,
) -> list[CaseEvaluation]:
    def execute(job: tuple[EvaluationCaseSource, Topology]) -> CaseEvaluation:
        source, topology = job
        try:
            return evaluate_case(
                fixtures,
                source.case_id,
                topology=topology,
                provider=provider,
                source=source,
            )
        except Exception as error:
            raise RuntimeError(
                f"LIVE_EVALUATION_JOB_FAILED:{source.case_id}:{topology}:{error}"
            ) from error

    if max_workers <= 1:
        return [execute(job) for job in jobs]
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(execute, jobs))


def _run_jobs_capturing_failures(
    fixtures: FixtureRepository,
    provider: ReviewProvider,
    jobs: list[tuple[EvaluationCaseSource, Topology]],
    max_workers: int,
) -> tuple[list[CaseEvaluation], list[LiveEvaluationFailure]]:
    def execute(
        job: tuple[EvaluationCaseSource, Topology],
    ) -> CaseEvaluation | LiveEvaluationFailure:
        source, topology = job
        try:
            return evaluate_case(
                fixtures,
                source.case_id,
                topology=topology,
                provider=provider,
                source=source,
            )
        except Exception as error:
            code = str(getattr(error, "code", "") or error or type(error).__name__)
            return LiveEvaluationFailure(
                case_id=source.case_id,
                topology=topology,
                error_code=code[:200],
            )

    if max_workers <= 1:
        items = [execute(job) for job in jobs]
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            items = list(executor.map(execute, jobs))
    return (
        [item for item in items if isinstance(item, CaseEvaluation)],
        [item for item in items if isinstance(item, LiveEvaluationFailure)],
    )


def _release_sources(
    manifest: EvaluationManifest | None,
    partitions: set[str],
) -> list[EvaluationCaseSource]:
    sources = (
        [manifest_case_source(item) for item in manifest.cases]
        if manifest is not None
        else V2_CASE_SOURCES
    )
    return [item for item in sources if item.partition in partitions]
