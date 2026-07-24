from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, JsonValue, model_validator

from soc_ot.application.enterprise_ingestion import (
    EnterpriseSourceIdentity,
    EnterpriseSourceRecord,
    RequiredText,
    SourceDeletionState,
)
from soc_ot.application.project_fixture_contracts import (
    IssueStatus,
    ProjectEventType,
    ProjectLifecycleStage,
)
from soc_ot.domain.models import StrictModel, WorkItemStatus


class MappingDisposition(StrEnum):
    ACCEPT = "ACCEPT"
    QUARANTINE = "QUARANTINE"
    REJECT = "REJECT"


class StructuredCandidateKind(StrEnum):
    PROJECT = "PROJECT"
    WORK_ITEM = "WORK_ITEM"
    ISSUE = "ISSUE"
    EVIDENCE = "EVIDENCE"
    EVENT = "EVENT"


_CANONICAL_STATUS_VALUES: dict[StructuredCandidateKind, set[str]] = {
    StructuredCandidateKind.PROJECT: {str(item) for item in ProjectLifecycleStage},
    StructuredCandidateKind.WORK_ITEM: {str(item) for item in WorkItemStatus},
    StructuredCandidateKind.ISSUE: {str(item) for item in IssueStatus},
    StructuredCandidateKind.EVENT: {str(item) for item in ProjectEventType},
}


class UnstructuredCandidateKind(StrEnum):
    CLAIM = "CLAIM"
    RISK = "RISK"
    ASSUMPTION = "ASSUMPTION"


class CandidateReviewStatus(StrEnum):
    UNREVIEWED = "UNREVIEWED"


class MappingReasonCode(StrEnum):
    MAPPED = "MAPPED"
    PROFILE_NOT_FOUND = "PROFILE_NOT_FOUND"
    REQUIRED_FIELD_MISSING = "REQUIRED_FIELD_MISSING"
    STATUS_UNMAPPED = "STATUS_UNMAPPED"
    DUPLICATE_SOURCE_VERSION = "DUPLICATE_SOURCE_VERSION"
    SOURCE_VERSION_CONFLICT = "SOURCE_VERSION_CONFLICT"
    OUT_OF_ORDER_SOURCE_UPDATE = "OUT_OF_ORDER_SOURCE_UPDATE"
    SOURCE_URL_CHANGED = "SOURCE_URL_CHANGED"
    SOURCE_DELETED = "SOURCE_DELETED"
    SOURCE_RESTRICTED = "SOURCE_RESTRICTED"
    LATE_ARRIVAL = "LATE_ARRIVAL"


class SourceSpan(StrictModel):
    json_pointer: RequiredText
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_offsets(self) -> "SourceSpan":
        if (self.start_offset is None) != (self.end_offset is None):
            raise ValueError("source span offsets must be provided together")
        if (
            self.start_offset is not None
            and self.end_offset is not None
            and self.end_offset <= self.start_offset
        ):
            raise ValueError("source span end_offset must follow start_offset")
        return self


class FieldMapping(StrictModel):
    source_field: RequiredText
    target_field: RequiredText


class UnstructuredExtractionRule(StrictModel):
    source_field: RequiredText
    candidate_kind: UnstructuredCandidateKind
    extractor_version: RequiredText


class EnterpriseMappingProfile(StrictModel):
    schema_version: Literal["enterprise-mapping-profile.v1"]
    profile_id: RequiredText
    mapping_version: RequiredText
    source_system: RequiredText
    source_object_type: RequiredText
    target_kind: StructuredCandidateKind
    required_source_fields: list[RequiredText] = Field(min_length=1)
    field_mappings: list[FieldMapping] = Field(min_length=1)
    status_source_field: RequiredText | None = None
    status_target_field: RequiredText | None = None
    status_map: dict[str, str] = Field(default_factory=dict)
    unstructured_rules: list[UnstructuredExtractionRule] = Field(default_factory=list)
    late_arrival_after_seconds: int = Field(default=86400, ge=0)

    @model_validator(mode="after")
    def validate_profile(self) -> "EnterpriseMappingProfile":
        required = self._unique(self.required_source_fields, "required source field")
        mapped_sources = self._unique(
            [item.source_field for item in self.field_mappings],
            "mapped source field",
        )
        self._unique(
            [item.target_field for item in self.field_mappings],
            "mapped target field",
        )
        self._unique(
            [item.source_field for item in self.unstructured_rules],
            "unstructured source field",
        )
        status_parts = (
            self.status_source_field is not None,
            self.status_target_field is not None,
            bool(self.status_map),
        )
        if any(status_parts) and not all(status_parts):
            raise ValueError("status mapping requires source field, target field and status_map")
        if self.status_source_field is not None:
            if self.status_source_field not in required:
                raise ValueError("status source field must be required")
            if self.status_source_field in mapped_sources:
                raise ValueError("status source field cannot also be a direct field mapping")
        for source_value, target_value in self.status_map.items():
            if not source_value.strip() or not target_value.strip():
                raise ValueError("status map values cannot be blank")
        allowed_statuses = _CANONICAL_STATUS_VALUES.get(self.target_kind)
        if allowed_statuses is not None and not set(self.status_map.values()) <= allowed_statuses:
            raise ValueError("status map contains a non-canonical target value")
        return self

    @staticmethod
    def _unique(values: list[str], label: str) -> set[str]:
        unique = set(values)
        if len(unique) != len(values):
            raise ValueError(f"duplicate {label}")
        return unique


