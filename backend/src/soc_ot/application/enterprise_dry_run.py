import hashlib
import json
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
    SourceDeletionState,
)
from soc_ot.application.enterprise_mapping import (
    EnterpriseDirtyFixtureCorpus,
    EnterpriseMappingProfile,
    EnterpriseMappingRegistry,
    MappingDisposition,
    MappingReasonCode,
    StructuredCandidateKind,
    map_source_records,
)
from soc_ot.application.enterprise_sync import (
    EnterpriseSourceReconciliationState,
    EnterpriseSyncDisposition,
    EnterpriseSyncResult,
    EnterpriseSyncStatus,
)
from soc_ot.domain.models import StrictModel


class CanonicalChangeAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    NO_CHANGE = "NO_CHANGE"


class EnterpriseQualityCode(StrEnum):
    DANGLING_REFERENCE = "DANGLING_REFERENCE"
    TIME_AMBIGUITY = "TIME_AMBIGUITY"
    UNMAPPED_FIELD = "UNMAPPED_FIELD"
    ACL_REFERENCE_UNKNOWN = "ACL_REFERENCE_UNKNOWN"
    STALE_SOURCE = "STALE_SOURCE"
    MAPPING_QUARANTINED = "MAPPING_QUARANTINED"
    MAPPING_REJECTED = "MAPPING_REJECTED"


class EnterpriseQualitySeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class EnterpriseDryRunStatus(StrEnum):
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    BLOCKED = "BLOCKED"


class EnterpriseQuarantineStatus(StrEnum):
    OPEN = "OPEN"
    RESOLUTION_PROPOSED = "RESOLUTION_PROPOSED"


class EnterpriseResolutionAction(StrEnum):
    EXCLUDE_SOURCE = "EXCLUDE_SOURCE"
    SOURCE_FIXED = "SOURCE_FIXED"
    MAPPING_UPDATED = "MAPPING_UPDATED"
    ACKNOWLEDGE_RISK = "ACKNOWLEDGE_RISK"


class CanonicalKeyRule(StrictModel):
    candidate_kind: StructuredCandidateKind
    target_field: RequiredText


class CanonicalObjectSnapshot(StrictModel):
    candidate_kind: StructuredCandidateKind
    canonical_key: RequiredText
    source_identity: EnterpriseSourceIdentity
    values: dict[str, JsonValue] = Field(min_length=1)


class EnterpriseQualityProbe(StrictModel):
    probe_id: RequiredText
    record: EnterpriseSourceRecord
    reference_keys: list[RequiredText] = Field(default_factory=list)


