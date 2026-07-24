import hashlib
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from soc_ot.application.contracts import CONTRACT_MODELS
from soc_ot.application.enterprise_ingestion import EnterpriseSourceRecord
from soc_ot.application.enterprise_mapping import (
    CandidateReviewStatus,
    DirtyFixturePattern,
    EnterpriseDirtyFixtureCorpus,
    EnterpriseMappingProfile,
    EnterpriseMappingRegistry,
    EnterpriseMappingResult,
    MappingDisposition,
    MappingReasonCode,
    StructuredCandidateKind,
    UnstructuredCandidateKind,
    UnstructuredMappingCandidate,
    load_dirty_fixture_corpus,
    load_mapping_registry,
    map_source_records,
)

ROOT = Path(__file__).resolve().parents[2]
ENTERPRISE_FIXTURES = ROOT / "fixtures/enterprise"
REGISTRY_PATH = ENTERPRISE_FIXTURES / "mapping-registry.v1.yaml"
CORPUS_PATH = ENTERPRISE_FIXTURES / "dirty-source-records.v1.yaml"


def _registry() -> EnterpriseMappingRegistry:
    return load_mapping_registry(REGISTRY_PATH)


def _corpus() -> EnterpriseDirtyFixtureCorpus:
    return load_dirty_fixture_corpus(CORPUS_PATH)


def test_registry_and_corpus_are_versioned_and_cover_every_dirty_pattern() -> None:
    registry = _registry()
    corpus = _corpus()

    assert registry.registry_version == "synthetic-enterprise-mapping.1"
    assert len(registry.profiles) == 5
    assert {item.target_kind for item in registry.profiles} == set(StructuredCandidateKind)
    assert {item.pattern for item in corpus.cases} == set(DirtyFixturePattern)
    assert len(corpus.cases) == 10


def test_every_dirty_fixture_has_the_declared_disposition_and_reason() -> None:
    registry = _registry()

    for case in _corpus().cases:
        actual = map_source_records(case.records, registry)
        assert len(actual) == len(case.expected_results), case.case_id
        for result, expected in zip(actual, case.expected_results, strict=True):
            assert result.disposition is expected.disposition, case.case_id
            assert set(expected.required_reason_codes) <= set(result.reason_codes), case.case_id


def test_structured_mapping_preserves_profile_version_and_source_spans() -> None:
    case = next(item for item in _corpus().cases if item.pattern is DirtyFixturePattern.NORMAL)

    result = map_source_records(case.records, _registry())[0]

    assert result.disposition is MappingDisposition.ACCEPT
    candidate = result.structured_candidates[0]
    assert candidate.candidate_kind is StructuredCandidateKind.WORK_ITEM
    assert candidate.mapping_profile_id == "synthetic-work-item"
    assert candidate.mapping_version == "synthetic-work-item.1"
    assert candidate.values == {
        "work_item_id": "WI-NORMAL",
        "title": "Synthetic interface closure",
        "owner": "architecture",
        "status": "IN_PROGRESS",
    }
    assert {item.json_pointer for item in candidate.source_spans} == {
        "/payload/item_id",
        "/payload/title",
        "/payload/owner",
        "/payload/status",
    }


@pytest.mark.parametrize(
    ("source_object_type", "payload", "expected_kind"),
    [
        (
            "project",
            {
                "project_id": "PROJECT-SYNTHETIC",
                "title": "Synthetic architecture project",
                "lifecycle": "presilicon",
            },
            StructuredCandidateKind.PROJECT,
        ),
        (
            "issue",
            {
                "issue_id": "ISSUE-SYNTHETIC",
                "title": "Synthetic observed issue",
                "status": "open",
            },
            StructuredCandidateKind.ISSUE,
        ),
        (
            "event",
            {
                "event_id": "EVENT-SYNTHETIC",
                "event_type": "evidence-change",
                "summary": "Synthetic evidence arrived",
            },
            StructuredCandidateKind.EVENT,
        ),
    ],
)
def test_registry_maps_project_issue_and_event_candidates(
    source_object_type: str,
    payload: dict[str, str],
    expected_kind: StructuredCandidateKind,
) -> None:
    source = _corpus().cases[0].records[0].model_dump(mode="json")
    source["source_object_type"] = source_object_type
    source["external_id"] = f"EXT-{source_object_type}"
    source["external_version"] = "1"
    source["content_hash"] = {
        "project": "8" * 64,
        "issue": "9" * 64,
        "event": "0" * 64,
    }[source_object_type]
    source["source_url"] = f"https://work.invalid/{source_object_type}/EXT"
    source["payload"] = payload

    result = map_source_records(
        [EnterpriseSourceRecord.model_validate(source)],
        _registry(),
    )[0]

    assert result.disposition is MappingDisposition.ACCEPT
    assert result.structured_candidates[0].candidate_kind is expected_kind


def test_unstructured_text_stays_unreviewed_candidate_with_exact_provenance() -> None:
    case = next(
        item
        for item in _corpus().cases
        if item.pattern is DirtyFixturePattern.LATE_EVIDENCE
    )

    result = map_source_records(case.records, _registry())[0]

    assert result.disposition is MappingDisposition.ACCEPT
    assert MappingReasonCode.LATE_ARRIVAL in result.reason_codes
    assert {item.candidate_kind for item in result.unstructured_candidates} == {
        UnstructuredCandidateKind.CLAIM,
        UnstructuredCandidateKind.RISK,
        UnstructuredCandidateKind.ASSUMPTION,
    }
    for candidate in result.unstructured_candidates:
        assert candidate.review_status is CandidateReviewStatus.UNREVIEWED
        assert candidate.mapping_version == "synthetic-knowledge-page.1"
        assert candidate.extractor_version == "synthetic-text-span.1"
        assert candidate.extractor_confidence is None
        assert candidate.source_span.json_pointer.startswith("/payload/")
        assert candidate.source_span.start_offset == 0
        assert candidate.source_span.end_offset == len(candidate.text)
        assert "fact" not in candidate.model_dump_json().lower()


