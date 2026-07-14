from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from soc_ot.agents.providers import ReplayProvider
from soc_ot.api.main import create_app
from soc_ot.application.evaluation import evaluate_case, run_evaluation
from soc_ot.application.multi_role import run_ablation
from soc_ot.application.outcome_advances import (
    InMemoryOutcomeAdvanceRepository,
    OutcomeAdvanceConflict,
)
from soc_ot.application.outcomes import advance_outcome
from soc_ot.application.packets import build_observable_case_packet
from soc_ot.application.repositories import InMemoryCaseRepository, PostgresCaseRepository
from soc_ot.application.review_runs import InMemoryReviewRunRepository
from soc_ot.infrastructure.database import get_outcome_engine, get_runtime_engine
from soc_ot.infrastructure.fixtures import FixtureRepository
from soc_ot.infrastructure.hidden_repository import (
    FixtureHiddenCaseReader,
    PostgresHiddenCaseRepository,
)

ROOT = Path(__file__).resolve().parents[2]


def test_all_twelve_v2_cases_complete_replay_evaluation() -> None:
    summary = run_evaluation(FixtureRepository(ROOT / "fixtures"))

    assert summary.total == 12
    assert summary.passed == 12
    assert {result.partition for result in summary.results} == {
        "development", "validation", "sealed-unseen"
    }


def test_step_advance_reveals_closed_world_outcome() -> None:
    fixtures = FixtureRepository(ROOT / "fixtures")
    case = fixtures.load_observable("CASE-VR-001")
    hidden = fixtures.load_hidden(case.case_id)
    packet = build_observable_case_packet(case)
    decision = run_ablation(
        packet, ReplayProvider(), "B3", allowed_decision_types=case.allowed_decision_types
    ).decision

    outcome = advance_outcome(case, hidden, decision, target_step=15)

    assert outcome.current_step == 15
    assert outcome.metrics["DDR_BANDWIDTH"] == 20.6
    assert outcome.guardrail_state == "triggered"
    assert outcome.executed_actions == ["rollback"]


def test_outcome_is_deterministic_and_wall_clock_independent() -> None:
    fixtures = FixtureRepository(ROOT / "fixtures")
    case = fixtures.load_observable("CASE-VR-001")
    hidden = fixtures.load_hidden(case.case_id)
    decision = evaluate_case(fixtures, case.case_id).ablation.decision
    first = advance_outcome(case, hidden, decision, target_step=15)
    second = advance_outcome(case, hidden, decision, target_step=15)
    assert first == second
    assert first.event_ids == second.event_ids


def test_unknown_option_and_conflicting_path_fail_closed() -> None:
    fixtures = FixtureRepository(ROOT / "fixtures")
    case = fixtures.load_observable("CASE-VR-001")
    hidden = fixtures.load_hidden(case.case_id)
    decision = evaluate_case(fixtures, case.case_id).ablation.decision
    unknown = decision.model_copy(update={"selected_option_id": "OPT-UNKNOWN"})
    with pytest.raises(ValueError, match="OUTCOME_PATH_UNDEFINED"):
        advance_outcome(case, hidden, unknown, target_step=15)
    conflicting = hidden.model_copy(
        update={"outcome_paths": [hidden.outcome_paths[0], hidden.outcome_paths[0]]}
    )
    with pytest.raises(ValueError, match="OUTCOME_RULE_CONFLICT"):
        advance_outcome(case, conflicting, decision, target_step=15)


def test_step_must_advance() -> None:
    fixtures = FixtureRepository(ROOT / "fixtures")
    result = evaluate_case(fixtures, "CASE-VR-001")
    case = fixtures.load_observable("CASE-VR-001")
    with pytest.raises(ValueError, match="TARGET_STEP_MUST_ADVANCE"):
        advance_outcome(
            case,
            fixtures.load_hidden(case.case_id),
            result.ablation.decision,
            target_step=case.current_step,
        )


def test_outcome_advance_is_idempotent_and_rejects_outdated_step() -> None:
    fixtures = FixtureRepository(ROOT / "fixtures")
    case = fixtures.load_observable("CASE-VR-001")
    hidden = fixtures.load_hidden(case.case_id)
    decision = evaluate_case(fixtures, case.case_id).ablation.decision
    repository = InMemoryOutcomeAdvanceRepository()
    first = repository.advance(
        case, hidden, decision, from_step=12, to_step=15, idempotency_key="advance-1"
    )
    repeated = repository.advance(
        case, hidden, decision, from_step=12, to_step=15, idempotency_key="advance-1"
    )
    assert first == repeated
    with pytest.raises(OutcomeAdvanceConflict, match="IDEMPOTENCY_KEY_REUSED"):
        repository.advance(
            case, hidden, decision, from_step=12, to_step=16, idempotency_key="advance-1"
        )
    with pytest.raises(OutcomeAdvanceConflict, match="SIMULATION_STEP_CONFLICT"):
        repository.advance(
            case, hidden, decision, from_step=12, to_step=16, idempotency_key="advance-2"
        )


