from concurrent.futures import ThreadPoolExecutor
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


class AblationEvaluation(StrictModel):
    provider: str
    results: list[CaseEvaluation]
    total_runs: int
    marginal_value_cases: int
    marginal_gate_passed: bool
    stop_rule: Literal["keep_b3", "release_b1", "release_b0"]
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
    marginal_cases = sum(_has_marginal_value(results, case_id) for case_id in case_ids)
    b1_value_cases = sum(_b1_adds_value(results, case_id) for case_id in case_ids)
    stop_rule: Literal["keep_b3", "release_b1", "release_b0"]
    if marginal_cases >= 3:
        stop_rule = "keep_b3"
    elif b1_value_cases > 0:
        stop_rule = "release_b1"
    else:
        stop_rule = "release_b0"
    return AblationEvaluation(
        provider=provider.name,
        results=results,
        total_runs=len(results),
        marginal_value_cases=marginal_cases,
        marginal_gate_passed=marginal_cases >= 3,
        stop_rule=stop_rule,
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


def _has_marginal_value(results: list[CaseEvaluation], case_id: str) -> bool:
    b1 = _by_topology(results, case_id, "B1")
    b3 = _by_topology(results, case_id, "B3")
    b1_concerns = {
        item.unique_concern for item in b1.ablation.dossier.original_reviews if item.unique_concern
    }
    b3_concerns = {
        item.unique_concern for item in b3.ablation.dossier.original_reviews if item.unique_concern
    }
    b1_safeguards = {item.metric_id for item in b1.ablation.decision.safeguards}
    b3_safeguards = {item.metric_id for item in b3.ablation.decision.safeguards}
    return bool((b3_concerns - b1_concerns) or (b3_safeguards - b1_safeguards))


def _b1_adds_value(results: list[CaseEvaluation], case_id: str) -> bool:
    b0 = _by_topology(results, case_id, "B0")
    b1 = _by_topology(results, case_id, "B1")
    return b0.ablation.decision != b1.ablation.decision or bool(
        b1.ablation.dossier.original_reviews[0].unique_concern
    )


def _by_topology(
    results: list[CaseEvaluation], case_id: str, topology: Topology
) -> CaseEvaluation:
    return next(item for item in results if item.case_id == case_id and item.topology == topology)


def _policy_compliant(result: CaseEvaluation) -> bool:
    process = result.process_evaluation
    return all(
        [
            process.required_roles_contributed,
            process.role_differentiation,
            process.unresolved_uncertainty_visible,
            process.conditional_control_complete,
        ]
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
