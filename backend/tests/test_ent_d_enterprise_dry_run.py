import hashlib
import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from soc_ot.application.contracts import CONTRACT_MODELS
from soc_ot.application.enterprise_dry_run import (
    CanonicalChangeAction,
    EnterpriseCanonicalChange,
    EnterpriseDryRunInput,
    EnterpriseDryRunReport,
    EnterpriseDryRunStatus,
    EnterpriseQualityCode,
    EnterpriseQuarantineStatus,
    EnterpriseResolutionFile,
    load_dry_run_input,
    load_resolution_file,
    run_enterprise_dry_run,
)
from soc_ot.application.enterprise_mapping import (
    load_dirty_fixture_corpus,
    load_mapping_registry,
)
from soc_ot.application.enterprise_sync import (
    EnterpriseSyncMode,
    load_sync_fixture_corpus,
    reconcile_enterprise_pages,
)
from soc_ot.cli.main import main

ROOT = Path(__file__).resolve().parents[2]
ENTERPRISE_FIXTURES = ROOT / "fixtures/enterprise"
REGISTRY_PATH = ENTERPRISE_FIXTURES / "mapping-registry.v1.yaml"
DIRTY_PATH = ENTERPRISE_FIXTURES / "dirty-source-records.v1.yaml"
SYNC_PATH = ENTERPRISE_FIXTURES / "sync-pages.v1.yaml"
DRY_RUN_PATH = ENTERPRISE_FIXTURES / "dry-run-input.v1.yaml"
RESOLUTION_PATH = ENTERPRISE_FIXTURES / "resolution-template.v1.yaml"


def _run(
    *,
    dry_run_input: EnterpriseDryRunInput | None = None,
    resolution_file: EnterpriseResolutionFile | None = None,
) -> EnterpriseDryRunReport:
    registry = load_mapping_registry(REGISTRY_PATH)
    corpus = load_sync_fixture_corpus(SYNC_PATH)
    sync_result = reconcile_enterprise_pages(
        pages=corpus.pages,
        registry=registry,
        policy=corpus.policy,
        mode=EnterpriseSyncMode.FULL,
        transient_failures_before_success=corpus.transient_failures_before_success,
    )
    return run_enterprise_dry_run(
        sync_result=sync_result,
        source_records=[record for page in corpus.pages for record in page.records],
        dirty_corpus=load_dirty_fixture_corpus(DIRTY_PATH),
        registry=registry,
        dry_run_input=dry_run_input or load_dry_run_input(DRY_RUN_PATH),
        resolution_file=resolution_file or load_resolution_file(RESOLUTION_PATH),
    )


def test_dry_run_proposes_create_update_delete_without_authorizing_import() -> None:
    report = _run()

    assert report.status is EnterpriseDryRunStatus.BLOCKED
    assert report.write_performed is False
    assert report.canonical_import_authorized is False
    assert report.summary.create_count == 2
    assert report.summary.update_count == 1
    assert report.summary.delete_count == 2
    assert report.summary.no_change_count == 0
    assert {item.action for item in report.canonical_changes} == {
        CanonicalChangeAction.CREATE,
        CanonicalChangeAction.UPDATE,
        CanonicalChangeAction.DELETE,
    }
    assert [item.canonical_key for item in report.canonical_changes[:2]] == [
        "EVENT-EARLIER",
        "EVENT-LATER",
    ]


def test_quality_report_exposes_every_required_failure_class_and_summary() -> None:
    report = _run()

    assert {item.code for item in report.quality_findings} == set(EnterpriseQualityCode)
    assert report.summary.source_record_count == 25
    assert report.summary.mapped_record_count == 19
    assert report.summary.mapping_coverage == pytest.approx(0.76)
    assert report.summary.quality_finding_count == 15
    assert report.summary.rejected_count == 1
    assert report.summary.quarantined_count == 5
    assert report.summary.freshness_seconds == 97140
    assert any(
        item.code is EnterpriseQualityCode.UNMAPPED_FIELD
        and item.field_name == "project_ref"
        and not item.blocks_import
        for item in report.quality_findings
    )


def test_one_bad_source_is_quarantined_without_dropping_valid_changes() -> None:
    report = _run()

    assert len(report.canonical_changes) == 5
    assert len(report.quarantine_entries) == 8
    assert len({item.quarantine_id for item in report.quarantine_entries}) == 8
    assert all(item.finding_ids for item in report.quarantine_entries)
    assert {
        item.source_identity.external_id
        for item in report.quarantine_entries
        if item.source_identity is not None
    } >= {
        "ISSUE-QUALITY-PROBE",
        "WI-CONFLICT",
        "WI-MISSING",
        "WI-ORDER",
        "WI-SYNC",
        "WI-UNKNOWN",
    }