class EnterpriseMappingRegistry(StrictModel):
    schema_version: Literal["enterprise-mapping-registry.v1"]
    registry_version: RequiredText
    profiles: list[EnterpriseMappingProfile] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_profiles(self) -> "EnterpriseMappingRegistry":
        profile_ids = [item.profile_id for item in self.profiles]
        source_keys = [(item.source_system, item.source_object_type) for item in self.profiles]
        if len(set(profile_ids)) != len(profile_ids):
            raise ValueError("mapping registry profile_id must be unique")
        if len(set(source_keys)) != len(source_keys):
            raise ValueError("mapping registry source key must be unique")
        return self

    def resolve(self, record: EnterpriseSourceRecord) -> EnterpriseMappingProfile | None:
        return next(
            (
                profile
                for profile in self.profiles
                if profile.source_system == record.source_system
                and profile.source_object_type == record.source_object_type
            ),
            None,
        )


class StructuredMappingCandidate(StrictModel):
    schema_version: Literal["enterprise-structured-candidate.v1"]
    candidate_kind: StructuredCandidateKind
    source_identity: EnterpriseSourceIdentity
    external_version: RequiredText
    mapping_profile_id: RequiredText
    mapping_version: RequiredText
    values: dict[str, JsonValue] = Field(min_length=1)
    source_spans: list[SourceSpan] = Field(min_length=1)


class UnstructuredMappingCandidate(StrictModel):
    schema_version: Literal["enterprise-unstructured-candidate.v1"]
    candidate_kind: UnstructuredCandidateKind
    source_identity: EnterpriseSourceIdentity
    external_version: RequiredText
    mapping_profile_id: RequiredText
    mapping_version: RequiredText
    extractor_version: RequiredText
    review_status: Literal[CandidateReviewStatus.UNREVIEWED]
    extractor_confidence: float | None = Field(default=None, ge=0, le=1)
    text: str = Field(min_length=1, max_length=65536)
    source_span: SourceSpan

    @model_validator(mode="after")
    def require_text_offsets(self) -> "UnstructuredMappingCandidate":
        if not self.text.strip():
            raise ValueError("unstructured candidate text cannot be blank")
        if self.source_span.start_offset is None or self.source_span.end_offset is None:
            raise ValueError("unstructured candidate requires source span offsets")
        if self.source_span.end_offset > len(self.text):
            raise ValueError("source span exceeds extracted text")
        return self


