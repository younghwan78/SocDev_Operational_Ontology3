from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from soc_ot.api.main import create_app
from soc_ot.application.contracts import CONTRACT_MODELS
from soc_ot.application.projections import (
    DecisionListItemProjection,
    build_decision_list_item,
    sort_decision_list_items,
)
from soc_ot.application.repositories import InMemoryCaseRepository, StoredCase
from soc_ot.domain.models import DecisionCaseStatus
from soc_ot.infrastructure.fixtures import FixtureRepository

ROOT = Path(__file__).resolve().parents[2]


def _fixtures() -> FixtureRepository:
    return FixtureRepository(ROOT / "fixtures")


def _repository() -> InMemoryCaseRepository:
    repository = InMemoryCaseRepository()
    fixtures = _fixtures()
    for case_id in fixtures.case_ids():
        repository.save(
            fixtures.load_observable(case_id),
            event_type="fixture_imported",
            expected_aggregate_version=None,
        )
    return repository


def test_backend_orders_decisions_by_group_deadline_and_impact() -> None:
    fixtures = _fixtures()
    items = sort_decision_list_items(
        [
            build_decision_list_item(StoredCase(fixtures.load_observable(case_id), 1))
            for case_id in fixtures.case_ids()
        ]
    )

    assert [item.case_id for item in items] == [
        "CASE-HO-001",
        "CASE-VR-004",
        "CASE-HO-003",
        "CASE-VR-001",
        "CASE-VR-003",
        "CASE-VR-002",
        "CASE-HO-002",
        "CASE-VR-005",
    ]
    assert items[0].deadline.attention == "OVERDUE"
    assert items[1].deadline.attention == "DUE_NOW"
    assert all(item.group == "ACTION_REQUIRED" for item in items)


def test_list_item_explains_deadline_blocker_and_next_action_in_korean() -> None:
    case = _fixtures().load_observable("CASE-VR-001")
    item = build_decision_list_item(StoredCase(case=case, aggregate_version=1))
    labels = yaml.safe_load(
        (ROOT / "fixtures/dictionaries/labels.ko.yaml").read_text(encoding="utf-8")
    )

    assert item.deadline.label_ko == "1 Step 남음"
    assert item.current_state_ko == "결정 필요"
    assert "Architecture Freeze까지 1 Step" in item.why_now_ko
    assert "EIS 구현 option 결정" in item.why_now_ko
    assert item.blocker.critical_track_name == "Architecture"
    assert item.blocker.downstream_work_item_titles == ["HW carry-over 가능성 검토"]
    assert item.blocker.impacted_milestone_titles == ["RTL Freeze"]
    assert item.next_action_ko == "결정 검토"
    assert labels["DecisionListGroup"][item.group] == item.group_label_ko
    assert labels["DecisionListAction"][item.next_action] == item.next_action_ko
    assert "WORK-" not in item.why_now_ko
    assert "TRACK-" not in item.blocker.summary_ko


def test_list_group_changes_for_actioning_and_closed_cases() -> None:
    base = _fixtures().load_observable("CASE-VR-001")
    actioning = base.model_copy(update={"status": DecisionCaseStatus.ACTIONING})
    closed = base.model_copy(update={"status": DecisionCaseStatus.CLOSED})

    actioning_item = build_decision_list_item(StoredCase(actioning, 1))
    closed_item = build_decision_list_item(StoredCase(closed, 1))

    assert actioning_item.group == "ACTION_AND_OBSERVATION"
    assert actioning_item.next_action_ko == "실행 상태 보기"
    assert closed_item.group == "COMPLETED"
    assert closed_item.next_action_ko == "학습 요약 보기"


def test_decision_collection_api_returns_consumer_shaped_list_items() -> None:
    client = TestClient(create_app(_repository()))

    response = client.get("/api/v1/decision-cases")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["projection_schema_version"] == "decision-list-item.v1"
    assert payload[0]["deadline"]["attention"] == "OVERDUE"
    assert "why_now_ko" in payload[0]
    assert "tracks" not in payload[0]
    assert "evidence" not in payload[0]


def test_decision_list_contract_is_registered_for_generation() -> None:
    assert CONTRACT_MODELS["decision-list-item.v1"] is DecisionListItemProjection
