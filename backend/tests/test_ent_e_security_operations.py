import hashlib
import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from soc_ot.application.contracts import CONTRACT_MODELS
from soc_ot.application.enterprise_security_operations import (
    EnterpriseAccessDecision,
    EnterpriseAccessReason,
    EnterpriseAuditEventType,
    EnterpriseExposureMode,
    EnterpriseExposureSurface,
    EnterpriseHealthStatus,
    EnterpriseIncidentType,
    EnterpriseReadinessStatus,
    EnterpriseRecoveryAction,
    EnterpriseSecurityOperationPolicy,
    EnterpriseSecurityOperationReport,
    EnterpriseSecurityOperationScenarioCorpus,
    load_security_operation_policy,
    load_security_operation_scenarios,
    run_security_operation_emulator,
)
from soc_ot.cli.main import main

ROOT = Path(__file__).resolve().parents[2]
ENTERPRISE_FIXTURES = ROOT / "fixtures/enterprise"
POLICY_PATH = ENTERPRISE_FIXTURES / "security-operation-policy.v1.yaml"
SCENARIOS_PATH = ENTERPRISE_FIXTURES / "security-operation-scenarios.v1.yaml"


def _policy() -> EnterpriseSecurityOperationPolicy:
    return load_security_operation_policy(POLICY_PATH)


def _corpus() -> EnterpriseSecurityOperationScenarioCorpus:
    return load_security_operation_scenarios(SCENARIOS_PATH)


def _report() -> EnterpriseSecurityOperationReport:
    return run_security_operation_emulator(_policy(), _corpus())


def _probe_decisions(report: EnterpriseSecurityOperationReport, probe_id: str):
    return [
        item for item in report.exposure_decisions if item.probe_id == probe_id
    ]


def test_policy_and_corpus_cover_classifications_surfaces_and_incidents() -> None:
    policy = _policy()
    corpus = _corpus()

    assert policy.policy_version == "synthetic-security-operation.1"
    assert len(policy.classification_rules) == 4
    assert all(
        {item.surface for item in rule.surface_rules}
        == set(EnterpriseExposureSurface)
        for rule in policy.classification_rules
    )
    assert {item.incident_type for item in corpus.operation_scenarios} == set(
        EnterpriseIncidentType
    )
    assert len(corpus.exposure_probes) == 7


def test_acl_allow_and_surface_modes_match_frozen_matrix() -> None:
    report = _report()
    public = _probe_decisions(report, "EXPOSURE-PUBLIC")
    internal = _probe_decisions(report, "EXPOSURE-INTERNAL-ALLOW")

    assert len(report.exposure_decisions) == 35
    assert all(item.decision is EnterpriseAccessDecision.ALLOW for item in public)
    assert all(item.reason is EnterpriseAccessReason.ACL_ALLOW for item in internal)
    assert next(
        item for item in internal if item.surface is EnterpriseExposureSurface.LOG
    ).exposure_mode is EnterpriseExposureMode.METADATA_ONLY
    assert all(
        item.exposure_mode is EnterpriseExposureMode.FULL
        for item in internal
        if item.surface is not EnterpriseExposureSurface.LOG
    )


def test_unknown_missing_conflicting_and_denied_acl_fail_closed() -> None:
    report = _report()
    expected = {
        "EXPOSURE-ACL-DENY": EnterpriseAccessReason.ACL_DENY,
        "EXPOSURE-PRINCIPAL-UNKNOWN": EnterpriseAccessReason.PRINCIPAL_UNKNOWN,
        "EXPOSURE-ACL-MISSING": EnterpriseAccessReason.ACL_MISSING,
    }
    for probe_id, reason in expected.items():
        decisions = _probe_decisions(report, probe_id)
        assert all(item.decision is EnterpriseAccessDecision.DENY for item in decisions)
        assert all(item.exposure_mode is EnterpriseExposureMode.DENY for item in decisions)
        assert {item.reason for item in decisions} == {reason}

    conflict = _probe_decisions(report, "EXPOSURE-ACL-CONFLICT")
    assert {
        item.reason
        for item in conflict
        if item.surface
        in {
            EnterpriseExposureSurface.FRONTEND,
            EnterpriseExposureSurface.API,
            EnterpriseExposureSurface.LOG,
        }
    } == {EnterpriseAccessReason.ACL_CONFLICT}
    assert {
        item.reason
        for item in conflict
        if item.surface
        in {
            EnterpriseExposureSurface.MODEL,
            EnterpriseExposureSurface.ROLE_PACKET,
        }
    } == {EnterpriseAccessReason.CLASSIFICATION_DENY}


