from pathlib import Path

from fastapi.testclient import TestClient

from soc_ot.api.main import create_app
from soc_ot.application.evaluation_manifest import PARTITIONS
from soc_ot.application.packets import _assert_hidden_free, build_observable_case_packet
from soc_ot.application.repositories import InMemoryCaseRepository
from soc_ot.infrastructure.fixtures import FixtureRepository

ROOT = Path(__file__).resolve().parents[2]


def _repository() -> InMemoryCaseRepository:
    fixtures = FixtureRepository(ROOT / "fixtures")
    repository = InMemoryCaseRepository()
    for case_id in fixtures.case_ids():
        repository.save(
            fixtures.load_observable(case_id),
            event_type="fixture_imported",
            expected_aggregate_version=None,
        )
    return repository


def test_all_eight_cases_validate_and_partition() -> None:
    fixtures = FixtureRepository(ROOT / "fixtures")
    for case_id in fixtures.case_ids():
        fixtures.validate_case(case_id, include_hidden=True)

    assert len(fixtures.case_ids()) == 8
    assert sum(len(items) for items in PARTITIONS.values()) == 8


def test_packet_is_deterministic_and_hidden_free() -> None:
    case = FixtureRepository(ROOT / "fixtures").load_observable("CASE-VR-001")

    first = build_observable_case_packet(case)
    second = build_observable_case_packet(case)

    assert first.packet_hash == second.packet_hash
    serialized = first.model_dump_json()
    assert "hidden_root_causes" not in serialized
    assert "outcome_paths" not in serialized
    assert len(first.selected_role_ids) <= 5
    assert first.hidden_denylist_checked is True
    assert first.allowed_source_ids == sorted(item.evidence_id for item in first.eligible_evidence)


def test_packet_projects_impact_operability_and_future_availability() -> None:
    fixtures = FixtureRepository(ROOT / "fixtures")
    base = build_observable_case_packet(fixtures.load_observable("CASE-VR-001"))
    early = build_observable_case_packet(fixtures.load_observable("CASE-VR-005"))

    architecture = next(
        item for item in base.work_impacts if item.source_work_item_id == "WORK-ARCH-OPTION"
    )
    assert architecture.downstream_work_item_ids == ["WORK-HW-CARRY"]
    assert architecture.impacted_track_ids == ["TRACK-HW"]
    assert all(item.detectability == "observable_now" for item in base.option_operability)
    assert early.eligible_evidence == []
    assert early.claims == []
    assert {item.evidence_id for item in early.evidence_availability} == {
        "EVD-POWER-MODEL",
        "EVD-BW-ESTIMATE",
    }
    assert all(not item.eligible_now for item in early.evidence_availability)
    assert all(item.detectability == "observable_later" for item in early.option_operability)


def test_hidden_denylist_fails_closed() -> None:
    try:
        _assert_hidden_free({"nested": {"outcome_paths": []}})
    except ValueError as error:
        assert "HIDDEN_FIELD_IN_PACKET" in str(error)
    else:
        raise AssertionError("hidden field was accepted")


def test_read_api_is_consumer_shaped() -> None:
    client = TestClient(create_app(_repository()))

    listing = client.get("/api/v1/decision-cases")
    workspace = client.get("/api/v1/decision-cases/CASE-VR-001/workspace")
    packet = client.get("/api/v1/dev/fixtures/CASE-VR-001/observable")

    assert listing.status_code == 200
    assert len(listing.json()) == 8
    assert workspace.json()["title_ko"] == "UHD60 EIS 전력 여유 검토"
    assert "packet_hash" in packet.json()
    assert "hidden_root_causes" not in packet.text
