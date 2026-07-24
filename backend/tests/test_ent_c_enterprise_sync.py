import hashlib
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from soc_ot.application.contracts import CONTRACT_MODELS
from soc_ot.application.enterprise_mapping import MappingReasonCode, load_mapping_registry
from soc_ot.application.enterprise_sync import (
    EnterpriseSyncCheckpoint,
    EnterpriseSyncDisposition,
    EnterpriseSyncFixtureCorpus,
    EnterpriseSyncMode,
    EnterpriseSyncReasonCode,
    EnterpriseSyncResult,
    EnterpriseSyncStatus,
    load_sync_fixture_corpus,
    reconcile_enterprise_pages,
)

ROOT = Path(__file__).resolve().parents[2]
ENTERPRISE_FIXTURES = ROOT / "fixtures/enterprise"
REGISTRY_PATH = ENTERPRISE_FIXTURES / "mapping-registry.v1.yaml"
SYNC_PATH = ENTERPRISE_FIXTURES / "sync-pages.v1.yaml"


def _corpus() -> EnterpriseSyncFixtureCorpus:
    return load_sync_fixture_corpus(SYNC_PATH)


def _run_full(
    *,
    failures: dict[int, int] | None = None,
) -> EnterpriseSyncResult:
    corpus = _corpus()
    return reconcile_enterprise_pages(
        pages=corpus.pages,
        registry=load_mapping_registry(REGISTRY_PATH),
        policy=corpus.policy,
        mode=EnterpriseSyncMode.FULL,
        transient_failures_before_success=failures,
    )


def _state(result: EnterpriseSyncResult, external_id: str):
    return next(
        item
        for item in result.checkpoint.source_states
        if item.source_identity.external_id == external_id
    )


def test_full_sync_tracks_cursor_page_token_and_deterministic_state() -> None:
    corpus = _corpus()
    result = _run_full(failures=corpus.transient_failures_before_success)

    assert result.status is EnterpriseSyncStatus.COMPLETED
    assert result.processed_page_count == 4
    assert result.processed_record_count == 10
    assert result.checkpoint.next_page_index == 4
    assert result.checkpoint.next_page_token is None
    assert result.checkpoint.cursor_value == "synthetic-cursor-400"
    assert [item.source_identity.external_id for item in result.checkpoint.source_states] == [
        "PAGE-LATE",
        "EVENT-EARLIER",
        "EVENT-LATER",
        "PROJECT-SYNC",
        "WI-SYNC",
    ]
    assert [
        item.external_id for item in result.checkpoint.ordered_event_identities
    ] == ["EVENT-EARLIER", "EVENT-LATER"]
    assert [item.retry_scheduled_after_seconds for item in result.checkpoint.retry_entries] == [
        1,
        2,
    ]


def test_interrupted_incremental_resume_equals_single_incremental_run() -> None:
    corpus = _corpus()
    registry = load_mapping_registry(REGISTRY_PATH)
    kwargs = {
        "pages": corpus.pages,
        "registry": registry,
        "policy": corpus.policy,
        "mode": EnterpriseSyncMode.INCREMENTAL,
        "transient_failures_before_success": corpus.transient_failures_before_success,
    }
    one_shot = reconcile_enterprise_pages(**kwargs)
    first = reconcile_enterprise_pages(**kwargs, max_pages=2)
    resumed = reconcile_enterprise_pages(**kwargs, checkpoint=first.checkpoint)

    assert first.status is EnterpriseSyncStatus.PAUSED
    assert first.checkpoint.next_page_index == 2
    assert first.checkpoint.next_page_token == "synthetic-page-2"
    assert resumed.status is EnterpriseSyncStatus.COMPLETED
    assert resumed.checkpoint == one_shot.checkpoint

    full = _run_full(failures=corpus.transient_failures_before_success)
    assert full.checkpoint.source_states == resumed.checkpoint.source_states
    assert full.checkpoint.ordered_event_identities == resumed.checkpoint.ordered_event_identities
    assert full.checkpoint.audit_entries == resumed.checkpoint.audit_entries


