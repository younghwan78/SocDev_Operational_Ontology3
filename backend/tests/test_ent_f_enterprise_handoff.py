import hashlib
import shutil
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from soc_ot.application.contracts import CONTRACT_MODELS
from soc_ot.application.enterprise_handoff import (
    EnterpriseEnvironmentWorksheet,
    EnterpriseHandoffMappingTemplate,
    EnterpriseHandoffPackage,
    EnterprisePilotRunbook,
    HandoffCheckStatus,
    HandoffRunbookStage,
    HandoffSourceKind,
    HandoffStageAuthority,
    HandoffValueOwnership,
    load_and_validate_handoff_package,
)
from soc_ot.application.enterprise_mapping import StructuredCandidateKind
from soc_ot.cli.main import main

ROOT = Path(__file__).resolve().parents[2]
HANDOFF_ROOT = ROOT / "fixtures/enterprise/handoff"
PACKAGE_PATH = HANDOFF_ROOT / "handoff-package.v1.yaml"


def _validated():
    return load_and_validate_handoff_package(HANDOFF_ROOT)


def test_package_is_hash_pinned_and_covers_both_source_kinds() -> None:
    handoff = _validated()

    assert handoff.package.package_status == "READY_FOR_INTERNAL_DISCOVERY"
    assert {item.source_kind for item in handoff.mapping_templates} == set(
        HandoffSourceKind
    )
    for artifact in handoff.package.artifacts:
        assert (
            hashlib.sha256((HANDOFF_ROOT / artifact.path).read_bytes()).hexdigest()
            == artifact.sha256
        )
    fixture_manifest = yaml.safe_load(
        (HANDOFF_ROOT.parent / "manifest.yaml").read_text(encoding="utf-8")
    )
    fixture_hashes = {
        item["path"]: item["sha256"] for item in fixture_manifest["artifacts"]
    }
    for path in HANDOFF_ROOT.glob("*.yaml"):
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest()
            == fixture_hashes[f"handoff/{path.name}"]
        )


def test_mapping_templates_cover_project_operation_candidate_kinds() -> None:
    handoff = _validated()
    by_source = {item.source_kind: item for item in handoff.mapping_templates}

    assert {
        item.target_kind
        for item in by_source[HandoffSourceKind.WORK_TRACKER].object_mappings
    } == {
        StructuredCandidateKind.PROJECT,
        StructuredCandidateKind.WORK_ITEM,
        StructuredCandidateKind.ISSUE,
        StructuredCandidateKind.EVENT,
    }
    assert {
        item.target_kind
        for item in by_source[HandoffSourceKind.KNOWLEDGE_BASE].object_mappings
    } == {StructuredCandidateKind.EVIDENCE}
    assert all(
        row.ownership is HandoffValueOwnership.INTERNAL_REQUIRED
        for template in handoff.mapping_templates
        for mapping in template.object_mappings
        for row in mapping.field_mappings
    )


def test_environment_worksheet_separates_unconfirmed_internal_values() -> None:
    worksheet = _validated().worksheet
    items = [item for section in worksheet.sections for item in section.items]
    topics = {item.topic for item in items}

    assert {
        "DEPLOYMENT_VERSION",
        "NETWORK_PROXY_CERTIFICATE",
        "IDENTITY_ACCESS_METHOD",
        "SECRET_MANAGER_REFERENCE",
        "ACL_CLASSIFICATION",
        "RETENTION_DELETION",
        "RATE_LIMIT",
        "DATA_OWNER",
        "SECURITY_OWNER",
        "HUMAN_DECISION_AUTHORITY",
        "MODEL_PROVIDER_POLICY",
    } <= topics
    assert all(item.value is None and item.evidence_ref is None for item in items)
    assert all(
        item.status is HandoffCheckStatus.UNCONFIRMED_INTERNAL for item in items
    )
    protected = {item.topic for item in items if item.must_not_commit_value}
    assert protected == {"IDENTITY_ACCESS_METHOD", "SECRET_MANAGER_REFERENCE"}


def test_pilot_is_one_project_read_only_and_not_authorized() -> None:
    runbook = _validated().runbook
    scope = runbook.pilot_scope

    assert scope.max_project_count == 1
    assert scope.allowed_project_refs == []
    assert scope.read_only is True
    assert scope.write_back_enabled is False
    assert scope.canonical_import_authorized is False
    assert runbook.live_use_authorized is False
    assert len(runbook.rollback.triggers) >= 4
    assert len(runbook.rollback.actions) >= 4


def test_runbook_has_fixed_order_and_company_gate() -> None:
    steps = _validated().runbook.steps

    assert [item.stage for item in steps] == list(HandoffRunbookStage)
    assert all(
        item.authority is HandoffStageAuthority.EXTERNAL_EXECUTABLE
        and item.command
        for item in steps[:3]
    )
    assert all(
        item.authority is HandoffStageAuthority.COMPANY_APPROVAL_REQUIRED
        and item.command is None
        for item in steps[3:]
    )