class EnterpriseMappingResult(StrictModel):
    schema_version: Literal["enterprise-mapping-result.v1"]
    source_identity: EnterpriseSourceIdentity
    external_version: RequiredText
    disposition: MappingDisposition
    reason_codes: list[MappingReasonCode] = Field(min_length=1)
    structured_candidates: list[StructuredMappingCandidate] = Field(default_factory=list)
    unstructured_candidates: list[UnstructuredMappingCandidate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_disposition(self) -> "EnterpriseMappingResult":
        has_candidates = bool(self.structured_candidates or self.unstructured_candidates)
        if self.disposition is MappingDisposition.ACCEPT and not has_candidates:
            raise ValueError("accepted mapping result requires a candidate")
        if self.disposition is not MappingDisposition.ACCEPT and has_candidates:
            raise ValueError("quarantined or rejected mapping result cannot carry candidates")
        return self


class DirtyFixturePattern(StrEnum):
    NORMAL = "NORMAL"
    MISSING_FIELD = "MISSING_FIELD"
    UNKNOWN_STATUS = "UNKNOWN_STATUS"
    DUPLICATE_UPDATE = "DUPLICATE_UPDATE"
    OUT_OF_ORDER_EVENT = "OUT_OF_ORDER_EVENT"
    MOVED_PAGE = "MOVED_PAGE"
    DELETED_OBJECT = "DELETED_OBJECT"
    RESTRICTED_OBJECT = "RESTRICTED_OBJECT"
    CONFLICTING_SOURCE = "CONFLICTING_SOURCE"
    LATE_EVIDENCE = "LATE_EVIDENCE"


class ExpectedMappingResult(StrictModel):
    disposition: MappingDisposition
    required_reason_codes: list[MappingReasonCode] = Field(min_length=1)


class EnterpriseDirtyFixtureCase(StrictModel):
    case_id: RequiredText
    pattern: DirtyFixturePattern
    records: list[EnterpriseSourceRecord] = Field(min_length=1)
    expected_results: list[ExpectedMappingResult] = Field(min_length=1)

    @model_validator(mode="after")
    def align_expected_results(self) -> "EnterpriseDirtyFixtureCase":
        if len(self.records) != len(self.expected_results):
            raise ValueError("dirty fixture records and expected results must align")
        return self


class EnterpriseDirtyFixtureCorpus(StrictModel):
    schema_version: Literal["enterprise-dirty-fixture-corpus.v1"]
    corpus_version: RequiredText
    cases: list[EnterpriseDirtyFixtureCase] = Field(min_length=1)

    @model_validator(mode="after")
    def require_pattern_coverage(self) -> "EnterpriseDirtyFixtureCorpus":
        case_ids = [item.case_id for item in self.cases]
        patterns = [item.pattern for item in self.cases]
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("dirty fixture case_id must be unique")
        if set(patterns) != set(DirtyFixturePattern):
            raise ValueError("dirty fixture corpus must cover every declared pattern")
        return self


def load_mapping_registry(path: Path) -> EnterpriseMappingRegistry:
    return EnterpriseMappingRegistry.model_validate(
        yaml.safe_load(path.read_text(encoding="utf-8"))
    )


def load_dirty_fixture_corpus(path: Path) -> EnterpriseDirtyFixtureCorpus:
    return EnterpriseDirtyFixtureCorpus.model_validate(
        yaml.safe_load(path.read_text(encoding="utf-8"))
    )


def map_source_records(
    records: list[EnterpriseSourceRecord],
    registry: EnterpriseMappingRegistry,
) -> list[EnterpriseMappingResult]:
    results: list[EnterpriseMappingResult] = []
    seen_versions: dict[tuple[str, str, str, str, str], str] = {}
    previous: dict[tuple[str, str, str, str], EnterpriseSourceRecord] = {}

    for record in records:
        identity_key = _identity_key(record)
        version_key = (*identity_key, record.external_version)
        prior_hash = seen_versions.get(version_key)
        if prior_hash is not None:
            reason = (
                MappingReasonCode.DUPLICATE_SOURCE_VERSION
                if prior_hash == record.content_hash
                else MappingReasonCode.SOURCE_VERSION_CONFLICT
            )
            disposition = (
                MappingDisposition.REJECT
                if reason is MappingReasonCode.DUPLICATE_SOURCE_VERSION
                else MappingDisposition.QUARANTINE
            )
            results.append(_empty_result(record, disposition, reason))
            continue
        seen_versions[version_key] = record.content_hash

        profile = registry.resolve(record)
        if profile is None:
            results.append(
                _empty_result(
                    record,
                    MappingDisposition.REJECT,
                    MappingReasonCode.PROFILE_NOT_FOUND,
                )
            )
            continue

        prior = previous.get(identity_key)
        if (
            prior is not None
            and record.ingested_at >= prior.ingested_at
            and record.source_updated_at < prior.source_updated_at
        ):
            results.append(
                _empty_result(
                    record,
                    MappingDisposition.QUARANTINE,
                    MappingReasonCode.OUT_OF_ORDER_SOURCE_UPDATE,
                )
            )
            continue

        result = _map_record(record, profile)
        if result.disposition is MappingDisposition.ACCEPT:
            reasons = list(result.reason_codes)
            if prior is not None and record.source_url != prior.source_url:
                reasons.append(MappingReasonCode.SOURCE_URL_CHANGED)
            delay_seconds = (record.observed_at - record.effective_at).total_seconds()
            if delay_seconds > profile.late_arrival_after_seconds:
                reasons.append(MappingReasonCode.LATE_ARRIVAL)
            result = result.model_copy(update={"reason_codes": reasons})
            previous[identity_key] = record
        results.append(result)

    return results


def _map_record(
    record: EnterpriseSourceRecord,
    profile: EnterpriseMappingProfile,
) -> EnterpriseMappingResult:
    if record.deletion_state is not SourceDeletionState.ACTIVE:
        reason = (
            MappingReasonCode.SOURCE_DELETED
            if record.deletion_state is SourceDeletionState.DELETED
            else MappingReasonCode.SOURCE_RESTRICTED
        )
        candidate = StructuredMappingCandidate(
            schema_version="enterprise-structured-candidate.v1",
            candidate_kind=StructuredCandidateKind.EVENT,
            source_identity=record.identity,
            external_version=record.external_version,
            mapping_profile_id=profile.profile_id,
            mapping_version=profile.mapping_version,
            values={"deletion_state": record.deletion_state},
            source_spans=[SourceSpan(json_pointer="/deletion_state")],
        )
        return EnterpriseMappingResult(
            schema_version="enterprise-mapping-result.v1",
            source_identity=record.identity,
            external_version=record.external_version,
            disposition=MappingDisposition.ACCEPT,
            reason_codes=[reason],
            structured_candidates=[candidate],
        )

    payload = record.payload
    if payload is None:
        raise AssertionError("validated active source record has no payload")
    missing = [
        field
        for field in profile.required_source_fields
        if field not in payload or payload[field] in (None, "")
    ]
    if missing:
        return _empty_result(
            record,
            MappingDisposition.QUARANTINE,
            MappingReasonCode.REQUIRED_FIELD_MISSING,
        )

    values: dict[str, JsonValue] = {}
    spans: list[SourceSpan] = []
    for field_mapping in profile.field_mappings:
        if field_mapping.source_field in payload:
            values[field_mapping.target_field] = payload[field_mapping.source_field]
            spans.append(
                SourceSpan(
                    json_pointer=f"/payload/{_escape_pointer(field_mapping.source_field)}"
                )
            )

    if profile.status_source_field is not None and profile.status_target_field is not None:
        source_status = payload[profile.status_source_field]
        if not isinstance(source_status, str) or source_status not in profile.status_map:
            return _empty_result(
                record,
                MappingDisposition.QUARANTINE,
                MappingReasonCode.STATUS_UNMAPPED,
            )
        values[profile.status_target_field] = profile.status_map[source_status]
        spans.append(
            SourceSpan(
                json_pointer=f"/payload/{_escape_pointer(profile.status_source_field)}"
            )
        )

    structured = StructuredMappingCandidate(
        schema_version="enterprise-structured-candidate.v1",
        candidate_kind=profile.target_kind,
        source_identity=record.identity,
        external_version=record.external_version,
        mapping_profile_id=profile.profile_id,
        mapping_version=profile.mapping_version,
        values=values,
        source_spans=spans,
    )
    unstructured = _extract_unstructured(record, profile, payload)
    return EnterpriseMappingResult(
        schema_version="enterprise-mapping-result.v1",
        source_identity=record.identity,
        external_version=record.external_version,
        disposition=MappingDisposition.ACCEPT,
        reason_codes=[MappingReasonCode.MAPPED],
        structured_candidates=[structured],
        unstructured_candidates=unstructured,
    )


def _extract_unstructured(
    record: EnterpriseSourceRecord,
    profile: EnterpriseMappingProfile,
    payload: dict[str, JsonValue],
) -> list[UnstructuredMappingCandidate]:
    candidates: list[UnstructuredMappingCandidate] = []
    for rule in profile.unstructured_rules:
        value = payload.get(rule.source_field)
        if not isinstance(value, str) or not value.strip():
            continue
        text = value
        candidates.append(
            UnstructuredMappingCandidate(
                schema_version="enterprise-unstructured-candidate.v1",
                candidate_kind=rule.candidate_kind,
                source_identity=record.identity,
                external_version=record.external_version,
                mapping_profile_id=profile.profile_id,
                mapping_version=profile.mapping_version,
                extractor_version=rule.extractor_version,
                review_status=CandidateReviewStatus.UNREVIEWED,
                extractor_confidence=None,
                text=text,
                source_span=SourceSpan(
                    json_pointer=f"/payload/{_escape_pointer(rule.source_field)}",
                    start_offset=0,
                    end_offset=len(text),
                ),
            )
        )
    return candidates


def _empty_result(
    record: EnterpriseSourceRecord,
    disposition: MappingDisposition,
    reason: MappingReasonCode,
) -> EnterpriseMappingResult:
    return EnterpriseMappingResult(
        schema_version="enterprise-mapping-result.v1",
        source_identity=record.identity,
        external_version=record.external_version,
        disposition=disposition,
        reason_codes=[reason],
    )


def _identity_key(record: EnterpriseSourceRecord) -> tuple[str, str, str, str]:
    identity = record.identity
    return (
        identity.source_system,
        identity.source_tenant,
        identity.source_object_type,
        identity.external_id,
    )


def _escape_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")