def test_restricted_source_is_denied_without_identity_or_payload_leakage() -> None:
    report = _report()
    restricted = _probe_decisions(report, "EXPOSURE-RESTRICTED")

    assert len(restricted) == 5
    assert all(item.decision is EnterpriseAccessDecision.DENY for item in restricted)
    assert {item.reason for item in restricted} == {
        EnterpriseAccessReason.SOURCE_RESTRICTED
    }
    rendered = report.model_dump_json()
    assert "PAGE-RESTRICTED-SECRET" not in rendered
    assert "knowledge.invalid/pages/PAGE-RESTRICTED-SECRET" not in rendered
    assert "source_identity" not in rendered


def test_credentials_are_redacted_from_diagnostic_and_audit_outputs() -> None:
    report = _report()
    rendered = report.model_dump_json()
    secret_values = (
        "synthetic-access-value",
        "synthetic-token-value",
        "synthetic-header-value",
        "synthetic-cookie-value",
        "synthetic-api-key-value",
        "synthetic-password-value",
        "synthetic-user",
        "synthetic-pass",
    )

    assert all(value not in rendered for value in secret_values)
    diagnostic = report.redacted_diagnostics[0]
    assert len(diagnostic.redacted_paths) == 6
    assert diagnostic.headers["X-Safe-Request"] == "synthetic-request-42"
    assert diagnostic.headers["Authorization"] == "[REDACTED]"
    assert diagnostic.payload["api_key"] == "[REDACTED]"
    assert "[REDACTED]" in diagnostic.message


def test_operation_health_recovery_and_unknown_freshness_are_fail_closed() -> None:
    report = _report()
    operations = {item.incident_type: item for item in report.operation_evaluations}

    healthy = operations[EnterpriseIncidentType.HEALTHY]
    assert healthy.health_status is EnterpriseHealthStatus.HEALTHY
    assert healthy.readiness_status is EnterpriseReadinessStatus.READY
    assert healthy.source_current is True
    assert healthy.recovery_action is EnterpriseRecoveryAction.NONE

    assert operations[EnterpriseIncidentType.LAG].recovery_action is (
        EnterpriseRecoveryAction.WAIT_BACKOFF
    )
    assert operations[EnterpriseIncidentType.STALE].recovery_action is (
        EnterpriseRecoveryAction.FULL_RECONCILIATION
    )
    assert operations[EnterpriseIncidentType.RATE_LIMITED].recovery_action is (
        EnterpriseRecoveryAction.WAIT_BACKOFF
    )
    assert operations[EnterpriseIncidentType.PARTIAL_SOURCE].recovery_action is (
        EnterpriseRecoveryAction.RETRY_MISSING_PARTITION
    )
    unknown = operations[EnterpriseIncidentType.UNKNOWN_FRESHNESS]
    assert unknown.readiness_status is EnterpriseReadinessStatus.NOT_READY
    assert unknown.source_current is False
    assert unknown.source_lag_seconds is None
    assert unknown.recovery_action is EnterpriseRecoveryAction.ESCALATE_SOURCE_OWNER
    assert sum(item.source_current for item in report.operation_evaluations) == 1


def test_metrics_are_unique_and_expose_security_and_recovery_signals() -> None:
    report = _report()
    metric_keys = [(item.metric_id, item.scenario_id) for item in report.metrics]
    globals_by_id = {
        item.metric_id: item.value
        for item in report.metrics
        if item.scenario_id is None
    }

    assert len(report.metrics) == 27
    assert len(metric_keys) == len(set(metric_keys))
    assert globals_by_id["enterprise_denied_exposure_total"] == 25
    assert globals_by_id["enterprise_redacted_field_total"] == 6
    assert globals_by_id["enterprise_partial_source_total"] == 1
    rate_limit = next(
        item
        for item in report.metrics
        if item.metric_id == "enterprise_rate_limit_retry_after_seconds"
    )
    assert rate_limit.scenario_id == "OP-RATE-LIMITED"
    assert rate_limit.value == 120


