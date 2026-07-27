import hashlib
import json
import re
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, JsonValue, field_validator, model_validator

from soc_ot.application.enterprise_ingestion import (
    EnterpriseSourceIdentity,
    EnterpriseSourceRecord,
    RequiredText,
    Sha256Hex,
    SourceDataClassification,
    SourceDeletionState,
)
from soc_ot.domain.models import StrictModel


class EnterpriseExposureSurface(StrEnum):
    FRONTEND = "FRONTEND"
    API = "API"
    MODEL = "MODEL"
    ROLE_PACKET = "ROLE_PACKET"
    LOG = "LOG"


class EnterpriseExposureMode(StrEnum):
    FULL = "FULL"
    METADATA_ONLY = "METADATA_ONLY"
    DENY = "DENY"


class EnterpriseAccessDecision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class EnterpriseAccessReason(StrEnum):
    ACL_ALLOW = "ACL_ALLOW"
    ACL_DENY = "ACL_DENY"
    ACL_NO_MATCH = "ACL_NO_MATCH"
    ACL_MISSING = "ACL_MISSING"
    ACL_CONFLICT = "ACL_CONFLICT"
    PRINCIPAL_UNKNOWN = "PRINCIPAL_UNKNOWN"
    CLASSIFICATION_DENY = "CLASSIFICATION_DENY"
    SOURCE_INACTIVE = "SOURCE_INACTIVE"
    SOURCE_RESTRICTED = "SOURCE_RESTRICTED"


class EnterpriseIncidentType(StrEnum):
    HEALTHY = "HEALTHY"
    LAG = "LAG"
    STALE = "STALE"
    RATE_LIMITED = "RATE_LIMITED"
    PARTIAL_SOURCE = "PARTIAL_SOURCE"
    UNKNOWN_FRESHNESS = "UNKNOWN_FRESHNESS"


class EnterpriseHealthStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    NOT_READY = "NOT_READY"


