from pathlib import Path
from time import perf_counter

import pytest
from fastapi.testclient import TestClient

from soc_ot.agents.providers import ReplayProvider
from soc_ot.api.main import create_app
from soc_ot.application.evaluation import run_evaluation
from soc_ot.application.evaluation_artifacts import write_evaluation_artifacts
from soc_ot.application.live_evaluation import (
    estimate_ablation_batch,
    estimate_stability_batch,
    run_live_stability,
)
from soc_ot.application.packets import build_observable_case_packet
from soc_ot.application.repositories import InMemoryCaseRepository
from soc_ot.application.review_runs import InMemoryReviewRunRepository
from soc_ot.infrastructure.fixtures import FixtureRepository

ROOT = Path(__file__).resolve().parents[2]


def test_replay_evaluation_performance_and_zero_cost() -> None:
    started = perf_counter()
    summary = run_evaluation(FixtureRepository(ROOT / "fixtures"))
    elapsed = perf_counter() - started

    assert summary.passed == 8
    assert elapsed < 2.0
    assert all(result.ablation.estimated_cost_usd == 0 for result in summary.results)


def test_packet_build_performance() -> None:
    case = FixtureRepository(ROOT / "fixtures").load_observable("CASE-VR-001")
    started = perf_counter()
    for _ in range(100):
        build_observable_case_packet(case)
    average_ms = (perf_counter() - started) * 1000 / 100

    assert average_ms < 20


def test_telemetry_endpoint_reports_completed_usage() -> None:
    cases = InMemoryCaseRepository()
    fixture = FixtureRepository(ROOT / "fixtures").load_observable("CASE-VR-001")
    cases.save(fixture, event_type="fixture_imported", expected_aggregate_version=None)
    client = TestClient(create_app(cases, InMemoryReviewRunRepository()))

    response = client.get("/api/v1/telemetry/agent-runs")

    assert response.status_code == 200
    assert response.json() == {
        "run_count": 0,
        "completed_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost_usd": 0.0,
        "provider_attempts": 0,
    }


def test_live_batch_estimates_abort_before_over_budget_calls() -> None:
    ablation = estimate_ablation_batch(
        max_case_cost_usd=2,
        max_evaluation_cost_usd=25,
        case_timeout_seconds=900,
    )
    validation = estimate_stability_batch(
        "validation",
        5,
        max_case_cost_usd=2,
        max_evaluation_cost_usd=25,
        case_timeout_seconds=900,
    )
    assert (ablation.run_count, ablation.semantic_call_count) == (20, 65)
    assert ablation.within_budget is False
    assert (validation.run_count, validation.semantic_call_count) == (10, 80)
    assert validation.within_budget is True


def test_stability_runner_uses_only_b3_and_applies_per_case_threshold() -> None:
    class FakeLiveProvider(ReplayProvider):
        name = "fake-live"

    result = run_live_stability(
        FixtureRepository(ROOT / "fixtures"),
        FakeLiveProvider(),
        partition="validation",
        repeats=5,
        max_cost_usd=25,
    )
    assert result.total_runs == 10
    assert all(item.topology == "B3" for item in result.results)
    assert result.stability_gate_passed is True


def test_stability_runner_records_provider_failure_instead_of_aborting() -> None:
    class FailingLiveProvider(ReplayProvider):
        name = "failing-live"

        def review(self, packet, role_id):
            if packet.case_id == "CASE-VR-005":
                raise ConnectionError("synthetic unavailable")
            return super().review(packet, role_id)

    result = run_live_stability(
        FixtureRepository(ROOT / "fixtures"),
        FailingLiveProvider(),
        partition="validation",
        repeats=1,
        max_cost_usd=25,
    )

    assert result.total_runs == 2
    assert len(result.results) == 1
    assert [failure.case_id for failure in result.failures] == ["CASE-VR-005"]
    assert result.stability_gate_passed is False


def test_evaluation_artifact_bundle_is_complete_and_immutable(tmp_path: Path) -> None:
    summary = run_evaluation(FixtureRepository(ROOT / "fixtures"))
    arguments = {
        "manifest_path": ROOT / "fixtures/manifests/eval-2026-07-14.1.yaml",
        "output_root": tmp_path,
        "provider": "replay",
        "model_identifier": "deterministic-replay",
        "runtime_settings": {"llm_mode": "replay"},
        "run_id": "fixed-test-run",
    }

    output = write_evaluation_artifacts(summary, **arguments)

    assert {path.name for path in output.iterdir()} == {
        "manifest.snapshot.yaml",
        "environment.json",
        "normalized_results.jsonl",
        "process_scores.json",
        "outcome_scores.json",
        "policy_violations.json",
        "report.md",
    }
    assert (
        len(
            (output / "normalized_results.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        == 8
    )
    assert '"code_revision": "sha256:' in (output / "environment.json").read_text(
        encoding="utf-8"
    )
    assert "Gate: **PASS**" in (output / "report.md").read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        write_evaluation_artifacts(summary, **arguments)