def test_audit_is_metadata_only_deterministic_and_covers_required_events() -> None:
    first = _report()
    second = _report()
    rendered = json.dumps(
        [item.model_dump(mode="json") for item in first.audit_events],
        ensure_ascii=False,
    )

    assert first == second
    assert len(first.audit_events) == 47
    assert len({item.event_id for item in first.audit_events}) == 47
    assert {item.event_type for item in first.audit_events} == set(
        EnterpriseAuditEventType
    )
    assert "payload" not in rendered
    assert "PAGE-RESTRICTED-SECRET" not in rendered
    assert "synthetic-password-value" not in rendered


def test_report_cannot_claim_real_authorization_or_credential_persistence() -> None:
    report = _report()

    assert report.real_authorization_performed is False
    assert report.credential_persisted is False
    payload = report.model_dump(mode="json")
    payload["real_authorization_performed"] = True
    with pytest.raises(ValidationError):
        EnterpriseSecurityOperationReport.model_validate(payload)
    payload = report.model_dump(mode="json")
    payload["credential_persisted"] = True
    with pytest.raises(ValidationError):
        EnterpriseSecurityOperationReport.model_validate(payload)


def test_scenario_expectation_drift_and_incomplete_policy_are_rejected() -> None:
    corpus_payload = yaml.safe_load(SCENARIOS_PATH.read_text(encoding="utf-8"))
    corpus_payload["exposure_probes"][0]["expected_decisions"][0]["reason"] = "ACL_DENY"
    drifted = EnterpriseSecurityOperationScenarioCorpus.model_validate(corpus_payload)
    with pytest.raises(ValueError, match="expectation mismatch"):
        run_security_operation_emulator(_policy(), drifted)

    policy_payload = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    policy_payload["classification_rules"].pop()
    with pytest.raises(ValidationError, match="cover every classification"):
        EnterpriseSecurityOperationPolicy.model_validate(policy_payload)


def test_security_emulator_cli_never_opens_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_database_access() -> None:
        raise AssertionError("security emulator must not open runtime database")

    monkeypatch.setattr("soc_ot.cli.main.get_runtime_engine", fail_database_access)
    output = tmp_path / "security-operation.json"
    assert (
        main(["enterprise", "emulate-security", "--output", str(output)])
        == 0
    )

    rendered = json.loads(output.read_text(encoding="utf-8"))
    assert rendered["real_authorization_performed"] is False
    assert rendered["credential_persisted"] is False
    console = capsys.readouterr().out
    assert "real authorization=false" in console
    assert "credential persisted=false" in console


def test_ent_e_fixtures_are_synthetic_hash_pinned_and_contracts_generated() -> None:
    combined = (
        POLICY_PATH.read_text(encoding="utf-8")
        + SCENARIOS_PATH.read_text(encoding="utf-8")
    ).lower()
    assert "jira" not in combined
    assert "confluence" not in combined
    assert "customfield_" not in combined

    manifest = yaml.safe_load(
        (ENTERPRISE_FIXTURES / "manifest.yaml").read_text(encoding="utf-8")
    )
    artifacts = {item["path"]: item["sha256"] for item in manifest["artifacts"]}
    for path in (POLICY_PATH, SCENARIOS_PATH):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifacts[path.name]

    assert (
        CONTRACT_MODELS["enterprise-security-operation-policy.v1"]
        is EnterpriseSecurityOperationPolicy
    )
    assert (
        CONTRACT_MODELS["enterprise-security-operation-scenario-corpus.v1"]
        is EnterpriseSecurityOperationScenarioCorpus
    )
    assert (
        CONTRACT_MODELS["enterprise-security-operation-report.v1"]
        is EnterpriseSecurityOperationReport
    )
    for name in (
        "enterprise-security-operation-policy.v1",
        "enterprise-security-operation-scenario-corpus.v1",
        "enterprise-security-operation-report.v1",
    ):
        assert (ROOT / f"contracts/generated/{name}.schema.json").exists()