def test_canonical_outcome_advance_api_uses_hidden_reader_port() -> None:
    fixtures = FixtureRepository(ROOT / "fixtures")
    case = fixtures.load_observable("CASE-VR-001")
    cases = InMemoryCaseRepository()
    cases.save(case, event_type="fixture_imported", expected_aggregate_version=None)
    client = TestClient(
        create_app(
            cases,
            InMemoryReviewRunRepository(),
            outcome_repository=InMemoryOutcomeAdvanceRepository(),
            hidden_reader=FixtureHiddenCaseReader(fixtures),
        )
    )
    decision = evaluate_case(fixtures, case.case_id).ablation.decision
    response = client.post(
        f"/api/v1/decision-cases/{case.case_id}/outcome-advances",
        headers={"Idempotency-Key": "api-advance", "If-Match": '"1"'},
        json={
            "command_schema_version": "outcome-advance-command.v1",
            "from_step": 12,
            "to_step": 15,
            "decision": decision.model_dump(mode="json"),
        },
    )
    assert response.status_code == 200
    assert response.json()["executed_actions"] == ["rollback"]


def test_evaluation_api_cannot_reveal_hidden_outcome_before_required_step() -> None:
    fixtures = FixtureRepository(ROOT / "fixtures")
    case = fixtures.load_observable("CASE-VR-001")
    cases = InMemoryCaseRepository()
    cases.save(case, event_type="fixture_imported", expected_aggregate_version=None)
    client = TestClient(create_app(cases, InMemoryReviewRunRepository()))

    early = client.get(f"/api/v1/decision-cases/{case.case_id}/evaluation")
    assert early.status_code == 409
    assert early.json()["detail"]["code"] == "OUTCOME_NOT_REVEALED"

    cases.save(
        case.model_copy(update={"current_step": 15}),
        event_type="outcome_advanced",
        expected_aggregate_version=1,
    )
    absent = client.get(f"/api/v1/decision-cases/{case.case_id}/evaluation")
    assert absent.status_code == 404
    created = client.post(
        f"/api/v1/decision-cases/{case.case_id}/evaluations",
        headers={"Idempotency-Key": "evaluation-1", "If-Match": '"2"'},
    )
    repeated = client.post(
        f"/api/v1/decision-cases/{case.case_id}/evaluations",
        headers={"Idempotency-Key": "evaluation-1", "If-Match": '"2"'},
    )
    revealed = client.get(f"/api/v1/decision-cases/{case.case_id}/evaluation")
    assert created.status_code == 200
    assert repeated.json() == created.json()
    assert revealed.json() == created.json()
    assert revealed.json()["outcome_evaluation"]["passed"] is True


@pytest.mark.postgres
def test_outcome_api_replays_same_idempotent_result_after_version_advances() -> None:
    fixtures = FixtureRepository(ROOT / "fixtures")
    case = fixtures.load_observable("CASE-VR-001")
    cases = PostgresCaseRepository(get_runtime_engine())
    current = cases.get(case.case_id)
    stored = cases.save(
        case,
        event_type="fixture_reimported" if current else "fixture_imported",
        expected_aggregate_version=current.aggregate_version if current else None,
    )
    PostgresHiddenCaseRepository(get_outcome_engine()).upsert(
        fixtures.load_hidden(case.case_id)
    )
    decision = evaluate_case(fixtures, case.case_id).ablation.decision
    headers = {
        "Idempotency-Key": f"api-advance-replay-after-version-{stored.aggregate_version}",
        "If-Match": f'"{stored.aggregate_version}"',
    }
    body = {
        "command_schema_version": "outcome-advance-command.v1",
        "from_step": 12,
        "to_step": 15,
        "decision": decision.model_dump(mode="json"),
    }
    client = TestClient(create_app())

    first = client.post(
        f"/api/v1/decision-cases/{case.case_id}/outcome-advances",
        headers=headers,
        json=body,
    )
    repeated = client.post(
        f"/api/v1/decision-cases/{case.case_id}/outcome-advances",
        headers=headers,
        json=body,
    )

    assert first.status_code == 200
    assert repeated.status_code == 200
    assert repeated.json() == first.json()


@pytest.mark.postgres
def test_evaluation_persists_across_api_restart_and_replays_idempotently() -> None:
    fixtures = FixtureRepository(ROOT / "fixtures")
    case = fixtures.load_observable("CASE-VR-001").model_copy(update={"current_step": 15})
    cases = PostgresCaseRepository(get_runtime_engine())
    current = cases.get(case.case_id)
    stored = cases.save(
        case,
        event_type="evaluation_test_state",
        expected_aggregate_version=current.aggregate_version if current else None,
    )
    key = f"evaluation-persist-{uuid4()}"
    headers = {
        "Idempotency-Key": key,
        "If-Match": f'"{stored.aggregate_version}"',
    }

    first_client = TestClient(create_app())
    created = first_client.post(
        f"/api/v1/decision-cases/{case.case_id}/evaluations", headers=headers
    )
    repeated = first_client.post(
        f"/api/v1/decision-cases/{case.case_id}/evaluations", headers=headers
    )
    restarted_client = TestClient(create_app())
    persisted = restarted_client.get(
        f"/api/v1/decision-cases/{case.case_id}/evaluation"
    )

    assert created.status_code == 200
    assert repeated.json() == created.json()
    assert persisted.json() == created.json()


@pytest.mark.postgres
def test_runtime_role_cannot_read_hidden_schema() -> None:
    with get_runtime_engine().connect() as connection, pytest.raises(ProgrammingError):
        connection.execute(text("SELECT * FROM hidden.hidden_cases"))
