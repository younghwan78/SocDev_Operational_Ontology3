from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from soc_ot.api.main import create_app
from soc_ot.application.development_twin import (
    build_development_timeline,
    reconstruct_case_at_step,
)
from soc_ot.application.packets import build_observable_case_packet
from soc_ot.application.repositories import InMemoryCaseRepository, StoredCase
from soc_ot.domain.models import ObservableCase
from soc_ot.infrastructure.fixtures import FixtureRepository

ROOT = Path(__file__).resolve().parents[2]


def _eventful_case() -> ObservableCase:
    payload = FixtureRepository(ROOT / "fixtures").load_observable(
        "CASE-VR-001"
    ).model_dump(mode="json")
    payload["development_events"] = [
        {
            "event_id": "DEV-009-WORK-STARTED",
            "event_type": "WORK_PROGRESS",
            "effective_at_step": 9,
            "observed_at_step": 9,
            "summary": "Architecture option 검토를 시작했다.",
            "cause": "SW feature flag prototype이 준비되었다.",
            "work_item_changes": [
                {
                    "work_item_id": "WORK-ARCH-OPTION",
                    "before": {
                        "status": "READY",
                        "blocker": None,
                        "planned_at_step": 10,
                        "dependency_ids": [],
                    },
                    "after": {
                        "status": "IN_PROGRESS",
                        "blocker": None,
                        "planned_at_step": 10,
                        "dependency_ids": [],
                    },
                }
            ],
        },
        {
            "event_id": "DEV-010-BLOCKER-RAISED",
            "event_type": "BLOCKER_CHANGE",
            "effective_at_step": 10,
            "observed_at_step": 10,
            "summary": "DDR bandwidth 실측 부재가 blocker가 되었다.",
            "cause": "Architecture freeze 전에 측정 slot을 확보하지 못했다.",
            "work_item_changes": [
                {
                    "work_item_id": "WORK-ARCH-OPTION",
                    "before": {
                        "status": "IN_PROGRESS",
                        "blocker": None,
                        "planned_at_step": 10,
                        "dependency_ids": [],
                    },
                    "after": {
                        "status": "IN_PROGRESS",
                        "blocker": "DDR bandwidth 실측 없음",
                        "planned_at_step": 10,
                        "dependency_ids": [],
                    },
                }
            ],
            "impacted_milestone_ids": ["M2-ARCH-FREEZE", "M3-RTL-FREEZE"],
        },
        {
            "event_id": "DEV-011-EVIDENCE-AVAILABLE",
            "event_type": "EVIDENCE_CHANGE",
            "effective_at_step": 10,
            "observed_at_step": 11,
            "summary": "DDR 분석 추정 결과를 검토 가능 상태로 공개했다.",
            "cause": "분석팀이 중간 추정 결과를 조기 완료했다.",
            "evidence_changes": [
                {
                    "evidence_id": "EVD-BW-ESTIMATE",
                    "before": {"available_at_step": 15},
                    "after": {"available_at_step": 11},
                }
            ],
        },
        {
            "event_id": "DEV-012-FREEZE-ADVANCED",
            "event_type": "PLAN_CHANGE",
            "effective_at_step": 12,
            "observed_at_step": 12,
            "summary": "Architecture freeze가 Step 13으로 앞당겨졌다.",
            "cause": "상위 통합 일정이 한 step 당겨졌다.",
            "milestone_changes": [
                {
                    "milestone_id": "M2-ARCH-FREEZE",
                    "before": {"planned_at_step": 14},
                    "after": {"planned_at_step": 13},
                }
            ],
            "impacted_milestone_ids": ["M2-ARCH-FREEZE"],
        },
    ]
    return ObservableCase.model_validate(payload)


def test_same_event_history_reconstructs_multiple_development_steps() -> None:
    case = _eventful_case()

    step_8 = reconstruct_case_at_step(case, 8)
    step_9 = reconstruct_case_at_step(case, 9)
    step_10 = reconstruct_case_at_step(case, 10)
    step_12 = reconstruct_case_at_step(case, 12)

    architecture_8 = next(
        item for item in step_8.work_items if item.work_item_id == "WORK-ARCH-OPTION"
    )
    architecture_9 = next(
        item for item in step_9.work_items if item.work_item_id == "WORK-ARCH-OPTION"
    )
    architecture_10 = next(
        item for item in step_10.work_items if item.work_item_id == "WORK-ARCH-OPTION"
    )
    assert architecture_8.status == "READY"
    assert architecture_9.status == "IN_PROGRESS"
    assert architecture_9.blocker is None
    assert architecture_10.blocker == "DDR bandwidth 실측 없음"
    assert step_8.milestones[0].planned_at_step == 14
    assert step_12.milestones[0].planned_at_step == 13