def test_resolution_is_review_input_not_import_approval() -> None:
    report = _run()
    proposed = [
        item
        for item in report.quarantine_entries
        if item.status is EnterpriseQuarantineStatus.RESOLUTION_PROPOSED
    ]

    assert len(proposed) == 1
    assert report.summary.proposed_resolution_count == 1
    assert report.summary.open_quarantine_count == 7
    assert proposed[0].proposed_resolution is not None
    assert proposed[0].proposed_resolution.action.value == "SOURCE_FIXED"
    assert report.status is EnterpriseDryRunStatus.BLOCKED
    assert report.canonical_import_authorized is False


def test_resolution_rejects_unknown_or_stale_quarantine_target() -> None:
    resolution = load_resolution_file(RESOLUTION_PATH)
    entry = resolution.entries[0]

    unknown = resolution.model_copy(
        update={
            "entries": [
                entry.model_copy(update={"quarantine_id": "0" * 64})
            ]
        }
    )
    with pytest.raises(ValueError, match="unknown quarantine"):
        _run(resolution_file=unknown)

    stale = resolution.model_copy(
        update={
            "entries": [
                entry.model_copy(update={"expected_content_hash": "f" * 64})
            ]
        }
    )
    with pytest.raises(ValueError, match="content hash does not match"):
        _run(resolution_file=stale)


def test_dry_run_is_deterministic_and_does_not_mutate_inputs() -> None:
    dry_run_input = load_dry_run_input(DRY_RUN_PATH)
    resolution = load_resolution_file(RESOLUTION_PATH)
    before_input = dry_run_input.model_dump_json()
    before_resolution = resolution.model_dump_json()

    first = _run(dry_run_input=dry_run_input, resolution_file=resolution)
    second = _run(dry_run_input=dry_run_input, resolution_file=resolution)

    assert first == second
    assert dry_run_input.model_dump_json() == before_input
    assert resolution.model_dump_json() == before_resolution


def test_source_validation_and_dry_run_cli_never_open_runtime_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_database_access() -> None:
        raise AssertionError("enterprise dry-run must not open runtime database")

    monkeypatch.setattr("soc_ot.cli.main.get_runtime_engine", fail_database_access)
    assert main(["enterprise", "validate-source"]) == 0
    output = tmp_path / "dry-run.json"
    assert main(["enterprise", "dry-run", "--output", str(output)]) == 0

    rendered = json.loads(output.read_text(encoding="utf-8"))
    assert rendered["write_performed"] is False
    assert rendered["canonical_import_authorized"] is False
    console = capsys.readouterr().out
    assert "no canonical write performed" in console
    assert "canonical write=false" in console


def test_dry_run_contracts_reject_unsafe_or_ambiguous_values() -> None:
    payload = yaml.safe_load(DRY_RUN_PATH.read_text(encoding="utf-8"))
    payload["as_of"] = "2026-07-24T12:00:00"
    with pytest.raises(ValidationError, match="must include a timezone"):
        EnterpriseDryRunInput.model_validate(payload)

    report = _run()
    change_payload = report.canonical_changes[0].model_dump(mode="json")
    change_payload["action"] = "DELETE"
    with pytest.raises(ValidationError, match="DELETE requires only before_values"):
        EnterpriseCanonicalChange.model_validate(change_payload)

    report_payload = report.model_dump(mode="json")
    report_payload["canonical_import_authorized"] = True
    with pytest.raises(ValidationError):
        EnterpriseDryRunReport.model_validate(report_payload)


def test_enterprise_dry_run_fixtures_are_synthetic_and_hash_pinned() -> None:
    combined = (
        DRY_RUN_PATH.read_text(encoding="utf-8")
        + RESOLUTION_PATH.read_text(encoding="utf-8")
    ).lower()
    assert "jira" not in combined
    assert "confluence" not in combined
    assert "customfield_" not in combined

    manifest = yaml.safe_load(
        (ENTERPRISE_FIXTURES / "manifest.yaml").read_text(encoding="utf-8")
    )
    artifacts = {item["path"]: item["sha256"] for item in manifest["artifacts"]}
    for path in (DRY_RUN_PATH, RESOLUTION_PATH):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifacts[path.name]


def test_ent_d_contracts_are_registered_and_generated() -> None:
    assert CONTRACT_MODELS["enterprise-dry-run-input.v1"] is EnterpriseDryRunInput
    assert CONTRACT_MODELS["enterprise-resolution-file.v1"] is EnterpriseResolutionFile
    assert CONTRACT_MODELS["enterprise-dry-run-report.v1"] is EnterpriseDryRunReport
    for name in (
        "enterprise-dry-run-input.v1",
        "enterprise-resolution-file.v1",
        "enterprise-dry-run-report.v1",
    ):
        assert (ROOT / f"contracts/generated/{name}.schema.json").exists()
