from pathlib import Path

import pytest

from soc_ot.agents.multi_role import DossierExecution
from soc_ot.agents.providers import ReplayProvider
from soc_ot.application.evaluation_artifacts import write_evaluation_artifacts
from soc_ot.application.live_evaluation import (
    estimate_stability_batch,
    run_live_stability,
)
from soc_ot.application.repositories import InMemoryCaseRepository
from soc_ot.application.review_runs import (
    InMemoryReviewRunRepository,
    RunConflictError,
    enqueue_dossier_review,
    execute_claimed_run,
)
from soc_ot.infrastructure.fixtures import FixtureRepository

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "fixtures/manifests/eval-2026-07-14.2.yaml"


def _repositories() -> tuple[InMemoryCaseRepository, InMemoryReviewRunRepository]:
    cases = InMemoryCaseRepository()
    fixture = FixtureRepository(ROOT / "fixtures").load_observable("CASE-VR-001")
    cases.save(fixture, event_type="fixture_imported", expected_aggregate_version=None)
    return cases, InMemoryReviewRunRepository()


def test_release_dossier_defaults_to_b2_and_retry_preserves_topology() -> None:
    cases, runs = _repositories()
    queued = enqueue_dossier_review(
        cases,
        runs,
        case_id="CASE-VR-001",
        provider="replay",
        model="replay-v1",
        idempotency_key="step5-default-b2",
    )
    claimed = runs.claim("step5-worker", 60)
    assert claimed is not None
    result = execute_claimed_run(claimed, cases, ReplayProvider())
    assert isinstance(result, DossierExecution)
    assert queued.topology == result.topology == "B2"
    assert result.challenger_provider_result is None
    assert result.chair_provider_result is None
    assert result.dossier.revised_reviews == []

    runs.complete(queued.run_id, "step5-worker", result)
    retry_source = enqueue_dossier_review(
        cases,
        runs,
        case_id="CASE-VR-001",
        provider="replay",
        model="replay-v1",
        idempotency_key="step5-default-b2-retry-source",
    )
    runs.cancel(retry_source.run_id)
    retried = runs.retry(
        retry_source.run_id,
        idempotency_key="step5-default-b2-retry",
    )
    assert retried.topology == "B2"


def test_topology_is_part_of_dossier_idempotency_contract() -> None:
    cases, runs = _repositories()
    enqueue_dossier_review(
        cases,
        runs,
        case_id="CASE-VR-001",
        provider="replay",
        model="replay-v1",
        idempotency_key="step5-topology-conflict",
        topology="B2",
    )
    with pytest.raises(RunConflictError, match="IDEMPOTENCY_KEY_REUSED"):
        enqueue_dossier_review(
            cases,
            runs,
            case_id="CASE-VR-001",
            provider="replay",
            model="replay-v1",
            idempotency_key="step5-topology-conflict",
            topology="B3",
        )


def test_b2_stability_estimate_and_artifact_are_topology_explicit(
    tmp_path: Path,
) -> None:
    estimate = estimate_stability_batch(
        "sealed-unseen",
        3,
        topology="B2",
        max_case_cost_usd=2,
        max_evaluation_cost_usd=25,
        case_timeout_seconds=900,
    )
    assert (estimate.run_count, estimate.semantic_call_count) == (6, 24)

    class FakeLiveProvider(ReplayProvider):
        name = "fake-live"

    result = run_live_stability(
        FixtureRepository(ROOT / "fixtures"),
        FakeLiveProvider(),
        topology="B2",
        partition="validation",
        repeats=5,
        max_cost_usd=25,
    )
    output = write_evaluation_artifacts(
        result,
        manifest_path=MANIFEST_PATH,
        output_root=tmp_path,
        provider="fake-live",
        model_identifier="deterministic-test-double",
        runtime_settings={"evaluation_topology": "B2"},
        run_id="step5-fixed-run",
        batch_estimate=estimate,
    )

    report = (output / "report.md").read_text(encoding="utf-8")
    assert result.stability_gate_passed is True
    assert "Evaluated topology: `B2`" in report
    assert "Stability partition: `validation`" in report