class EnterpriseDryRunInput(StrictModel):
    schema_version: Literal["enterprise-dry-run-input.v1"]
    input_version: RequiredText
    as_of: datetime
    stale_after_seconds: int = Field(ge=0)
    known_acl_refs: list[RequiredText] = Field(min_length=1)
    canonical_snapshot_version: RequiredText
    canonical_key_rules: list[CanonicalKeyRule] = Field(min_length=1)
    canonical_objects: list[CanonicalObjectSnapshot] = Field(default_factory=list)
    quality_probes: list[EnterpriseQualityProbe] = Field(default_factory=list)

    @field_validator("as_of")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("dry-run as_of must include a timezone")
        return value

    @model_validator(mode="after")
    def require_unique_configuration(self) -> "EnterpriseDryRunInput":
        kinds = [item.candidate_kind for item in self.canonical_key_rules]
        if len(kinds) != len(set(kinds)):
            raise ValueError("canonical key rule kind must be unique")
        object_keys = [
            (item.candidate_kind, item.canonical_key) for item in self.canonical_objects
        ]
        if len(object_keys) != len(set(object_keys)):
            raise ValueError("canonical snapshot object key must be unique")
        identities = [
            _identity_key(item.source_identity) for item in self.canonical_objects
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("canonical snapshot source identity must be unique")
        probe_ids = [item.probe_id for item in self.quality_probes]
        if len(probe_ids) != len(set(probe_ids)):
            raise ValueError("quality probe_id must be unique")
        if len(self.known_acl_refs) != len(set(self.known_acl_refs)):
            raise ValueError("known ACL reference must be unique")
        return self


class EnterpriseResolutionEntry(StrictModel):
    quarantine_id: Sha256Hex
    expected_content_hash: Sha256Hex | None = None
    action: EnterpriseResolutionAction
    reviewer: RequiredText
    justification: RequiredText
    proposed_at: datetime

    @field_validator("proposed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("resolution time must include a timezone")
        return value


class EnterpriseResolutionFile(StrictModel):
    schema_version: Literal["enterprise-resolution-file.v1"]
    resolution_version: RequiredText
    entries: list[EnterpriseResolutionEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_unique_targets(self) -> "EnterpriseResolutionFile":
        targets = [item.quarantine_id for item in self.entries]
        if len(targets) != len(set(targets)):
            raise ValueError("resolution quarantine_id must be unique")
        return self


class EnterpriseCanonicalChange(StrictModel):
    change_id: Sha256Hex
    action: CanonicalChangeAction
    candidate_kind: StructuredCandidateKind
    canonical_key: RequiredText
    source_identity: EnterpriseSourceIdentity
    before_values: dict[str, JsonValue] | None = None
    after_values: dict[str, JsonValue] | None = None
    reason_codes: list[MappingReasonCode] = Field(default_factory=list)

    @model_validator(mode="after")
    def align_action_values(self) -> "EnterpriseCanonicalChange":
        if self.action is CanonicalChangeAction.CREATE:
            if self.before_values is not None or self.after_values is None:
                raise ValueError("CREATE requires only after_values")
        elif self.action is CanonicalChangeAction.UPDATE:
            if self.before_values is None or self.after_values is None:
                raise ValueError("UPDATE requires before_values and after_values")
        elif self.action is CanonicalChangeAction.DELETE:
            if self.before_values is None or self.after_values is not None:
                raise ValueError("DELETE requires only before_values")
        elif self.before_values is None or self.after_values is None:
            raise ValueError("NO_CHANGE requires before_values and after_values")
        return self


class EnterpriseQualityFinding(StrictModel):
    finding_id: Sha256Hex
    code: EnterpriseQualityCode
    severity: EnterpriseQualitySeverity
    blocks_import: bool
    detail: RequiredText
    source_identity: EnterpriseSourceIdentity | None = None
    content_hash: Sha256Hex | None = None
    field_name: str | None = None
    reference_key: str | None = None
    mapping_reason_codes: list[MappingReasonCode] = Field(default_factory=list)


class EnterpriseQuarantineEntry(StrictModel):
    quarantine_id: Sha256Hex
    finding_ids: list[Sha256Hex] = Field(min_length=1)
    source_identity: EnterpriseSourceIdentity | None = None
    content_hash: Sha256Hex | None = None
    status: EnterpriseQuarantineStatus
    proposed_resolution: EnterpriseResolutionEntry | None = None


class EnterpriseDryRunSummary(StrictModel):
    source_record_count: int = Field(ge=0)
    mapped_record_count: int = Field(ge=0)
    mapping_coverage: float = Field(ge=0, le=1)
    create_count: int = Field(ge=0)
    update_count: int = Field(ge=0)
    delete_count: int = Field(ge=0)
    no_change_count: int = Field(ge=0)
    quality_finding_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    quarantined_count: int = Field(ge=0)
    open_quarantine_count: int = Field(ge=0)
    proposed_resolution_count: int = Field(ge=0)
    freshness_seconds: int | None = Field(default=None, ge=0)


class EnterpriseDryRunReport(StrictModel):
    schema_version: Literal["enterprise-dry-run-report.v1"]
    report_id: Sha256Hex
    input_version: RequiredText
    registry_version: RequiredText
    checkpoint_version: RequiredText
    status: EnterpriseDryRunStatus
    write_performed: Literal[False]
    canonical_import_authorized: Literal[False]
    canonical_changes: list[EnterpriseCanonicalChange]
    quality_findings: list[EnterpriseQualityFinding]
    quarantine_entries: list[EnterpriseQuarantineEntry]
    summary: EnterpriseDryRunSummary


def load_dry_run_input(path: Path) -> EnterpriseDryRunInput:
    return EnterpriseDryRunInput.model_validate(
        yaml.safe_load(path.read_text(encoding="utf-8"))
    )


def load_resolution_file(path: Path) -> EnterpriseResolutionFile:
    return EnterpriseResolutionFile.model_validate(
        yaml.safe_load(path.read_text(encoding="utf-8"))
    )


def run_enterprise_dry_run(
    *,
    sync_result: EnterpriseSyncResult,
    source_records: list[EnterpriseSourceRecord],
    dirty_corpus: EnterpriseDirtyFixtureCorpus,
    registry: EnterpriseMappingRegistry,
    dry_run_input: EnterpriseDryRunInput,
    resolution_file: EnterpriseResolutionFile,
) -> EnterpriseDryRunReport:
    if sync_result.status is not EnterpriseSyncStatus.COMPLETED:
        raise ValueError("dry-run requires a completed sync result")

    changes, change_findings = _canonical_changes(
        sync_result.checkpoint.source_states,
        dry_run_input,
    )
    findings = list(change_findings)
    findings.extend(
        _quality_findings(
            sync_result=sync_result,
            source_records=source_records,
            dirty_corpus=dirty_corpus,
            registry=registry,
            dry_run_input=dry_run_input,
        )
    )
    findings = sorted(findings, key=lambda item: item.finding_id)
    quarantine = _quarantine_entries(findings, resolution_file)

    source_outcome_count = len(sync_result.checkpoint.audit_entries)
    mapped_sync_count = sum(
        item.disposition
        in {EnterpriseSyncDisposition.APPLIED, EnterpriseSyncDisposition.NO_CHANGE}
        for item in sync_result.checkpoint.audit_entries
    )
    dirty_results = [
        result
        for case in dirty_corpus.cases
        for result in map_source_records(case.records, registry)
    ]
    probe_results = [
        map_source_records([probe.record], registry)[0]
        for probe in dry_run_input.quality_probes
    ]
    total_records = source_outcome_count + len(dirty_results) + len(probe_results)
    mapped_records = (
        mapped_sync_count
        + sum(item.disposition is MappingDisposition.ACCEPT for item in dirty_results)
        + sum(item.disposition is MappingDisposition.ACCEPT for item in probe_results)
    )
    rejected = sum(item.disposition is MappingDisposition.REJECT for item in dirty_results)
    quarantined = (
        sum(item.disposition is MappingDisposition.QUARANTINE for item in dirty_results)
        + sum(
            item.disposition is EnterpriseSyncDisposition.QUARANTINED
            for item in sync_result.checkpoint.audit_entries
        )
        + sum(item.disposition is MappingDisposition.QUARANTINE for item in probe_results)
    )
    latest_ingested = max(
        (item.ingested_at for item in source_records + _probe_records(dry_run_input)),
        default=None,
    )
    freshness_seconds = (
        max(0, int((dry_run_input.as_of - latest_ingested).total_seconds()))
        if latest_ingested is not None
        else None
    )
    summary = EnterpriseDryRunSummary(
        source_record_count=total_records,
        mapped_record_count=mapped_records,
        mapping_coverage=mapped_records / total_records if total_records else 0,
        create_count=_count_changes(changes, CanonicalChangeAction.CREATE),
        update_count=_count_changes(changes, CanonicalChangeAction.UPDATE),
        delete_count=_count_changes(changes, CanonicalChangeAction.DELETE),
        no_change_count=_count_changes(changes, CanonicalChangeAction.NO_CHANGE),
        quality_finding_count=len(findings),
        rejected_count=rejected,
        quarantined_count=quarantined,
        open_quarantine_count=sum(
            item.status is EnterpriseQuarantineStatus.OPEN for item in quarantine
        ),
        proposed_resolution_count=sum(
            item.status is EnterpriseQuarantineStatus.RESOLUTION_PROPOSED
            for item in quarantine
        ),
        freshness_seconds=freshness_seconds,
    )
    material = {
        "input_version": dry_run_input.input_version,
        "registry_version": registry.registry_version,
        "checkpoint": sync_result.checkpoint.model_dump(mode="json"),
        "changes": [item.model_dump(mode="json") for item in changes],
        "findings": [item.model_dump(mode="json") for item in findings],
        "quarantine": [item.model_dump(mode="json") for item in quarantine],
    }
    report_id = _hash(material)
    return EnterpriseDryRunReport(
        schema_version="enterprise-dry-run-report.v1",
        report_id=report_id,
        input_version=dry_run_input.input_version,
        registry_version=registry.registry_version,
        checkpoint_version=sync_result.checkpoint.checkpoint_version,
        status=(
            EnterpriseDryRunStatus.BLOCKED
            if any(item.blocks_import for item in findings)
            else EnterpriseDryRunStatus.READY_FOR_REVIEW
        ),
        write_performed=False,
        canonical_import_authorized=False,
        canonical_changes=changes,
        quality_findings=findings,
        quarantine_entries=quarantine,
        summary=summary,
    )


def _canonical_changes(
    states: list[EnterpriseSourceReconciliationState],
    dry_run_input: EnterpriseDryRunInput,
) -> tuple[list[EnterpriseCanonicalChange], list[EnterpriseQualityFinding]]:
    baseline = {
        _identity_key(item.source_identity): item
        for item in dry_run_input.canonical_objects
    }
    key_rules = {
        item.candidate_kind: item.target_field
        for item in dry_run_input.canonical_key_rules
    }
    changes: list[EnterpriseCanonicalChange] = []
    findings: list[EnterpriseQualityFinding] = []
    for state in states:
        existing = baseline.get(_identity_key(state.source_identity))
        if state.deletion_state is not SourceDeletionState.ACTIVE:
            if existing is None:
                continue
            changes.append(
                _change(
                    action=CanonicalChangeAction.DELETE,
                    kind=existing.candidate_kind,
                    key=existing.canonical_key,
                    identity=state.source_identity,
                    before=existing.values,
                    after=None,
                    reasons=state.current_mapping_result.reason_codes,
                )
            )
            continue

        candidates = state.current_mapping_result.structured_candidates
        if not candidates:
            continue
        candidate = candidates[0]
        key_field = key_rules.get(candidate.candidate_kind)
        key_value = candidate.values.get(key_field) if key_field is not None else None
        if not isinstance(key_value, str) or not key_value.strip():
            findings.append(
                _finding(
                    code=EnterpriseQualityCode.UNMAPPED_FIELD,
                    severity=EnterpriseQualitySeverity.ERROR,
                    blocks=True,
                    detail="canonical key field is not mapped",
                    identity=state.source_identity,
                    content_hash=state.current_content_hash,
                    field_name=key_field,
                )
            )
            continue
        if existing is None:
            action = CanonicalChangeAction.CREATE
            before = None
        else:
            before = existing.values
            action = (
                CanonicalChangeAction.NO_CHANGE
                if existing.values == candidate.values
                else CanonicalChangeAction.UPDATE
            )
        changes.append(
            _change(
                action=action,
                kind=candidate.candidate_kind,
                key=key_value,
                identity=state.source_identity,
                before=before,
                after=candidate.values,
                reasons=state.current_mapping_result.reason_codes,
            )
        )
    return sorted(changes, key=lambda item: (item.candidate_kind, item.canonical_key)), findings


def _quality_findings(
    *,
    sync_result: EnterpriseSyncResult,
    source_records: list[EnterpriseSourceRecord],
    dirty_corpus: EnterpriseDirtyFixtureCorpus,
    registry: EnterpriseMappingRegistry,
    dry_run_input: EnterpriseDryRunInput,
) -> list[EnterpriseQualityFinding]:
    findings: list[EnterpriseQualityFinding] = []
    known_acl_refs = set(dry_run_input.known_acl_refs)
    all_records = (
        source_records
        + _probe_records(dry_run_input)
        + [record for case in dirty_corpus.cases for record in case.records]
    )
    for record in all_records:
        profile = registry.resolve(record)
        if record.source_acl_ref not in known_acl_refs:
            findings.append(
                _finding(
                    code=EnterpriseQualityCode.ACL_REFERENCE_UNKNOWN,
                    severity=EnterpriseQualitySeverity.ERROR,
                    blocks=True,
                    detail="source ACL reference is not registered in dry-run input",
                    identity=record.identity,
                    content_hash=record.content_hash,
                )
            )
        if (
            record.effective_at > record.observed_at
            or record.source_updated_at > record.ingested_at
        ):
            findings.append(
                _finding(
                    code=EnterpriseQualityCode.TIME_AMBIGUITY,
                    severity=EnterpriseQualitySeverity.ERROR,
                    blocks=True,
                    detail="enterprise times require explicit review before import",
                    identity=record.identity,
                    content_hash=record.content_hash,
                )
            )
        if record.payload is not None and profile is not None:
            for field_name in sorted(set(record.payload) - _covered_fields(profile)):
                findings.append(
                    _finding(
                        code=EnterpriseQualityCode.UNMAPPED_FIELD,
                        severity=EnterpriseQualitySeverity.WARNING,
                        blocks=False,
                        detail="source payload field is not consumed by the mapping profile",
                        identity=record.identity,
                        content_hash=record.content_hash,
                        field_name=field_name,
                    )
                )

    available_keys = {
        item.canonical_key for item in dry_run_input.canonical_objects
    } | {
        str(value)
        for state in sync_result.checkpoint.source_states
        for candidate in state.current_mapping_result.structured_candidates
        for value in candidate.values.values()
        if isinstance(value, str)
    }
    for probe in dry_run_input.quality_probes:
        for reference_key in probe.reference_keys:
            if reference_key not in available_keys:
                findings.append(
                    _finding(
                        code=EnterpriseQualityCode.DANGLING_REFERENCE,
                        severity=EnterpriseQualitySeverity.ERROR,
                        blocks=True,
                        detail="source reference has no canonical or proposed target",
                        identity=probe.record.identity,
                        content_hash=probe.record.content_hash,
                        reference_key=reference_key,
                    )
                )

    for state in sync_result.checkpoint.source_states:
        age = int((dry_run_input.as_of - state.latest_source_updated_at).total_seconds())
        if age > dry_run_input.stale_after_seconds:
            findings.append(
                _finding(
                    code=EnterpriseQualityCode.STALE_SOURCE,
                    severity=EnterpriseQualitySeverity.WARNING,
                    blocks=False,
                    detail="source update exceeds the configured freshness threshold",
                    identity=state.source_identity,
                    content_hash=state.current_content_hash,
                )
            )

    for audit in sync_result.checkpoint.audit_entries:
        if audit.disposition is EnterpriseSyncDisposition.QUARANTINED:
            findings.append(
                _finding(
                    code=EnterpriseQualityCode.MAPPING_QUARANTINED,
                    severity=EnterpriseQualitySeverity.ERROR,
                    blocks=True,
                    detail="sync reconciliation quarantined the source record",
                    identity=audit.source_identity,
                    content_hash=audit.content_hash,
                    mapping_reasons=audit.mapping_reason_codes,
                )
            )
    for case in dirty_corpus.cases:
        for record, result in zip(
            case.records,
            map_source_records(case.records, registry),
            strict=True,
        ):
            if result.disposition is MappingDisposition.ACCEPT:
                continue
            is_duplicate = MappingReasonCode.DUPLICATE_SOURCE_VERSION in result.reason_codes
            findings.append(
                _finding(
                    code=(
                        EnterpriseQualityCode.MAPPING_REJECTED
                        if result.disposition is MappingDisposition.REJECT
                        else EnterpriseQualityCode.MAPPING_QUARANTINED
                    ),
                    severity=(
                        EnterpriseQualitySeverity.INFO
                        if is_duplicate
                        else EnterpriseQualitySeverity.ERROR
                    ),
                    blocks=not is_duplicate,
                    detail="mapping did not produce an importable candidate",
                    identity=record.identity,
                    content_hash=record.content_hash,
                    mapping_reasons=result.reason_codes,
                )
            )
    return findings


def _quarantine_entries(
    findings: list[EnterpriseQualityFinding],
    resolution_file: EnterpriseResolutionFile,
) -> list[EnterpriseQuarantineEntry]:
    entries: list[EnterpriseQuarantineEntry] = []
    resolutions = {item.quarantine_id: item for item in resolution_file.entries}
    for finding in findings:
        if not finding.blocks_import:
            continue
        quarantine_id = _hash(
            {
                "finding_id": finding.finding_id,
                "identity": (
                    finding.source_identity.model_dump(mode="json")
                    if finding.source_identity is not None
                    else None
                ),
                "content_hash": finding.content_hash,
            }
        )
        resolution = resolutions.get(quarantine_id)
        if (
            resolution is not None
            and resolution.expected_content_hash is not None
            and resolution.expected_content_hash != finding.content_hash
        ):
            raise ValueError("resolution content hash does not match quarantine source")
        entries.append(
            EnterpriseQuarantineEntry(
                quarantine_id=quarantine_id,
                finding_ids=[finding.finding_id],
                source_identity=finding.source_identity,
                content_hash=finding.content_hash,
                status=(
                    EnterpriseQuarantineStatus.RESOLUTION_PROPOSED
                    if resolution is not None
                    else EnterpriseQuarantineStatus.OPEN
                ),
                proposed_resolution=resolution,
            )
        )
    unknown = set(resolutions) - {item.quarantine_id for item in entries}
    if unknown:
        raise ValueError("resolution references an unknown quarantine entry")
    return sorted(entries, key=lambda item: item.quarantine_id)


def _change(
    *,
    action: CanonicalChangeAction,
    kind: StructuredCandidateKind,
    key: str,
    identity: EnterpriseSourceIdentity,
    before: dict[str, JsonValue] | None,
    after: dict[str, JsonValue] | None,
    reasons: list[MappingReasonCode],
) -> EnterpriseCanonicalChange:
    material = {
        "action": action,
        "kind": kind,
        "key": key,
        "identity": identity.model_dump(mode="json"),
        "before": before,
        "after": after,
        "reasons": reasons,
    }
    return EnterpriseCanonicalChange(
        change_id=_hash(material),
        action=action,
        candidate_kind=kind,
        canonical_key=key,
        source_identity=identity,
        before_values=before,
        after_values=after,
        reason_codes=reasons,
    )


def _finding(
    *,
    code: EnterpriseQualityCode,
    severity: EnterpriseQualitySeverity,
    blocks: bool,
    detail: str,
    identity: EnterpriseSourceIdentity | None = None,
    content_hash: str | None = None,
    field_name: str | None = None,
    reference_key: str | None = None,
    mapping_reasons: list[MappingReasonCode] | None = None,
) -> EnterpriseQualityFinding:
    material = {
        "code": code,
        "severity": severity,
        "blocks": blocks,
        "detail": detail,
        "identity": identity.model_dump(mode="json") if identity is not None else None,
        "content_hash": content_hash,
        "field_name": field_name,
        "reference_key": reference_key,
        "mapping_reasons": mapping_reasons or [],
    }
    return EnterpriseQualityFinding(
        finding_id=_hash(material),
        code=code,
        severity=severity,
        blocks_import=blocks,
        detail=detail,
        source_identity=identity,
        content_hash=content_hash,
        field_name=field_name,
        reference_key=reference_key,
        mapping_reason_codes=mapping_reasons or [],
    )


def _covered_fields(profile: EnterpriseMappingProfile) -> set[str]:
    fields = set(profile.required_source_fields)
    fields.update(item.source_field for item in profile.field_mappings)
    fields.update(item.source_field for item in profile.unstructured_rules)
    if profile.status_source_field is not None:
        fields.add(profile.status_source_field)
    return fields


def _probe_records(dry_run_input: EnterpriseDryRunInput) -> list[EnterpriseSourceRecord]:
    return [item.record for item in dry_run_input.quality_probes]


def _count_changes(
    changes: list[EnterpriseCanonicalChange],
    action: CanonicalChangeAction,
) -> int:
    return sum(item.action is action for item in changes)


def _identity_key(identity: EnterpriseSourceIdentity) -> tuple[str, str, str, str]:
    return (
        identity.source_system,
        identity.source_tenant,
        identity.source_object_type,
        identity.external_id,
    )


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
