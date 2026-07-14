from pathlib import Path

import pytest
import yaml

from soc_ot.application.evaluation import CaseEvaluation, run_evaluation
from soc_ot.application.evaluation_manifest import (
    load_evaluation_manifest,
    manifest_case_source,
    manifest_partitions,
    validate_evaluation_manifest,
)
from soc_ot.domain.models import DecisionType
from soc_ot.infrastructure.fixtures import FixtureRepository

ROOT = Path(__file__).resolve().parents[2]
V1_MANIFEST = ROOT / "fixtures/manifests/eval-2026-07-14.1.yaml"
V2_MANIFEST = ROOT / "fixtures/manifests/eval-2026-07-14.2.yaml"


def test_historical_and_v2_release_hashes_are_independently_valid() -> None:
    historical = validate_evaluation_manifest(ROOT / "fixtures", V1_MANIFEST)
    current = validate_evaluation_manifest(ROOT / "fixtures", V2_MANIFEST)

    assert historical.evaluation_release == "eval-2026-07-14.1"
    assert historical.schema_version == "evaluation-manifest.v1"
    assert current.evaluation_release == "eval-2026-07-14.2"
    assert current.schema_version == "evaluation-manifest.v2"


def test_v2_retires_opened_cases_to_development_and_freezes_new_partitions() -> None:
    manifest = load_evaluation_manifest(V2_MANIFEST)
    partitions = manifest_partitions(manifest)

    assert len(manifest.cases) == 12
    assert partitions == {
        "development": [
            "CASE-VR-001",
            "CASE-VR-002",
            "CASE-VR-003",
            "CASE-VR-004",
            "CASE-VR-005",
            "CASE-HO-001",
            "CASE-HO-002",
            "CASE-HO-003",
        ],
        "validation": ["CASE-DT-001", "CASE-DT-002"],
        "sealed-unseen": ["CASE-DT-003", "CASE-DT-004"],
    }
    assert all(
        item.observable_path and item.hidden_path and item.expected_path
        for item in manifest.cases
    )


def test_v2_escalation_policy_does_not_mutate_v1_expected_result() -> None:
    fixtures = FixtureRepository(ROOT / "fixtures")
    manifest = load_evaluation_manifest(V2_MANIFEST)
    source = manifest_case_source(
        next(item for item in manifest.cases if item.case_id == "CASE-VR-005")
    )
    legacy = fixtures.load_expected("CASE-VR-005")
    current = fixtures.load_expected("CASE-VR-005", source.expected_path)

    assert DecisionType.ESCALATE not in legacy.acceptable_decision_types
    assert DecisionType.ESCALATE in current.acceptable_decision_types


def test_v2_replay_evaluates_action_and_development_history_contracts() -> None:
    fixtures = FixtureRepository(ROOT / "fixtures")
    manifest = load_evaluation_manifest(V2_MANIFEST)
    summary = run_evaluation(fixtures, manifest=manifest)

    assert summary.schema_version == "evaluation-summary.v2"
    assert (summary.passed, summary.total) == (12, 12)
    assert all(item.schema_version == "case-evaluation.v2" for item in summary.results)
    assert all(
        item.process_evaluation.decision_action_type_complete
        for item in summary.results
    )
    new_cases = [item for item in summary.results if item.case_id.startswith("CASE-DT-")]
    assert all(
        item.process_evaluation.development_history_reconstructable
        and item.process_evaluation.historical_packet_boundary_preserved
        and item.process_evaluation.blocker_impact_traceable
        for item in new_cases
    )


def test_manifest_hash_tampering_fails_closed(tmp_path: Path) -> None:
    payload = yaml.safe_load(V2_MANIFEST.read_text(encoding="utf-8"))
    payload["cases"][0]["expected_sha256"] = "0" * 64
    tampered = tmp_path / "tampered.yaml"
    tampered.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="CASE-VR-001:expected_sha256"):
        validate_evaluation_manifest(ROOT / "fixtures", tampered)


def test_persisted_case_evaluation_v1_remains_readable() -> None:
    result = run_evaluation(FixtureRepository(ROOT / "fixtures")).results[0]
    payload = result.model_dump(mode="json")
    payload["schema_version"] = "case-evaluation.v1"
    for field in (
        "decision_action_type_complete",
        "development_history_reconstructable",
        "historical_packet_boundary_preserved",
        "blocker_impact_traceable",
    ):
        payload["process_evaluation"].pop(field)

    restored = CaseEvaluation.model_validate(payload)

    assert restored.schema_version == "case-evaluation.v1"
    assert restored.process_evaluation.decision_action_type_complete is True