class EnterpriseReadinessStatus(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"


class EnterpriseRecoveryAction(StrEnum):
    NONE = "NONE"
    WAIT_BACKOFF = "WAIT_BACKOFF"
    FULL_RECONCILIATION = "FULL_RECONCILIATION"
    RETRY_MISSING_PARTITION = "RETRY_MISSING_PARTITION"
    ESCALATE_SOURCE_OWNER = "ESCALATE_SOURCE_OWNER"


class EnterpriseAuditEventType(StrEnum):
    ACCESS_EVALUATED = "ACCESS_EVALUATED"
    REDACTION_APPLIED = "REDACTION_APPLIED"
    RECOVERY_PLANNED = "RECOVERY_PLANNED"
    HEALTH_EVALUATED = "HEALTH_EVALUATED"


class SyntheticPrincipal(StrictModel):
    principal_id: RequiredText
    group_ids: list[RequiredText] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_unique_groups(self) -> "SyntheticPrincipal":
        if len(self.group_ids) != len(set(self.group_ids)):
            raise ValueError("synthetic principal group must be unique")
        return self


class SyntheticAclRule(StrictModel):
    acl_ref: RequiredText
    allow_principal_ids: list[RequiredText] = Field(default_factory=list)
    deny_principal_ids: list[RequiredText] = Field(default_factory=list)
    allow_group_ids: list[RequiredText] = Field(default_factory=list)
    deny_group_ids: list[RequiredText] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_unique_acl_members(self) -> "SyntheticAclRule":
        for values in (
            self.allow_principal_ids,
            self.deny_principal_ids,
            self.allow_group_ids,
            self.deny_group_ids,
        ):
            if len(values) != len(set(values)):
                raise ValueError("synthetic ACL member must be unique within a list")
        return self


class ClassificationSurfaceRule(StrictModel):
    surface: EnterpriseExposureSurface
    exposure_mode: EnterpriseExposureMode


class ClassificationExposureRule(StrictModel):
    classification: SourceDataClassification
    surface_rules: list[ClassificationSurfaceRule] = Field(min_length=1)

    @model_validator(mode="after")
    def cover_every_surface(self) -> "ClassificationExposureRule":
        surfaces = [item.surface for item in self.surface_rules]
        if len(surfaces) != len(set(surfaces)):
            raise ValueError("classification surface must be unique")
        if set(surfaces) != set(EnterpriseExposureSurface):
            raise ValueError("classification rule must cover every exposure surface")
        return self


class EnterpriseSecurityOperationPolicy(StrictModel):
    schema_version: Literal["enterprise-security-operation-policy.v1"]
    policy_version: RequiredText
    principals: list[SyntheticPrincipal] = Field(min_length=1)
    acl_rules: list[SyntheticAclRule] = Field(min_length=1)
    classification_rules: list[ClassificationExposureRule] = Field(min_length=1)
    sensitive_field_names: list[RequiredText] = Field(min_length=1)
    max_source_lag_seconds: int = Field(ge=0)
    stale_source_after_seconds: int = Field(ge=0)

    @model_validator(mode="after")
    def require_unique_and_complete_policy(self) -> "EnterpriseSecurityOperationPolicy":
        principal_ids = [item.principal_id for item in self.principals]
        acl_refs = [item.acl_ref for item in self.acl_rules]
        classifications = [item.classification for item in self.classification_rules]
        if len(principal_ids) != len(set(principal_ids)):
            raise ValueError("synthetic principal_id must be unique")
        if len(acl_refs) != len(set(acl_refs)):
            raise ValueError("synthetic ACL ref must be unique")
        if len(classifications) != len(set(classifications)):
            raise ValueError("classification policy must be unique")
        if set(classifications) != set(SourceDataClassification):
            raise ValueError("security policy must cover every classification")
        normalized_fields = [item.casefold() for item in self.sensitive_field_names]
        if len(normalized_fields) != len(set(normalized_fields)):
            raise ValueError("sensitive field name must be unique")
        if self.stale_source_after_seconds < self.max_source_lag_seconds:
            raise ValueError("stale threshold cannot be lower than lag threshold")
        return self


class ExpectedExposureDecision(StrictModel):
    surface: EnterpriseExposureSurface
    decision: EnterpriseAccessDecision
    exposure_mode: EnterpriseExposureMode
    reason: EnterpriseAccessReason


class EnterpriseExposureProbe(StrictModel):
    probe_id: RequiredText
    principal_id: RequiredText
    record: EnterpriseSourceRecord
    expected_decisions: list[ExpectedExposureDecision] = Field(min_length=1)

    @model_validator(mode="after")
    def require_expected_surface_coverage(self) -> "EnterpriseExposureProbe":
        surfaces = [item.surface for item in self.expected_decisions]
        if len(surfaces) != len(set(surfaces)):
            raise ValueError("expected exposure surface must be unique")
        if set(surfaces) != set(EnterpriseExposureSurface):
            raise ValueError("exposure probe must cover every surface")
        return self


class UntrustedDiagnostic(StrictModel):
    diagnostic_id: RequiredText
    message: RequiredText
    headers: dict[str, JsonValue] = Field(default_factory=dict)
    payload: dict[str, JsonValue] = Field(default_factory=dict)


class EnterpriseOperationScenario(StrictModel):
    scenario_id: RequiredText
    incident_type: EnterpriseIncidentType
    evaluated_at: datetime
    last_success_at: datetime | None
    freshness_known: bool
    expected_source_count: int = Field(ge=1)
    received_source_count: int = Field(ge=0)
    retry_after_seconds: int | None = Field(default=None, ge=1)

    @field_validator("evaluated_at", "last_success_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("operation scenario time must include a timezone")
        return value

    @model_validator(mode="after")
    def align_incident_fields(self) -> "EnterpriseOperationScenario":
        if self.received_source_count > self.expected_source_count:
            raise ValueError("received source count cannot exceed expected count")
        if self.freshness_known != (self.last_success_at is not None):
            raise ValueError("freshness flag must align with last_success_at")
        if self.incident_type is EnterpriseIncidentType.RATE_LIMITED:
            if self.retry_after_seconds is None:
                raise ValueError("rate-limited scenario requires retry_after_seconds")
        elif self.retry_after_seconds is not None:
            raise ValueError("only rate-limited scenario can declare retry_after_seconds")
        if (
            self.incident_type is EnterpriseIncidentType.PARTIAL_SOURCE
            and self.received_source_count >= self.expected_source_count
        ):
            raise ValueError("partial-source scenario requires a missing source")
        if (
            self.incident_type is EnterpriseIncidentType.UNKNOWN_FRESHNESS
            and self.freshness_known
        ):
            raise ValueError("unknown-freshness scenario cannot know freshness")
        return self


class EnterpriseSecurityOperationScenarioCorpus(StrictModel):
    schema_version: Literal["enterprise-security-operation-scenario-corpus.v1"]
    corpus_version: RequiredText
    exposure_probes: list[EnterpriseExposureProbe] = Field(min_length=1)
    diagnostics: list[UntrustedDiagnostic] = Field(min_length=1)
    operation_scenarios: list[EnterpriseOperationScenario] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_and_complete_scenarios(
        self,
    ) -> "EnterpriseSecurityOperationScenarioCorpus":
        identifiers = (
            [item.probe_id for item in self.exposure_probes]
            + [item.diagnostic_id for item in self.diagnostics]
            + [item.scenario_id for item in self.operation_scenarios]
        )
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("security/operation scenario identifier must be unique")
        incident_types = [item.incident_type for item in self.operation_scenarios]
        if set(incident_types) != set(EnterpriseIncidentType):
            raise ValueError("scenario corpus must cover every incident type")
        return self


class EnterpriseExposureDecisionRecord(StrictModel):
    decision_id: Sha256Hex
    probe_id: RequiredText
    source_ref_hash: Sha256Hex
    principal_id: RequiredText
    classification: SourceDataClassification
    surface: EnterpriseExposureSurface
    decision: EnterpriseAccessDecision
    exposure_mode: EnterpriseExposureMode
    reason: EnterpriseAccessReason


class RedactedDiagnostic(StrictModel):
    diagnostic_id: RequiredText
    message: RequiredText
    headers: dict[str, JsonValue]
    payload: dict[str, JsonValue]
    redacted_paths: list[RequiredText]


class EnterpriseOperationEvaluation(StrictModel):
    scenario_id: RequiredText
    incident_type: EnterpriseIncidentType
    health_status: EnterpriseHealthStatus
    readiness_status: EnterpriseReadinessStatus
    source_current: bool
    source_lag_seconds: int | None = Field(default=None, ge=0)
    completion_ratio: float = Field(ge=0, le=1)
    recovery_action: EnterpriseRecoveryAction

    @model_validator(mode="after")
    def protect_unknown_or_unready_source(self) -> "EnterpriseOperationEvaluation":
        if self.source_current and self.readiness_status is not EnterpriseReadinessStatus.READY:
            raise ValueError("current source must be ready")
        if self.readiness_status is EnterpriseReadinessStatus.NOT_READY and self.source_current:
            raise ValueError("not-ready source cannot be current")
        return self


class EnterpriseOperationMetric(StrictModel):
    metric_id: RequiredText
    scenario_id: str | None = None
    value: float = Field(ge=0)
    unit: RequiredText


class EnterpriseOperationAuditEvent(StrictModel):
    event_id: Sha256Hex
    event_type: EnterpriseAuditEventType
    occurred_at: datetime
    subject_ref_hash: Sha256Hex
    outcome: RequiredText

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("operation audit time must include a timezone")
        return value


class EnterpriseSecurityOperationReport(StrictModel):
    schema_version: Literal["enterprise-security-operation-report.v1"]
    report_id: Sha256Hex
    policy_version: RequiredText
    corpus_version: RequiredText
    real_authorization_performed: Literal[False]
    credential_persisted: Literal[False]
    exposure_decisions: list[EnterpriseExposureDecisionRecord]
    redacted_diagnostics: list[RedactedDiagnostic]
    operation_evaluations: list[EnterpriseOperationEvaluation]
    metrics: list[EnterpriseOperationMetric]
    audit_events: list[EnterpriseOperationAuditEvent]

    @model_validator(mode="after")
    def require_unique_report_records(self) -> "EnterpriseSecurityOperationReport":
        decision_ids = [item.decision_id for item in self.exposure_decisions]
        metric_keys = [(item.metric_id, item.scenario_id) for item in self.metrics]
        event_ids = [item.event_id for item in self.audit_events]
        if len(decision_ids) != len(set(decision_ids)):
            raise ValueError("security report decision_id must be unique")
        if len(metric_keys) != len(set(metric_keys)):
            raise ValueError("security report metric key must be unique")
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("security report event_id must be unique")
        return self


def load_security_operation_policy(path: Path) -> EnterpriseSecurityOperationPolicy:
    return EnterpriseSecurityOperationPolicy.model_validate(
        yaml.safe_load(path.read_text(encoding="utf-8"))
    )


def load_security_operation_scenarios(
    path: Path,
) -> EnterpriseSecurityOperationScenarioCorpus:
    return EnterpriseSecurityOperationScenarioCorpus.model_validate(
        yaml.safe_load(path.read_text(encoding="utf-8"))
    )


def run_security_operation_emulator(
    policy: EnterpriseSecurityOperationPolicy,
    corpus: EnterpriseSecurityOperationScenarioCorpus,
) -> EnterpriseSecurityOperationReport:
    decisions = [
        _evaluate_exposure(policy, probe, surface)
        for probe in corpus.exposure_probes
        for surface in EnterpriseExposureSurface
    ]
    _validate_expected_exposure(corpus.exposure_probes, decisions)
    redacted = [
        _redact_diagnostic(policy, diagnostic) for diagnostic in corpus.diagnostics
    ]
    operations = [
        _evaluate_operation(policy, scenario)
        for scenario in corpus.operation_scenarios
    ]
    metrics = _metrics(decisions, redacted, operations, corpus.operation_scenarios)
    audit_events = _audit_events(corpus, decisions, redacted, operations)
    material = {
        "policy_version": policy.policy_version,
        "corpus_version": corpus.corpus_version,
        "decisions": [item.model_dump(mode="json") for item in decisions],
        "redacted": [item.model_dump(mode="json") for item in redacted],
        "operations": [item.model_dump(mode="json") for item in operations],
        "metrics": [item.model_dump(mode="json") for item in metrics],
        "audit": [item.model_dump(mode="json") for item in audit_events],
    }
    return EnterpriseSecurityOperationReport(
        schema_version="enterprise-security-operation-report.v1",
        report_id=_hash(material),
        policy_version=policy.policy_version,
        corpus_version=corpus.corpus_version,
        real_authorization_performed=False,
        credential_persisted=False,
        exposure_decisions=decisions,
        redacted_diagnostics=redacted,
        operation_evaluations=operations,
        metrics=metrics,
        audit_events=audit_events,
    )


def _evaluate_exposure(
    policy: EnterpriseSecurityOperationPolicy,
    probe: EnterpriseExposureProbe,
    surface: EnterpriseExposureSurface,
) -> EnterpriseExposureDecisionRecord:
    record = probe.record
    principal = next(
        (item for item in policy.principals if item.principal_id == probe.principal_id),
        None,
    )
    acl = next(
        (item for item in policy.acl_rules if item.acl_ref == record.source_acl_ref),
        None,
    )
    classification_rule = next(
        item
        for item in policy.classification_rules
        if item.classification is record.classification
    )
    requested_mode = next(
        item.exposure_mode
        for item in classification_rule.surface_rules
        if item.surface is surface
    )

    if record.deletion_state is SourceDeletionState.RESTRICTED:
        decision, mode, reason = _deny(EnterpriseAccessReason.SOURCE_RESTRICTED)
    elif record.deletion_state is not SourceDeletionState.ACTIVE:
        decision, mode, reason = _deny(EnterpriseAccessReason.SOURCE_INACTIVE)
    elif requested_mode is EnterpriseExposureMode.DENY:
        decision, mode, reason = _deny(EnterpriseAccessReason.CLASSIFICATION_DENY)
    elif principal is None:
        decision, mode, reason = _deny(EnterpriseAccessReason.PRINCIPAL_UNKNOWN)
    elif acl is None:
        decision, mode, reason = _deny(EnterpriseAccessReason.ACL_MISSING)
    else:
        groups = set(principal.group_ids)
        allowed = (
            principal.principal_id in acl.allow_principal_ids
            or bool(groups & set(acl.allow_group_ids))
        )
        denied = (
            principal.principal_id in acl.deny_principal_ids
            or bool(groups & set(acl.deny_group_ids))
        )
        if allowed and denied:
            decision, mode, reason = _deny(EnterpriseAccessReason.ACL_CONFLICT)
        elif denied:
            decision, mode, reason = _deny(EnterpriseAccessReason.ACL_DENY)
        elif not allowed:
            decision, mode, reason = _deny(EnterpriseAccessReason.ACL_NO_MATCH)
        else:
            decision = EnterpriseAccessDecision.ALLOW
            mode = requested_mode
            reason = EnterpriseAccessReason.ACL_ALLOW

    identity_hash = _identity_hash(record.identity)
    material = {
        "probe_id": probe.probe_id,
        "source_ref_hash": identity_hash,
        "principal_id": probe.principal_id,
        "classification": record.classification,
        "surface": surface,
        "decision": decision,
        "mode": mode,
        "reason": reason,
    }
    return EnterpriseExposureDecisionRecord(
        decision_id=_hash(material),
        probe_id=probe.probe_id,
        source_ref_hash=identity_hash,
        principal_id=probe.principal_id,
        classification=record.classification,
        surface=surface,
        decision=decision,
        exposure_mode=mode,
        reason=reason,
    )


def _deny(
    reason: EnterpriseAccessReason,
) -> tuple[
    EnterpriseAccessDecision,
    EnterpriseExposureMode,
    EnterpriseAccessReason,
]:
    return EnterpriseAccessDecision.DENY, EnterpriseExposureMode.DENY, reason


def _validate_expected_exposure(
    probes: list[EnterpriseExposureProbe],
    decisions: list[EnterpriseExposureDecisionRecord],
) -> None:
    actual = {
        (item.probe_id, item.surface): (
            item.decision,
            item.exposure_mode,
            item.reason,
        )
        for item in decisions
    }
    for probe in probes:
        for expected in probe.expected_decisions:
            if actual[(probe.probe_id, expected.surface)] != (
                expected.decision,
                expected.exposure_mode,
                expected.reason,
            ):
                raise ValueError(
                    f"exposure expectation mismatch: {probe.probe_id}/{expected.surface}"
                )


def _redact_diagnostic(
    policy: EnterpriseSecurityOperationPolicy,
    diagnostic: UntrustedDiagnostic,
) -> RedactedDiagnostic:
    sensitive = {item.casefold() for item in policy.sensitive_field_names}
    redacted_paths: list[str] = []
    message = _redact_string(diagnostic.message)
    if message != diagnostic.message:
        redacted_paths.append("/message")
    headers = _redact_mapping(diagnostic.headers, "/headers", sensitive, redacted_paths)
    payload = _redact_mapping(diagnostic.payload, "/payload", sensitive, redacted_paths)
    return RedactedDiagnostic(
        diagnostic_id=diagnostic.diagnostic_id,
        message=message,
        headers=headers,
        payload=payload,
        redacted_paths=sorted(redacted_paths),
    )


def _redact_mapping(
    values: dict[str, JsonValue],
    path: str,
    sensitive: set[str],
    redacted_paths: list[str],
) -> dict[str, JsonValue]:
    output: dict[str, JsonValue] = {}
    for key, value in values.items():
        item_path = f"{path}/{key}"
        if key.casefold() in sensitive:
            output[key] = "[REDACTED]"
            redacted_paths.append(item_path)
        else:
            output[key] = _redact_value(value, item_path, sensitive, redacted_paths)
    return output


def _redact_value(
    value: JsonValue,
    path: str,
    sensitive: set[str],
    redacted_paths: list[str],
) -> JsonValue:
    if isinstance(value, dict):
        return _redact_mapping(value, path, sensitive, redacted_paths)
    if isinstance(value, list):
        return [
            _redact_value(item, f"{path}/{index}", sensitive, redacted_paths)
            for index, item in enumerate(value)
        ]
    if isinstance(value, str):
        redacted = _redact_string(value)
        if redacted != value:
            redacted_paths.append(path)
        return redacted
    return value


def _redact_string(value: str) -> str:
    patterns = (
        (r"(?i)(bearer\s+)[^\s,;]+", r"\1[REDACTED]"),
        (
            r"(?i)\b(token|password|secret|api[_-]?key)=([^\s,;&]+)",
            r"\1=[REDACTED]",
        ),
        (r"(?i)(https?://)[^/@\s:]+:[^/@\s]+@", r"\1[REDACTED]@"),
    )
    redacted = value
    for pattern, replacement in patterns:
        redacted = re.sub(pattern, replacement, redacted)
    return redacted


def _evaluate_operation(
    policy: EnterpriseSecurityOperationPolicy,
    scenario: EnterpriseOperationScenario,
) -> EnterpriseOperationEvaluation:
    lag = (
        max(0, int((scenario.evaluated_at - scenario.last_success_at).total_seconds()))
        if scenario.last_success_at is not None
        else None
    )
    completion = (
        scenario.received_source_count / scenario.expected_source_count
        if scenario.expected_source_count
        else 1.0
    )
    incident = scenario.incident_type
    if (
        incident is EnterpriseIncidentType.HEALTHY
        and lag is not None
        and lag <= policy.max_source_lag_seconds
        and completion == 1
    ):
        health = EnterpriseHealthStatus.HEALTHY
        readiness = EnterpriseReadinessStatus.READY
        current = True
        recovery = EnterpriseRecoveryAction.NONE
    else:
        current = False
        readiness = EnterpriseReadinessStatus.NOT_READY
        if incident in {
            EnterpriseIncidentType.LAG,
            EnterpriseIncidentType.RATE_LIMITED,
        } and (lag is None or lag <= policy.stale_source_after_seconds):
            health = EnterpriseHealthStatus.DEGRADED
            recovery = EnterpriseRecoveryAction.WAIT_BACKOFF
        elif incident is EnterpriseIncidentType.PARTIAL_SOURCE:
            health = EnterpriseHealthStatus.NOT_READY
            recovery = EnterpriseRecoveryAction.RETRY_MISSING_PARTITION
        elif incident is EnterpriseIncidentType.UNKNOWN_FRESHNESS:
            health = EnterpriseHealthStatus.NOT_READY
            recovery = EnterpriseRecoveryAction.ESCALATE_SOURCE_OWNER
        else:
            health = EnterpriseHealthStatus.NOT_READY
            recovery = EnterpriseRecoveryAction.FULL_RECONCILIATION
    return EnterpriseOperationEvaluation(
        scenario_id=scenario.scenario_id,
        incident_type=incident,
        health_status=health,
        readiness_status=readiness,
        source_current=current,
        source_lag_seconds=lag,
        completion_ratio=completion,
        recovery_action=recovery,
    )


def _metrics(
    decisions: list[EnterpriseExposureDecisionRecord],
    diagnostics: list[RedactedDiagnostic],
    operations: list[EnterpriseOperationEvaluation],
    scenarios: list[EnterpriseOperationScenario],
) -> list[EnterpriseOperationMetric]:
    metrics = [
        EnterpriseOperationMetric(
            metric_id="enterprise_denied_exposure_total",
            value=float(
                sum(item.decision is EnterpriseAccessDecision.DENY for item in decisions)
            ),
            unit="count",
        ),
        EnterpriseOperationMetric(
            metric_id="enterprise_redacted_field_total",
            value=float(sum(len(item.redacted_paths) for item in diagnostics)),
            unit="count",
        ),
        EnterpriseOperationMetric(
            metric_id="enterprise_partial_source_total",
            value=float(
                sum(
                    item.incident_type is EnterpriseIncidentType.PARTIAL_SOURCE
                    for item in operations
                )
            ),
            unit="count",
        ),
    ]
    for operation in operations:
        metrics.extend(
            [
                EnterpriseOperationMetric(
                    metric_id="enterprise_source_freshness_known",
                    scenario_id=operation.scenario_id,
                    value=float(operation.source_lag_seconds is not None),
                    unit="boolean",
                ),
                EnterpriseOperationMetric(
                    metric_id="enterprise_source_completion_ratio",
                    scenario_id=operation.scenario_id,
                    value=operation.completion_ratio,
                    unit="ratio",
                ),
                EnterpriseOperationMetric(
                    metric_id="enterprise_source_current",
                    scenario_id=operation.scenario_id,
                    value=float(operation.source_current),
                    unit="boolean",
                ),
            ]
        )
        if operation.source_lag_seconds is not None:
            metrics.append(
                EnterpriseOperationMetric(
                    metric_id="enterprise_source_lag_seconds",
                    scenario_id=operation.scenario_id,
                    value=float(operation.source_lag_seconds),
                    unit="seconds",
                )
            )
    for scenario in scenarios:
        if scenario.retry_after_seconds is not None:
            metrics.append(
                EnterpriseOperationMetric(
                    metric_id="enterprise_rate_limit_retry_after_seconds",
                    scenario_id=scenario.scenario_id,
                    value=float(scenario.retry_after_seconds),
                    unit="seconds",
                )
            )
    return metrics


def _audit_events(
    corpus: EnterpriseSecurityOperationScenarioCorpus,
    decisions: list[EnterpriseExposureDecisionRecord],
    diagnostics: list[RedactedDiagnostic],
    operations: list[EnterpriseOperationEvaluation],
) -> list[EnterpriseOperationAuditEvent]:
    occurred_at = min(item.evaluated_at for item in corpus.operation_scenarios)
    events: list[EnterpriseOperationAuditEvent] = []
    for decision in decisions:
        events.append(
            _audit_event(
                EnterpriseAuditEventType.ACCESS_EVALUATED,
                occurred_at,
                decision.source_ref_hash,
                f"{decision.surface}:{decision.decision}:{decision.reason}",
            )
        )
    for diagnostic in diagnostics:
        events.append(
            _audit_event(
                EnterpriseAuditEventType.REDACTION_APPLIED,
                occurred_at,
                _hash(diagnostic.diagnostic_id),
                f"redacted_paths={len(diagnostic.redacted_paths)}",
            )
        )
    for operation in operations:
        subject = _hash(operation.scenario_id)
        events.append(
            _audit_event(
                EnterpriseAuditEventType.HEALTH_EVALUATED,
                occurred_at,
                subject,
                f"{operation.health_status}:{operation.readiness_status}",
            )
        )
        if operation.recovery_action is not EnterpriseRecoveryAction.NONE:
            events.append(
                _audit_event(
                    EnterpriseAuditEventType.RECOVERY_PLANNED,
                    occurred_at,
                    subject,
                    str(operation.recovery_action),
                )
            )
    return events


def _audit_event(
    event_type: EnterpriseAuditEventType,
    occurred_at: datetime,
    subject_ref_hash: str,
    outcome: str,
) -> EnterpriseOperationAuditEvent:
    material = {
        "event_type": event_type,
        "occurred_at": occurred_at.isoformat(),
        "subject_ref_hash": subject_ref_hash,
        "outcome": outcome,
    }
    return EnterpriseOperationAuditEvent(
        event_id=_hash(material),
        event_type=event_type,
        occurred_at=occurred_at,
        subject_ref_hash=subject_ref_hash,
        outcome=outcome,
    )


def _identity_hash(identity: EnterpriseSourceIdentity) -> str:
    return _hash(identity.model_dump(mode="json"))


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