def test_completed_checkpoint_reprocessing_is_an_exact_noop() -> None:
    corpus = _corpus()
    first = _run_full(failures=corpus.transient_failures_before_success)
    second = reconcile_enterprise_pages(
        pages=corpus.pages,
        registry=load_mapping_registry(REGISTRY_PATH),
        policy=corpus.policy,
        mode=EnterpriseSyncMode.FULL,
        checkpoint=first.checkpoint,
        transient_failures_before_success=corpus.transient_failures_before_success,
    )

    assert second.processed_page_count == 0
    assert second.processed_record_count == 0
    assert second.checkpoint == first.checkpoint
    assert _state(second, "WI-SYNC").mapping_revision == 3
    assert len(second.checkpoint.audit_entries) == 10


def test_duplicate_does_not_inflate_revision_and_conflict_is_quarantined() -> None:
    result = _run_full()
    wi_audits = [
        item
        for item in result.checkpoint.audit_entries
        if item.source_identity.external_id == "WI-SYNC"
    ]

    assert wi_audits[0].mapping_revision == 1
    assert wi_audits[1].disposition is EnterpriseSyncDisposition.NO_CHANGE
    assert wi_audits[1].reason_code is EnterpriseSyncReasonCode.CONTENT_UNCHANGED
    assert wi_audits[1].mapping_revision == 1
    assert MappingReasonCode.DUPLICATE_SOURCE_VERSION in wi_audits[1].mapping_reason_codes
    assert wi_audits[2].mapping_revision == 2

    payload = _corpus().pages[1].records[0].model_copy(
        update={"content_hash": "8" * 64}
    )
    pages = [page.model_copy(deep=True) for page in _corpus().pages[:2]]
    pages[1] = pages[1].model_copy(update={"records": [payload]})
    result = reconcile_enterprise_pages(
        pages=pages,
        registry=load_mapping_registry(REGISTRY_PATH),
        policy=_corpus().policy,
        mode=EnterpriseSyncMode.FULL,
    )
    conflict = result.checkpoint.audit_entries[-1]
    assert conflict.disposition is EnterpriseSyncDisposition.QUARANTINED
    assert conflict.mapping_reason_codes == [MappingReasonCode.SOURCE_VERSION_CONFLICT]
    assert _state(result, "WI-SYNC").mapping_revision == 1


def test_tombstone_and_access_restriction_dominate_stale_active_content() -> None:
    result = _run_full()
    work_item = _state(result, "WI-SYNC")
    page = _state(result, "PAGE-LATE")

    assert work_item.deletion_state.value == "DELETED"
    assert work_item.mapping_revision == 3
    assert work_item.current_mapping_result.structured_candidates[0].values == {
        "deletion_state": "DELETED"
    }
    stale = next(
        item
        for item in result.checkpoint.audit_entries
        if item.external_version == "2-stale"
    )
    assert stale.disposition is EnterpriseSyncDisposition.QUARANTINED
    assert stale.reason_code is EnterpriseSyncReasonCode.STALE_SOURCE_UPDATE
    assert stale.mapping_revision == 3

    assert page.deletion_state.value == "RESTRICTED"
    assert page.current_mapping_result.unstructured_candidates == []
    assert page.current_mapping_result.structured_candidates[0].values == {
        "deletion_state": "RESTRICTED"
    }


def test_late_arrival_is_applied_with_explicit_mapping_reason() -> None:
    result = _run_full()
    audit = next(
        item
        for item in result.checkpoint.audit_entries
        if item.source_identity.external_id == "PAGE-LATE" and item.external_version == "1"
    )

    assert audit.disposition is EnterpriseSyncDisposition.APPLIED
    assert audit.reason_code is EnterpriseSyncReasonCode.MAPPING_APPLIED
    assert MappingReasonCode.LATE_ARRIVAL in audit.mapping_reason_codes


