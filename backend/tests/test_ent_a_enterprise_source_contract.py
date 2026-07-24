from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from soc_ot.application.contracts import CONTRACT_MODELS
from soc_ot.application.enterprise_ingestion import (
    EnterpriseSourceIdentity,
    EnterpriseSourceRecord,
    SourceDataClassification,
    SourceDeletionState,
)
from soc_ot.application.ports import IngestionSink, SourceReader

ROOT = Path(__file__).resolve().parents[2]


def _payload() -> dict[str, object]:
    return {
        "schema_version": "enterprise-source-record.v1",
        "source_system": "synthetic-work-tracker",
        "source_tenant": "lab-a",
        "source_object_type": "work-item",
        "external_id": "EXT-42",
        "external_version": "7",
        "effective_at": "2026-07-21T09:00:00+09:00",
        "observed_at": "2026-07-21T10:30:00+09:00",
        "source_updated_at": "2026-07-21T10:20:00+09:00",
        "ingested_at": "2026-07-21T10:31:00+09:00",
        "content_hash": "a" * 64,
        "source_url": "https://source.invalid/items/EXT-42",
        "deletion_state": "ACTIVE",
        "source_acl_ref": "acl-ref:project-v",
        "classification": "INTERNAL",
        "payload": {"title": "Synthetic interface review", "status": "open"},
    }


def test_enterprise_source_record_preserves_identity_time_and_access_metadata() -> None:
    record = EnterpriseSourceRecord.model_validate(_payload())

    assert record.identity == EnterpriseSourceIdentity(
        source_system="synthetic-work-tracker",
        source_tenant="lab-a",
        source_object_type="work-item",
        external_id="EXT-42",
    )
    assert record.effective_at != record.observed_at
    assert record.source_updated_at != record.ingested_at
    assert record.classification is SourceDataClassification.INTERNAL
    assert record.deletion_state is SourceDeletionState.ACTIVE


def test_rename_update_and_delete_keep_the_stable_external_identity() -> None:
    active = EnterpriseSourceRecord.model_validate(_payload())
    updated_payload = deepcopy(_payload())
    updated_payload["external_version"] = "8"
    updated_payload["content_hash"] = "b" * 64
    updated_payload["source_url"] = "https://source.invalid/items/renamed-EXT-42"
    updated_payload["payload"] = {"title": "Renamed synthetic review", "status": "closed"}
    updated = EnterpriseSourceRecord.model_validate(updated_payload)
    deleted_payload = deepcopy(updated_payload)
    deleted_payload["external_version"] = "9"
    deleted_payload["content_hash"] = "c" * 64
    deleted_payload["deletion_state"] = "DELETED"
    deleted_payload["payload"] = None
    deleted = EnterpriseSourceRecord.model_validate(deleted_payload)

    assert active.identity == updated.identity == deleted.identity
    assert active.external_version != updated.external_version != deleted.external_version


@pytest.mark.parametrize(
    "field",
    ["effective_at", "observed_at", "source_updated_at", "ingested_at"],
)
def test_enterprise_source_record_rejects_naive_time(field: str) -> None:
    payload = _payload()
    payload[field] = datetime(2026, 7, 21, 10, 30)

    with pytest.raises(ValidationError, match="must include a timezone"):
        EnterpriseSourceRecord.model_validate(payload)


@pytest.mark.parametrize("field", ["source_acl_ref", "classification"])
def test_enterprise_source_record_fails_closed_without_access_metadata(field: str) -> None:
    payload = _payload()
    payload.pop(field)

    with pytest.raises(ValidationError):
        EnterpriseSourceRecord.model_validate(payload)


@pytest.mark.parametrize("state", ["DELETED", "RESTRICTED"])
def test_inactive_source_record_cannot_carry_stale_or_restricted_payload(state: str) -> None:
    payload = _payload()
    payload["deletion_state"] = state

    with pytest.raises(ValidationError, match="cannot carry payload"):
        EnterpriseSourceRecord.model_validate(payload)


def test_active_source_record_requires_payload() -> None:
    payload = _payload()
    payload["payload"] = None

    with pytest.raises(ValidationError, match="active source record requires payload"):
        EnterpriseSourceRecord.model_validate(payload)


def test_hash_url_and_unknown_fields_are_strict() -> None:
    uppercase_hash = _payload()
    uppercase_hash["content_hash"] = "A" * 64
    with pytest.raises(ValidationError):
        EnterpriseSourceRecord.model_validate(uppercase_hash)

    credential_url = _payload()
    credential_url["source_url"] = "https://reader:secret@source.invalid/items/EXT-42"
    with pytest.raises(ValidationError, match="cannot contain embedded credentials"):
        EnterpriseSourceRecord.model_validate(credential_url)

    extra_field = _payload()
    extra_field["company_project_key"] = "MUST-NOT-BE-CANONICAL"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EnterpriseSourceRecord.model_validate(extra_field)

    non_json_payload = _payload()
    non_json_payload["payload"] = {"invalid": object()}
    with pytest.raises(ValidationError):
        EnterpriseSourceRecord.model_validate(non_json_payload)


class _SyntheticReader:
    def __init__(self, record: EnterpriseSourceRecord) -> None:
        self.record = record

    def read(self, identity: EnterpriseSourceIdentity) -> EnterpriseSourceRecord | None:
        return self.record if identity == self.record.identity else None


class _MemorySink:
    def __init__(self) -> None:
        self.records: list[EnterpriseSourceRecord] = []

    def write(self, record: EnterpriseSourceRecord) -> None:
        self.records.append(record)


def test_source_ports_depend_only_on_the_validated_envelope() -> None:
    record = EnterpriseSourceRecord.model_validate(_payload())
    reader = _SyntheticReader(record)
    sink = _MemorySink()

    assert isinstance(reader, SourceReader)
    assert isinstance(sink, IngestionSink)
    loaded = reader.read(record.identity)
    assert loaded is not None
    sink.write(loaded)
    assert sink.records == [record]


def test_enterprise_source_contract_is_registered_and_generated() -> None:
    assert CONTRACT_MODELS["enterprise-source-record.v1"] is EnterpriseSourceRecord
    assert (ROOT / "contracts/generated/enterprise-source-record.v1.schema.json").exists()


def test_time_fields_do_not_assume_source_event_ordering() -> None:
    payload = _payload()
    payload["effective_at"] = "2026-08-01T09:00:00+09:00"
    payload["observed_at"] = "2026-07-21T10:30:00+09:00"

    record = EnterpriseSourceRecord.model_validate(payload)

    assert record.observed_at < record.effective_at
    assert record.ingested_at.tzinfo is not None