def test_expected_output_has_explicit_zero_thresholds_and_is_not_evaluated() -> None:
    metrics = _validated().runbook.expected_metrics
    by_id = {item.metric_id: item for item in metrics}

    assert {
        "acl_exposure_total",
        "credential_leak_total",
        "write_attempt_total",
        "silent_drop_total",
        "duplicate_event_total",
        "reconciliation_mismatch_total",
    } <= set(by_id)
    assert all(item.expected_value == 0 for item in metrics)
    assert all(item.status is HandoffCheckStatus.NOT_EVALUATED for item in metrics)


def test_checklist_distinguishes_external_evidence_from_internal_discovery() -> None:
    checklist = _validated().package.checklist
    externally_verified = [
        item
        for item in checklist
        if item.ownership is HandoffValueOwnership.EXTERNALLY_VERIFIED
    ]
    internally_required = [
        item
        for item in checklist
        if item.ownership is HandoffValueOwnership.INTERNAL_REQUIRED
    ]

    assert len(externally_verified) == 5
    assert all(
        item.status is HandoffCheckStatus.VERIFIED_EXTERNALLY
        and item.evidence_ref
        and (ROOT / item.evidence_ref).is_file()
        for item in externally_verified
    )
    assert len(internally_required) >= 4
    assert all(
        item.status is HandoffCheckStatus.UNCONFIRMED_INTERNAL
        and item.evidence_ref is None
        for item in internally_required
    )


def test_handoff_validator_rejects_changed_artifact(
    tmp_path: Path,
) -> None:
    copied = tmp_path / "handoff"
    shutil.copytree(HANDOFF_ROOT, copied)
    path = copied / "environment-worksheet.v1.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="hash mismatch"):
        load_and_validate_handoff_package(copied)


def test_contracts_reject_live_values_writeback_and_import_commands() -> None:
    package = yaml.safe_load(PACKAGE_PATH.read_text(encoding="utf-8"))
    package["write_back_implemented"] = True
    with pytest.raises(ValidationError):
        EnterpriseHandoffPackage.model_validate(package)

    worksheet_path = HANDOFF_ROOT / "environment-worksheet.v1.yaml"
    worksheet = yaml.safe_load(worksheet_path.read_text(encoding="utf-8"))
    worksheet["sections"][0]["items"][0]["value"] = "internal-value"
    with pytest.raises(ValidationError, match="filled inside company"):
        EnterpriseEnvironmentWorksheet.model_validate(worksheet)

    runbook_path = HANDOFF_ROOT / "pilot-runbook.v1.yaml"
    runbook = yaml.safe_load(runbook_path.read_text(encoding="utf-8"))
    runbook["steps"][3]["command"] = "perform-live-import"
    with pytest.raises(ValidationError, match="cannot ship an execution command"):
        EnterprisePilotRunbook.model_validate(runbook)


def test_contract_rejects_more_than_one_project_and_stage_reordering() -> None:
    runbook_path = HANDOFF_ROOT / "pilot-runbook.v1.yaml"
    payload = yaml.safe_load(runbook_path.read_text(encoding="utf-8"))
    payload["pilot_scope"]["allowed_project_refs"] = ["PROJECT-A", "PROJECT-B"]
    with pytest.raises(ValidationError):
        EnterprisePilotRunbook.model_validate(payload)

    payload = yaml.safe_load(runbook_path.read_text(encoding="utf-8"))
    payload["steps"][0]["stage"], payload["steps"][1]["stage"] = (
        payload["steps"][1]["stage"],
        payload["steps"][0]["stage"],
    )
    with pytest.raises(ValidationError, match="stage order is fixed"):
        EnterprisePilotRunbook.model_validate(payload)


def test_validate_handoff_cli_never_opens_database(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_database_access() -> None:
        raise AssertionError("handoff validation must not open runtime database")

    monkeypatch.setattr("soc_ot.cli.main.get_runtime_engine", fail_database_access)
    assert main(["enterprise", "validate-handoff"]) == 0
    console = capsys.readouterr().out

    assert "artifacts=4" in console
    assert "live use authorized=false" in console
    assert "write-back implemented=false" in console


def test_ent_f_contracts_are_registered_generated_and_vendor_neutral() -> None:
    expected = {
        "enterprise-handoff-mapping-template.v1": EnterpriseHandoffMappingTemplate,
        "enterprise-environment-worksheet.v1": EnterpriseEnvironmentWorksheet,
        "enterprise-pilot-runbook.v1": EnterprisePilotRunbook,
        "enterprise-handoff-package.v1": EnterpriseHandoffPackage,
    }
    assert all(CONTRACT_MODELS[name] is model for name, model in expected.items())
    for name in expected:
        assert (ROOT / f"contracts/generated/{name}.schema.json").is_file()

    combined = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in HANDOFF_ROOT.glob("*.yaml")
    )
    assert "jira" not in combined
    assert "confluence" not in combined
    assert "customfield_" not in combined