def test_retry_is_bounded_and_failure_checkpoint_is_resumable() -> None:
    corpus = _corpus()
    failed = _run_full(failures={1: 3})

    assert failed.status is EnterpriseSyncStatus.FAILED
    assert failed.failed_page_index == 1
    assert failed.checkpoint.next_page_index == 1
    assert failed.checkpoint.next_page_token == "synthetic-page-1"
    assert [item.exhausted for item in failed.checkpoint.retry_entries] == [
        False,
        False,
        True,
    ]
    assert _state(failed, "WI-SYNC").mapping_revision == 1

    resumed = reconcile_enterprise_pages(
        pages=corpus.pages,
        registry=load_mapping_registry(REGISTRY_PATH),
        policy=corpus.policy,
        mode=EnterpriseSyncMode.FULL,
        checkpoint=failed.checkpoint,
    )
    assert resumed.status is EnterpriseSyncStatus.COMPLETED
    assert _state(resumed, "WI-SYNC").mapping_revision == 3


def test_sync_audit_is_deterministic_and_unique() -> None:
    first = _run_full()
    second = _run_full()

    assert first.checkpoint.audit_entries == second.checkpoint.audit_entries
    audit_ids = [item.audit_id for item in first.checkpoint.audit_entries]
    assert len(audit_ids) == len(set(audit_ids))


def test_sync_contracts_reject_invalid_checkpoint_policy_and_pages() -> None:
    corpus_payload = yaml.safe_load(SYNC_PATH.read_text(encoding="utf-8"))
    corpus_payload["policy"]["retry_backoff_seconds"] = [1]
    with pytest.raises(ValidationError, match="cover every retry"):
        EnterpriseSyncFixtureCorpus.model_validate(corpus_payload)

    corpus_payload = yaml.safe_load(SYNC_PATH.read_text(encoding="utf-8"))
    corpus_payload["pages"][1]["page_index"] = 4
    with pytest.raises(ValidationError, match="contiguous and ordered"):
        EnterpriseSyncFixtureCorpus.model_validate(corpus_payload)

    result = _run_full()
    checkpoint_payload = result.checkpoint.model_dump(mode="json")
    checkpoint_payload["source_states"].append(checkpoint_payload["source_states"][0])
    with pytest.raises(ValidationError, match="identity must be unique"):
        EnterpriseSyncCheckpoint.model_validate(checkpoint_payload)

    checkpoint_payload = result.checkpoint.model_dump(mode="json")
    checkpoint_payload["ordered_event_identities"].reverse()
    with pytest.raises(ValidationError, match="event order must match"):
        EnterpriseSyncCheckpoint.model_validate(checkpoint_payload)

    paused = reconcile_enterprise_pages(
        pages=_corpus().pages,
        registry=load_mapping_registry(REGISTRY_PATH),
        policy=_corpus().policy,
        mode=EnterpriseSyncMode.INCREMENTAL,
        max_pages=1,
    )
    corrupted = paused.checkpoint.model_copy(
        update={"next_page_token": "wrong-page-token"}
    )
    with pytest.raises(ValueError, match="page token does not match"):
        reconcile_enterprise_pages(
            pages=_corpus().pages,
            registry=load_mapping_registry(REGISTRY_PATH),
            policy=_corpus().policy,
            mode=EnterpriseSyncMode.INCREMENTAL,
            checkpoint=corrupted,
        )


def test_sync_fixture_is_synthetic_hash_pinned_and_contracts_are_generated() -> None:
    text = SYNC_PATH.read_text(encoding="utf-8").lower()
    assert "jira" not in text
    assert "confluence" not in text
    assert "customfield_" not in text

    manifest = yaml.safe_load(
        (ENTERPRISE_FIXTURES / "manifest.yaml").read_text(encoding="utf-8")
    )
    sync_artifact = next(
        item for item in manifest["artifacts"] if item["path"] == SYNC_PATH.name
    )
    assert hashlib.sha256(SYNC_PATH.read_bytes()).hexdigest() == sync_artifact["sha256"]

    assert CONTRACT_MODELS["enterprise-sync-checkpoint.v1"] is EnterpriseSyncCheckpoint
    assert CONTRACT_MODELS["enterprise-sync-result.v1"] is EnterpriseSyncResult
    assert (
        CONTRACT_MODELS["enterprise-sync-fixture-corpus.v1"]
        is EnterpriseSyncFixtureCorpus
    )
    for name in (
        "enterprise-sync-checkpoint.v1",
        "enterprise-sync-result.v1",
        "enterprise-sync-fixture-corpus.v1",
    ):
        assert (ROOT / f"contracts/generated/{name}.schema.json").exists()