def test_historical_packet_excludes_not_yet_observed_evidence() -> None:
    packet = build_observable_case_packet(_eventful_case(), at_step=10)

    assert "EVD-BW-ESTIMATE" not in {
        item.evidence_id for item in packet.eligible_evidence
    }
    assert "CLM-BW-RISK" not in {item.claim_id for item in packet.claims}
    assert {item.event_id for item in packet.development_events} == {
        "DEV-009-WORK-STARTED",
        "DEV-010-BLOCKER-RAISED",
    }


def test_blocker_propagates_to_downstream_work_and_milestone() -> None:
    timeline = build_development_timeline(
        StoredCase(case=_eventful_case(), aggregate_version=1), at_step=10
    )
    impact = next(
        item
        for item in timeline.blocker_propagations
        if item.source_work_item_id == "WORK-ARCH-OPTION"
    )

    assert impact.downstream_work_item_ids == ["WORK-HW-CARRY"]
    assert impact.source_work_item_title == "EIS 구현 option 결정"
    assert impact.downstream_work_item_titles == ["HW carry-over 가능성 검토"]
    assert impact.impacted_track_ids == ["TRACK-HW"]
    assert impact.impacted_milestone_ids == ["M3-RTL-FREEZE"]
    assert impact.impacted_milestone_titles == ["RTL Freeze"]
    assert impact.reaches_decision_deadline is True


def test_timeline_api_returns_reconstructed_projection() -> None:
    repository = InMemoryCaseRepository()
    repository.save(
        _eventful_case(),
        event_type="fixture_imported",
        expected_aggregate_version=None,
    )
    client = TestClient(create_app(repository))

    response = client.get(
        "/api/v1/decision-cases/CASE-VR-001/timeline", params={"at_step": 9}
    )
    invalid = client.get(
        "/api/v1/decision-cases/CASE-VR-001/timeline", params={"at_step": 13}
    )

    assert response.status_code == 200
    assert response.json()["projection_schema_version"] == "development-timeline.v1"
    assert response.json()["reconstructed_at_step"] == 9
    assert len(response.json()["events"]) == 1
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "DEVELOPMENT_STEP_OUT_OF_RANGE"


def test_event_chain_must_match_current_case_state() -> None:
    payload = _eventful_case().model_dump(mode="json")
    payload["development_events"][-1]["milestone_changes"][0]["after"] = {
        "planned_at_step": 15
    }

    with pytest.raises(ValidationError, match="does not match current state"):
        ObservableCase.model_validate(payload)


def test_development_corpus_is_independent_and_reconstructable() -> None:
    repository = FixtureRepository(ROOT / "fixtures")

    assert repository.development_case_ids() == [
        "CASE-DT-001",
        "CASE-DT-002",
        "CASE-DT-003",
        "CASE-DT-004",
    ]
    for case_id in repository.development_case_ids():
        case = repository.validate_case(case_id)
        observed_steps = sorted({event.observed_at_step for event in case.development_events})
        assert len(observed_steps) >= 3
        checkpoints = (
            observed_steps[0] - 1,
            observed_steps[len(observed_steps) // 2],
            case.current_step,
        )
        for step in checkpoints:
            reconstructed = reconstruct_case_at_step(case, step)
            assert reconstructed.current_step == step
        source = ROOT / "fixtures" / "cases" / "development" / f"{case_id}.yaml"
        assert "extends:" not in source.read_text(encoding="utf-8")


def test_development_corpus_covers_required_real_work_structures() -> None:
    repository = FixtureRepository(ROOT / "fixtures")
    event_types = {
        event.event_type
        for case_id in repository.development_case_ids()
        for event in repository.load_observable(case_id).development_events
    }

    assert {
        "INTERFACE_CHANGE",
        "REWORK",
        "EVIDENCE_CHANGE",
        "PLAN_CHANGE",
        "RESOURCE_CONFLICT",
        "DECISION_ACTION_PROGRESS",
    } <= event_types
