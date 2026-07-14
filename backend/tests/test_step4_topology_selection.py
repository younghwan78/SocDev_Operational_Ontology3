from collections.abc import Callable
from pathlib import Path

import pytest

from soc_ot.agents.providers import ReplayProvider
from soc_ot.application.evaluation import CaseEvaluation
from soc_ot.application.evaluation_artifacts import write_evaluation_artifacts
from soc_ot.application.evaluation_manifest import load_evaluation_manifest
from soc_ot.application.live_evaluation import (
    AblationEvaluation,
    classify_ablation_results,
    run_live_ablation,
)
from soc_ot.application.multi_role import Topology
from soc_ot.infrastructure.fixtures import FixtureRepository

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "fixtures/manifests/eval-2026-07-14.2.yaml"
CASE_IDS = ["CASE-DT-001", "CASE-DT-002", "CASE-DT-003", "CASE-DT-004"]


class FakeLiveProvider(ReplayProvider):
    name = "fake-live"


@pytest.fixture(scope="module")
def replay_ablation() -> AblationEvaluation:
    return run_live_ablation(
        FixtureRepository(ROOT / "fixtures"),
        FakeLiveProvider(),
        max_cost_usd=0,
        manifest=load_evaluation_manifest(MANIFEST_PATH),
    )


def test_step4_separates_each_topology_delta(
    replay_ablation: AblationEvaluation,
) -> None:
    assert replay_ablation.total_runs == 16
    assert replay_ablation.b1_over_b0.marginal_case_ids == CASE_IDS
    assert replay_ablation.b1_over_b0.required_marginal_cases == 1
    assert replay_ablation.b2_over_b1.marginal_case_ids == CASE_IDS
    assert replay_ablation.b2_over_b1.required_marginal_cases == 3
    assert replay_ablation.b3_over_b2.marginal_case_ids == CASE_IDS
    assert replay_ablation.b3_over_b2.required_marginal_cases == 3
    assert replay_ablation.selected_topology == "B3"
    assert replay_ablation.stop_rule == "keep_b3"
    assert replay_ablation.release_gate_passed is True


def test_stop_rule_can_release_b2_when_challenger_adds_no_value(
    replay_ablation: AblationEvaluation,
) -> None:
    results = _replace_topology(
        replay_ablation.results,
        "B3",
        lambda item, all_results: _copy_as_candidate(
            item, _find(all_results, item.case_id, "B2"), "B3"
        ),
    )

    selection = classify_ablation_results("synthetic", results, CASE_IDS)

    assert selection.b3_over_b2.marginal_case_ids == []
    assert selection.selected_topology == "B2"
    assert selection.stop_rule == "release_b2"
    assert selection.release_gate_passed is True


def test_stop_rule_can_release_b1_when_multi_role_policy_fails(
    replay_ablation: AblationEvaluation,
) -> None:
    results = _fail_process_for_topologies(replay_ablation.results, {"B2", "B3"})

    selection = classify_ablation_results("synthetic", results, CASE_IDS)

    assert selection.b2_over_b1.policy_failure_case_ids == CASE_IDS
    assert selection.b3_over_b2.policy_failure_case_ids == CASE_IDS
    assert selection.selected_topology == "B1"
    assert selection.stop_rule == "release_b1"
    assert selection.release_gate_passed is True


def test_stop_rule_falls_back_to_b0_and_reports_failed_release_gate(
    replay_ablation: AblationEvaluation,
) -> None:
    results = _fail_process_for_topologies(
        replay_ablation.results, {"B1", "B2", "B3"}
    )

    selection = classify_ablation_results("synthetic", results, CASE_IDS)

    assert selection.selected_topology == "B0"
    assert selection.stop_rule == "release_b0"
    assert selection.release_gate_passed is False


def test_quality_regression_blocks_b3_even_when_it_has_a_challenger(
    replay_ablation: AblationEvaluation,
) -> None:
    target_case = CASE_IDS[0]

    def regress_one(
        item: CaseEvaluation, _: list[CaseEvaluation]
    ) -> CaseEvaluation:
        if item.case_id != target_case:
            return item
        process = item.process_evaluation.model_copy(
            update={"decision_action_type_complete": False, "passed": False}
        )
        return item.model_copy(update={"process_evaluation": process, "passed": False})

    results = _replace_topology(replay_ablation.results, "B3", regress_one)

    selection = classify_ablation_results("synthetic", results, CASE_IDS)

    assert selection.b3_over_b2.quality_regression_case_ids == [target_case]
    assert selection.b3_over_b2.gate_passed is False
    assert selection.stop_rule == "release_b2"


def test_ablation_artifact_reports_only_selected_topology_gate(
    replay_ablation: AblationEvaluation, tmp_path: Path
) -> None:
    output = write_evaluation_artifacts(
        replay_ablation,
        manifest_path=MANIFEST_PATH,
        output_root=tmp_path,
        provider="fake-live",
        model_identifier="deterministic-test-double",
        runtime_settings={"evaluation_surface": "test-double"},
        run_id="step4-fixed-run",
    )

    report = (output / "report.md").read_text(encoding="utf-8")
    violations = (output / "policy_violations.json").read_text(encoding="utf-8")
    assert "Gate: **PASS**" in report
    assert "Selected topology: `B3`" in report
    assert "Stop rule: `keep_b3`" in report
    assert "stability is not evaluated here" in report
    assert "Selected case runs passed: 4/4" in report
    assert "Total comparison runs: 16" in report
    assert violations == "[]\n"


def _replace_topology(
    results: list[CaseEvaluation],
    topology: Topology,
    replacement: Callable[
        [CaseEvaluation, list[CaseEvaluation]], CaseEvaluation
    ],
) -> list[CaseEvaluation]:
    return [
        replacement(item, results) if item.topology == topology else item
        for item in results
    ]


def _copy_as_candidate(
    target: CaseEvaluation, source: CaseEvaluation, topology: Topology
) -> CaseEvaluation:
    ablation = source.ablation.model_copy(update={"topology": topology})
    return source.model_copy(update={"topology": topology, "ablation": ablation})


def _fail_process_for_topologies(
    results: list[CaseEvaluation], topologies: set[Topology]
) -> list[CaseEvaluation]:
    changed: list[CaseEvaluation] = []
    for item in results:
        if item.topology not in topologies:
            changed.append(item)
            continue
        process = item.process_evaluation.model_copy(
            update={"decision_action_type_complete": False, "passed": False}
        )
        changed.append(
            item.model_copy(update={"process_evaluation": process, "passed": False})
        )
    return changed


def _find(
    results: list[CaseEvaluation], case_id: str, topology: Topology
) -> CaseEvaluation:
    return next(
        item
        for item in results
        if item.case_id == case_id and item.topology == topology
    )