def test_unstructured_candidate_rejects_missing_provenance_and_false_review_state() -> None:
    case = next(
        item
        for item in _corpus().cases
        if item.pattern is DirtyFixturePattern.LATE_EVIDENCE
    )
    candidate = map_source_records(case.records, _registry())[0].unstructured_candidates[0]
    payload = candidate.model_dump(mode="json")
    payload.pop("extractor_version")
    with pytest.raises(ValidationError):
        UnstructuredMappingCandidate.model_validate(payload)

    payload = candidate.model_dump(mode="json")
    payload["source_span"] = {"json_pointer": "/payload/claim_text"}
    with pytest.raises(ValidationError, match="requires source span offsets"):
        UnstructuredMappingCandidate.model_validate(payload)

    payload = candidate.model_dump(mode="json")
    payload["review_status"] = "FACT"
    with pytest.raises(ValidationError):
        UnstructuredMappingCandidate.model_validate(payload)


def test_deleted_and_restricted_records_create_metadata_only_event_candidates() -> None:
    corpus = _corpus()
    cases = [
        item
        for item in corpus.cases
        if item.pattern
        in {DirtyFixturePattern.DELETED_OBJECT, DirtyFixturePattern.RESTRICTED_OBJECT}
    ]

    for case in cases:
        result = map_source_records(case.records, _registry())[0]
        assert result.disposition is MappingDisposition.ACCEPT
        assert result.unstructured_candidates == []
        assert len(result.structured_candidates) == 1
        candidate = result.structured_candidates[0]
        assert candidate.candidate_kind is StructuredCandidateKind.EVENT
        assert set(candidate.values) == {"deletion_state"}
        assert candidate.source_spans[0].json_pointer == "/deletion_state"


def test_unknown_source_type_is_rejected_without_candidates() -> None:
    payload = _corpus().cases[0].records[0].model_dump(mode="json")
    payload["source_object_type"] = "unknown-synthetic-type"
    record = EnterpriseSourceRecord.model_validate(payload)

    result = map_source_records([record], _registry())[0]

    assert result.disposition is MappingDisposition.REJECT
    assert result.reason_codes == [MappingReasonCode.PROFILE_NOT_FOUND]
    assert result.structured_candidates == []
    assert result.unstructured_candidates == []


def test_mapping_is_deterministic_and_does_not_mutate_source_records() -> None:
    case = next(item for item in _corpus().cases if item.pattern is DirtyFixturePattern.MOVED_PAGE)
    before = [item.model_dump_json() for item in case.records]

    first = map_source_records(case.records, _registry())
    second = map_source_records(case.records, _registry())

    assert first == second
    assert [item.model_dump_json() for item in case.records] == before


def test_registry_rejects_ambiguous_or_incomplete_profiles() -> None:
    payload = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    payload["profiles"].append(payload["profiles"][0])
    with pytest.raises(ValidationError, match="profile_id must be unique"):
        EnterpriseMappingRegistry.model_validate(payload)

    profile = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))["profiles"][0]
    profile["status_map"] = {}
    with pytest.raises(ValidationError, match="status mapping requires"):
        EnterpriseMappingProfile.model_validate(profile)

    profile = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))["profiles"][1]
    profile["status_map"]["doing"] = "NOT_CANONICAL"
    with pytest.raises(ValidationError, match="non-canonical target"):
        EnterpriseMappingProfile.model_validate(profile)


def test_mapping_result_cannot_smuggle_candidates_through_non_accept_disposition() -> None:
    accepted = map_source_records([_corpus().cases[0].records[0]], _registry())[0]
    payload = accepted.model_dump(mode="json")
    payload["disposition"] = "QUARANTINE"

    with pytest.raises(ValidationError, match="cannot carry candidates"):
        EnterpriseMappingResult.model_validate(payload)


def test_enterprise_fixtures_are_synthetic_and_hash_pinned() -> None:
    combined = (
        REGISTRY_PATH.read_text(encoding="utf-8")
        + CORPUS_PATH.read_text(encoding="utf-8")
    ).lower()
    assert "jira" not in combined
    assert "confluence" not in combined
    assert "customfield_" not in combined

    manifest = yaml.safe_load(
        (ENTERPRISE_FIXTURES / "manifest.yaml").read_text(encoding="utf-8")
    )
    assert manifest["schema_version"] == "enterprise-fixture-manifest.v1"
    for artifact in manifest["artifacts"]:
        actual = hashlib.sha256(
            (ENTERPRISE_FIXTURES / artifact["path"]).read_bytes()
        ).hexdigest()
        assert actual == artifact["sha256"]


def test_ent_b_contracts_are_registered_and_generated() -> None:
    assert CONTRACT_MODELS["enterprise-mapping-registry.v1"] is EnterpriseMappingRegistry
    assert CONTRACT_MODELS["enterprise-mapping-result.v1"] is EnterpriseMappingResult
    assert CONTRACT_MODELS["enterprise-dirty-fixture-corpus.v1"] is EnterpriseDirtyFixtureCorpus
    for name in (
        "enterprise-mapping-registry.v1",
        "enterprise-mapping-result.v1",
        "enterprise-dirty-fixture-corpus.v1",
    ):
        assert (ROOT / f"contracts/generated/{name}.schema.json").exists()
