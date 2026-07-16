from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from soc_ot.api.main import create_app
from soc_ot.application.repositories import InMemoryCaseRepository, StoredCase
from soc_ot.application.workspace_projection_v2 import build_workspace_projection_v2
from soc_ot.domain.models import DecisionCaseStatus
from soc_ot.infrastructure.fixtures import FixtureRepository

ROOT = Path(__file__).resolve().parents[2]


def _fixtures() -> FixtureRepository:
    return FixtureRepository(ROOT / "fixtures")


def _stored(case_id: str = "CASE-VR-001") -> StoredCase:
    return StoredCase(case=_fixtures().load_observable(case_id), aggregate_version=7)


def test_current_workspace_uses_live_state_and_validated_model_content() -> None:
    fixtures = _fixtures()
    workspace = build_workspace_projection_v2(
        _stored(),
        content=fixtures.load_workspace_ux("CASE-VR-001"),
    )

    assert workspace.projection_schema_version == "decision-workspace.v2"
    assert workspace.time_context.mode == "current"
    assert workspace.header.workspace_phase == "READY_FOR_REVIEW"
    assert workspace.workflow.primary_action == "RUN_VIRTUAL_REVIEW"
    assert workspace.development_twin.state_at_selected_step.reconstructed_at_step == 12
    assert workspace.development_twin.blocker_impacts
    assert any(
        "HW carry-over 가능성 검토" in item.downstream_work_item_titles
        for item in workspace.development_twin.blocker_impacts
    )
    assert workspace.development_twin.commitment_windows[0].closes_at_step == 13
    assert {
        item.option_id for item in workspace.expected_option_transitions
    } == {"OPT-SW-GUARDED", "OPT-DEFER-EIS"}
    assert all(
        item.label == "expected_from_observable_model"
        for item in workspace.expected_option_transitions
    )
    assert workspace.observed_decision_transitions.available is False


def test_historical_workspace_reconstructs_observable_state_without_future_workflow() -> None:
    fixtures = _fixtures()
    stored = _stored()
    closed_case = stored.case.model_copy(update={"status": DecisionCaseStatus.CLOSED})
    workspace = build_workspace_projection_v2(
        StoredCase(case=closed_case, aggregate_version=stored.aggregate_version),
        at_step=9,
        content=fixtures.load_workspace_ux("CASE-VR-001"),
    )

    assert workspace.time_context.mode == "historical"
    assert workspace.time_context.earliest_available_step == 9
    assert workspace.time_context.commands_allowed_at_selected_step is False
    assert workspace.header.workspace_phase is None
    assert workspace.header.case_status is None
    assert workspace.workflow.primary_action is None
    assert workspace.workflow.allowed_actions == []
    assert workspace.development_twin.commitment_windows == []
    assert all(
        chain.observed_at_step <= 9 for chain in workspace.development_twin.causal_chains
    )
    assert all(
        not item.state_changes and item.model_basis == []
        for item in workspace.expected_option_transitions
    )
    assert workspace.observed_decision_transitions.available is False
    assert "종료" not in workspace.current_brief.why_now_ko


def test_generic_case_fails_open_as_unknown_instead_of_inventing_model_transitions() -> None:
    fixtures = _fixtures()
    case_id = fixtures.development_case_ids()[0]
    workspace = build_workspace_projection_v2(
        _stored(case_id),
        content=fixtures.load_workspace_ux(case_id),
    )

    assert workspace.development_twin.commitment_windows == []
    assert all(
        item.unknown_impacts_ko == ["선택한 Step에서 검증된 상태 전이 모델이 없습니다."]
        for item in workspace.expected_option_transitions
    )
    assert workspace.decision_posture.downside == "unknown"


@pytest.mark.parametrize(
    ("status", "phase", "action"),
    [
        (DecisionCaseStatus.CONTEXT_BUILDING, "CONTEXT_PREPARATION", "BUILD_CONTEXT"),
        (DecisionCaseStatus.DECISION_REQUIRED, "READY_FOR_REVIEW", "RUN_VIRTUAL_REVIEW"),
        (DecisionCaseStatus.ACTIONING, "OUTCOME_RUNNING", "ADVANCE_SIMULATION"),
        (DecisionCaseStatus.VERIFIED, "EVALUATION_READY", "VIEW_EVALUATION"),
        (DecisionCaseStatus.CLOSED, "CLOSED", "VIEW_LEARNING_SUMMARY"),
    ],
)
def test_current_brief_adapts_to_persisted_case_phase(
    status: DecisionCaseStatus,
    phase: str,
    action: str,
) -> None:
    fixtures = _fixtures()
    case = fixtures.load_observable("CASE-VR-001").model_copy(update={"status": status})
    workspace = build_workspace_projection_v2(
        StoredCase(case=case, aggregate_version=8),
        content=fixtures.load_workspace_ux("CASE-VR-001"),
    )

    assert workspace.header.workspace_phase == phase
    assert workspace.workflow.primary_action == action


def test_workspace_api_supports_selected_step_and_rejects_future_step() -> None:
    cases = InMemoryCaseRepository()
    case = _fixtures().load_observable("CASE-VR-001")
    cases.save(case, event_type="fixture_imported", expected_aggregate_version=None)
    client = TestClient(create_app(cases))

    historical = client.get(
        "/api/v1/decision-cases/CASE-VR-001/workspace", params={"at_step": 9}
    )
    future = client.get(
        "/api/v1/decision-cases/CASE-VR-001/workspace", params={"at_step": 13}
    )
    before_history = client.get(
        "/api/v1/decision-cases/CASE-VR-001/workspace", params={"at_step": 8}
    )

    assert historical.status_code == 200
    assert historical.json()["time_context"]["selected_step"] == 9
    assert historical.json()["header"]["workspace_phase"] is None
    assert future.status_code == 422
    assert future.json()["detail"]["code"] == "DEVELOPMENT_STEP_OUT_OF_RANGE"
    assert before_history.status_code == 422
    assert before_history.json()["detail"]["code"] == "DEVELOPMENT_STEP_OUT_OF_RANGE"
