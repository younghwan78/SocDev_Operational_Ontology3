import hashlib
import json
from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, field_validator, model_validator

from soc_ot.application.enterprise_ingestion import (
    EnterpriseSourceIdentity,
    EnterpriseSourceRecord,
    RequiredText,
    Sha256Hex,
    SourceDeletionState,
)
from soc_ot.application.enterprise_mapping import (
    EnterpriseMappingRegistry,
    EnterpriseMappingResult,
    MappingDisposition,
    MappingReasonCode,
    StructuredCandidateKind,
    map_source_records,
)
from soc_ot.domain.models import StrictModel


class EnterpriseSyncMode(StrEnum):
    FULL = "FULL"
    INCREMENTAL = "INCREMENTAL"


class EnterpriseSyncStatus(StrEnum):
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    FAILED = "FAILED"


class EnterpriseSyncDisposition(StrEnum):
    APPLIED = "APPLIED"
    NO_CHANGE = "NO_CHANGE"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"


class EnterpriseSyncReasonCode(StrEnum):
    MAPPING_APPLIED = "MAPPING_APPLIED"
    CONTENT_UNCHANGED = "CONTENT_UNCHANGED"
    STALE_SOURCE_UPDATE = "STALE_SOURCE_UPDATE"
    TOMBSTONE_APPLIED = "TOMBSTONE_APPLIED"
    ACCESS_RESTRICTION_APPLIED = "ACCESS_RESTRICTION_APPLIED"


class EnterpriseSyncPolicy(StrictModel):
    schema_version: Literal["enterprise-sync-policy.v1"]
    policy_version: RequiredText
    max_attempts_per_page: int = Field(default=3, ge=1, le=10)
    retry_backoff_seconds: list[int] = Field(default=[1, 2], min_length=1, max_length=9)

    @field_validator("retry_backoff_seconds")
    @classmethod
    def require_positive_backoff(cls, value: list[int]) -> list[int]:
        if any(item <= 0 for item in value):
            raise ValueError("retry backoff must be positive")
        return value

    @model_validator(mode="after")
    def cover_retry_attempts(self) -> "EnterpriseSyncPolicy":
        if len(self.retry_backoff_seconds) < self.max_attempts_per_page - 1:
            raise ValueError("retry backoff must cover every retry attempt")
        return self


class EnterpriseSyncPage(StrictModel):
    schema_version: Literal["enterprise-sync-page.v1"]
    page_index: int = Field(ge=0)
    page_token: RequiredText
    cursor_value: RequiredText
    records: list[EnterpriseSourceRecord] = Field(min_length=1)


class EnterpriseSourceReconciliationState(StrictModel):
    schema_version: Literal["enterprise-source-reconciliation-state.v1"]
    source_identity: EnterpriseSourceIdentity
    current_external_version: RequiredText
    current_content_hash: Sha256Hex
    current_effective_at: datetime
    latest_source_updated_at: datetime
    deletion_state: SourceDeletionState
    mapping_revision: int = Field(ge=1)
    current_mapping_result: EnterpriseMappingResult
    seen_version_hashes: dict[str, Sha256Hex] = Field(min_length=1)

    @field_validator("current_effective_at", "latest_source_updated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("reconciliation time must include a timezone")
        return value


class EnterpriseSyncAuditEntry(StrictModel):
    schema_version: Literal["enterprise-sync-audit-entry.v1"]
    audit_id: Sha256Hex
    page_index: int = Field(ge=0)
    record_index: int = Field(ge=0)
    source_identity: EnterpriseSourceIdentity
    external_version: RequiredText
    content_hash: Sha256Hex
    disposition: EnterpriseSyncDisposition
    reason_code: EnterpriseSyncReasonCode | None = None
    mapping_reason_codes: list[MappingReasonCode] = Field(default_factory=list)
    mapping_revision: int | None = Field(default=None, ge=1)


class EnterpriseRetryAuditEntry(StrictModel):
    schema_version: Literal["enterprise-retry-audit-entry.v1"]
    page_index: int = Field(ge=0)
    attempt: int = Field(ge=1)
    retry_scheduled_after_seconds: int | None = Field(default=None, ge=1)
    exhausted: bool

    @model_validator(mode="after")
    def align_retry_state(self) -> "EnterpriseRetryAuditEntry":
        if self.exhausted == (self.retry_scheduled_after_seconds is not None):
            raise ValueError("retry audit must be either scheduled or exhausted")
        return self


class EnterpriseSyncCheckpoint(StrictModel):
    schema_version: Literal["enterprise-sync-checkpoint.v1"]
    checkpoint_version: RequiredText
    mode: EnterpriseSyncMode
    next_page_index: int = Field(ge=0)
    next_page_token: str | None = None
    cursor_value: str | None = None
    source_states: list[EnterpriseSourceReconciliationState] = Field(default_factory=list)
    ordered_event_identities: list[EnterpriseSourceIdentity] = Field(default_factory=list)
    audit_entries: list[EnterpriseSyncAuditEntry] = Field(default_factory=list)
    retry_entries: list[EnterpriseRetryAuditEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_unique_state_and_audit(self) -> "EnterpriseSyncCheckpoint":
        identities = [_identity_key(item.source_identity) for item in self.source_states]
        if len(identities) != len(set(identities)):
            raise ValueError("checkpoint source identity must be unique")
        event_identities = [
            _identity_key(item) for item in self.ordered_event_identities
        ]
        if len(event_identities) != len(set(event_identities)):
            raise ValueError("checkpoint event identity must be unique")
        expected_events = [
            _identity_key(item.source_identity)
            for item in _ordered_event_states(self.source_states)
        ]
        if event_identities != expected_events:
            raise ValueError("checkpoint event order must match reconciled event state")
        audit_ids = [item.audit_id for item in self.audit_entries]
        if len(audit_ids) != len(set(audit_ids)):
            raise ValueError("checkpoint audit_id must be unique")
        return self


class EnterpriseSyncResult(StrictModel):
    schema_version: Literal["enterprise-sync-result.v1"]
    status: EnterpriseSyncStatus
    checkpoint: EnterpriseSyncCheckpoint
    processed_page_count: int = Field(ge=0)
    processed_record_count: int = Field(ge=0)
    failed_page_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def align_failure(self) -> "EnterpriseSyncResult":
        if self.status is EnterpriseSyncStatus.FAILED:
            if self.failed_page_index is None:
                raise ValueError("failed sync requires failed_page_index")
        elif self.failed_page_index is not None:
            raise ValueError("non-failed sync cannot carry failed_page_index")
        return self


class EnterpriseSyncFixtureCorpus(StrictModel):
    schema_version: Literal["enterprise-sync-fixture-corpus.v1"]
    corpus_version: RequiredText
    policy: EnterpriseSyncPolicy
    pages: list[EnterpriseSyncPage] = Field(min_length=1)
    transient_failures_before_success: dict[int, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_pages(self) -> "EnterpriseSyncFixtureCorpus":
        expected = list(range(len(self.pages)))
        actual = [item.page_index for item in self.pages]
        if actual != expected:
            raise ValueError("sync fixture pages must be contiguous and ordered")
        page_indexes = set(actual)
        if not set(self.transient_failures_before_success) <= page_indexes:
            raise ValueError("transient failure references an unknown page")
        if any(item < 0 for item in self.transient_failures_before_success.values()):
            raise ValueError("transient failure count cannot be negative")
        return self


def load_sync_fixture_corpus(path: Path) -> EnterpriseSyncFixtureCorpus:
    return EnterpriseSyncFixtureCorpus.model_validate(
        yaml.safe_load(path.read_text(encoding="utf-8"))
    )


def reconcile_enterprise_pages(
    *,
    pages: list[EnterpriseSyncPage],
    registry: EnterpriseMappingRegistry,
    policy: EnterpriseSyncPolicy,
    mode: EnterpriseSyncMode,
    checkpoint: EnterpriseSyncCheckpoint | None = None,
    max_pages: int | None = None,
    transient_failures_before_success: dict[int, int] | None = None,
) -> EnterpriseSyncResult:
    """Apply source pages deterministically without sleeping or persisting side effects."""
    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages must be positive")
    _validate_page_sequence(pages)
    state = _copy_or_create_checkpoint(checkpoint, mode)
    if state.next_page_index > len(pages):
        raise ValueError("checkpoint points beyond supplied pages")
    if checkpoint is not None:
        expected_token = (
            pages[state.next_page_index].page_token
            if state.next_page_index < len(pages)
            else None
        )
        if state.next_page_token != expected_token:
            raise ValueError("checkpoint page token does not match supplied pages")

    failures = transient_failures_before_success or {}
    processed_pages = 0
    processed_records = 0
    states = {_identity_key(item.source_identity): item for item in state.source_states}
    audits = list(state.audit_entries)
    retry_entries = list(state.retry_entries)

    while state.next_page_index < len(pages):
        if max_pages is not None and processed_pages >= max_pages:
            break
        page = pages[state.next_page_index]
        failed_attempts = failures.get(page.page_index, 0)
        retry_result = _simulate_page_attempts(page.page_index, failed_attempts, policy)
        retry_entries.extend(retry_result)
        if retry_result and retry_result[-1].exhausted:
            failed_checkpoint = _checkpoint(
                mode=mode,
                next_page_index=state.next_page_index,
                pages=pages,
                cursor_value=state.cursor_value,
                states=states,
                audits=audits,
                retries=retry_entries,
            )
            return EnterpriseSyncResult(
                schema_version="enterprise-sync-result.v1",
                status=EnterpriseSyncStatus.FAILED,
                checkpoint=failed_checkpoint,
                processed_page_count=processed_pages,
                processed_record_count=processed_records,
                failed_page_index=page.page_index,
            )

        for record_index, record in enumerate(page.records):
            audit, reconciled = _reconcile_record(
                page_index=page.page_index,
                record_index=record_index,
                record=record,
                registry=registry,
                prior=states.get(_identity_key(record.identity)),
            )
            audits.append(audit)
            if reconciled is not None:
                states[_identity_key(record.identity)] = reconciled
            processed_records += 1

        processed_pages += 1
        state = _checkpoint(
            mode=mode,
            next_page_index=page.page_index + 1,
            pages=pages,
            cursor_value=page.cursor_value,
            states=states,
            audits=audits,
            retries=retry_entries,
        )

    status = (
        EnterpriseSyncStatus.COMPLETED
        if state.next_page_index == len(pages)
        else EnterpriseSyncStatus.PAUSED
    )
    return EnterpriseSyncResult(
        schema_version="enterprise-sync-result.v1",
        status=status,
        checkpoint=state,
        processed_page_count=processed_pages,
        processed_record_count=processed_records,
    )


def _reconcile_record(
    *,
    page_index: int,
    record_index: int,
    record: EnterpriseSourceRecord,
    registry: EnterpriseMappingRegistry,
    prior: EnterpriseSourceReconciliationState | None,
) -> tuple[EnterpriseSyncAuditEntry, EnterpriseSourceReconciliationState | None]:
    prior_hash = (
        prior.seen_version_hashes.get(record.external_version) if prior is not None else None
    )
    if prior_hash is not None:
        disposition = (
            EnterpriseSyncDisposition.NO_CHANGE
            if prior_hash == record.content_hash
            else EnterpriseSyncDisposition.QUARANTINED
        )
        mapping_reason = (
            MappingReasonCode.DUPLICATE_SOURCE_VERSION
            if prior_hash == record.content_hash
            else MappingReasonCode.SOURCE_VERSION_CONFLICT
        )
        return (
            _audit(
                page_index,
                record_index,
                record,
                disposition,
                EnterpriseSyncReasonCode.CONTENT_UNCHANGED
                if disposition is EnterpriseSyncDisposition.NO_CHANGE
                else None,
                [mapping_reason],
                prior.mapping_revision if prior is not None else None,
            ),
            prior,
        )

    seen_versions = dict(prior.seen_version_hashes) if prior is not None else {}
    seen_versions[record.external_version] = record.content_hash

    is_inactive = record.deletion_state is not SourceDeletionState.ACTIVE
    if (
        prior is not None
        and not is_inactive
        and record.source_updated_at < prior.latest_source_updated_at
    ):
        updated_prior = prior.model_copy(update={"seen_version_hashes": seen_versions})
        return (
            _audit(
                page_index,
                record_index,
                record,
                EnterpriseSyncDisposition.QUARANTINED,
                EnterpriseSyncReasonCode.STALE_SOURCE_UPDATE,
                [MappingReasonCode.OUT_OF_ORDER_SOURCE_UPDATE],
                prior.mapping_revision,
            ),
            updated_prior,
        )

    if prior is not None and record.content_hash == prior.current_content_hash:
        updated_prior = prior.model_copy(
            update={
                "current_external_version": record.external_version,
                "current_effective_at": record.effective_at,
                "latest_source_updated_at": max(
                    prior.latest_source_updated_at, record.source_updated_at
                ),
                "seen_version_hashes": seen_versions,
            }
        )
        return (
            _audit(
                page_index,
                record_index,
                record,
                EnterpriseSyncDisposition.NO_CHANGE,
                EnterpriseSyncReasonCode.CONTENT_UNCHANGED,
                [],
                prior.mapping_revision,
            ),
            updated_prior,
        )

    mapping = map_source_records([record], registry)[0]
    if mapping.disposition is not MappingDisposition.ACCEPT:
        disposition = (
            EnterpriseSyncDisposition.QUARANTINED
            if mapping.disposition is MappingDisposition.QUARANTINE
            else EnterpriseSyncDisposition.REJECTED
        )
        rejected_prior = (
            prior.model_copy(update={"seen_version_hashes": seen_versions})
            if prior is not None
            else None
        )
        return (
            _audit(
                page_index,
                record_index,
                record,
                disposition,
                None,
                mapping.reason_codes,
                prior.mapping_revision if prior is not None else None,
            ),
            rejected_prior,
        )

    revision = 1 if prior is None else prior.mapping_revision + 1
    reason = EnterpriseSyncReasonCode.MAPPING_APPLIED
    if record.deletion_state is SourceDeletionState.DELETED:
        reason = EnterpriseSyncReasonCode.TOMBSTONE_APPLIED
    elif record.deletion_state is SourceDeletionState.RESTRICTED:
        reason = EnterpriseSyncReasonCode.ACCESS_RESTRICTION_APPLIED
    reconciled = EnterpriseSourceReconciliationState(
        schema_version="enterprise-source-reconciliation-state.v1",
        source_identity=record.identity,
        current_external_version=record.external_version,
        current_content_hash=record.content_hash,
        current_effective_at=record.effective_at,
        latest_source_updated_at=(
            record.source_updated_at
            if prior is None
            else max(prior.latest_source_updated_at, record.source_updated_at)
        ),
        deletion_state=record.deletion_state,
        mapping_revision=revision,
        current_mapping_result=mapping,
        seen_version_hashes=seen_versions,
    )
    return (
        _audit(
            page_index,
            record_index,
            record,
            EnterpriseSyncDisposition.APPLIED,
            reason,
            mapping.reason_codes,
            revision,
        ),
        reconciled,
    )


def _audit(
    page_index: int,
    record_index: int,
    record: EnterpriseSourceRecord,
    disposition: EnterpriseSyncDisposition,
    reason: EnterpriseSyncReasonCode | None,
    mapping_reasons: list[MappingReasonCode],
    revision: int | None,
) -> EnterpriseSyncAuditEntry:
    material = {
        "page_index": page_index,
        "record_index": record_index,
        "identity": record.identity.model_dump(mode="json"),
        "external_version": record.external_version,
        "content_hash": record.content_hash,
        "disposition": disposition,
        "reason": reason,
        "mapping_reasons": mapping_reasons,
        "mapping_revision": revision,
    }
    audit_id = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    return EnterpriseSyncAuditEntry(
        schema_version="enterprise-sync-audit-entry.v1",
        audit_id=audit_id,
        page_index=page_index,
        record_index=record_index,
        source_identity=record.identity,
        external_version=record.external_version,
        content_hash=record.content_hash,
        disposition=disposition,
        reason_code=reason,
        mapping_reason_codes=mapping_reasons,
        mapping_revision=revision,
    )


def _simulate_page_attempts(
    page_index: int,
    failures_before_success: int,
    policy: EnterpriseSyncPolicy,
) -> list[EnterpriseRetryAuditEntry]:
    entries: list[EnterpriseRetryAuditEntry] = []
    attempted_failures = min(failures_before_success, policy.max_attempts_per_page)
    for failed_index in range(attempted_failures):
        attempt = failed_index + 1
        exhausted = attempt == policy.max_attempts_per_page
        entries.append(
            EnterpriseRetryAuditEntry(
                schema_version="enterprise-retry-audit-entry.v1",
                page_index=page_index,
                attempt=attempt,
                retry_scheduled_after_seconds=(
                    None if exhausted else policy.retry_backoff_seconds[failed_index]
                ),
                exhausted=exhausted,
            )
        )
    return entries


def _copy_or_create_checkpoint(
    checkpoint: EnterpriseSyncCheckpoint | None,
    mode: EnterpriseSyncMode,
) -> EnterpriseSyncCheckpoint:
    if checkpoint is None:
        return EnterpriseSyncCheckpoint(
            schema_version="enterprise-sync-checkpoint.v1",
            checkpoint_version="enterprise-sync-checkpoint.1",
            mode=mode,
            next_page_index=0,
        )
    if checkpoint.mode is not mode:
        raise ValueError("checkpoint mode does not match requested sync mode")
    return checkpoint.model_copy(deep=True)


def _checkpoint(
    *,
    mode: EnterpriseSyncMode,
    next_page_index: int,
    pages: list[EnterpriseSyncPage],
    cursor_value: str | None,
    states: dict[tuple[str, str, str, str], EnterpriseSourceReconciliationState],
    audits: list[EnterpriseSyncAuditEntry],
    retries: list[EnterpriseRetryAuditEntry],
) -> EnterpriseSyncCheckpoint:
    return EnterpriseSyncCheckpoint(
        schema_version="enterprise-sync-checkpoint.v1",
        checkpoint_version="enterprise-sync-checkpoint.1",
        mode=mode,
        next_page_index=next_page_index,
        next_page_token=(
            pages[next_page_index].page_token if next_page_index < len(pages) else None
        ),
        cursor_value=cursor_value,
        source_states=[states[key] for key in sorted(states)],
        ordered_event_identities=[
            item.source_identity for item in _ordered_event_states(states.values())
        ],
        audit_entries=audits,
        retry_entries=retries,
    )


def _validate_page_sequence(pages: list[EnterpriseSyncPage]) -> None:
    if [item.page_index for item in pages] != list(range(len(pages))):
        raise ValueError("sync pages must be contiguous and ordered")
    if len({item.page_token for item in pages}) != len(pages):
        raise ValueError("sync page_token must be unique")


def _ordered_event_states(
    states: Iterable[EnterpriseSourceReconciliationState],
) -> list[EnterpriseSourceReconciliationState]:
    candidates = [
        item
        for item in states
        if item.deletion_state is SourceDeletionState.ACTIVE
        and any(
            candidate.candidate_kind is StructuredCandidateKind.EVENT
            for candidate in item.current_mapping_result.structured_candidates
        )
    ]
    return sorted(
        candidates,
        key=lambda item: (
            item.current_effective_at,
            item.latest_source_updated_at,
            _identity_key(item.source_identity),
        ),
    )


def _identity_key(identity: EnterpriseSourceIdentity) -> tuple[str, str, str, str]:
    return (
        identity.source_system,
        identity.source_tenant,
        identity.source_object_type,
        identity.external_id,
    )
