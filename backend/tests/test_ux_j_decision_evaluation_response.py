from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from soc_ot.agents.providers import ReplayProvider
from soc_ot.api.main import create_app
from soc_ot.application.decision_evaluation_responses import (
    DecisionEvaluationResponseConflict,
    DecisionFinalResponseCommand,
    DecisionInitialResponseCommand,
    InMemoryDecisionEvaluationResponseRepository,
    PostgresDecisionEvaluationResponseRepository,
)
from soc_ot.application.repositories import InMemoryCaseRepository
from soc_ot.application.review_runs import (
    InMemoryReviewRunRepository,
    execute_claimed_run,
)
from soc_ot.application.simulated_decisions import InMemorySimulatedDecisionRepository
from soc_ot.infrastructure.database import get_runtime_engine
from soc_ot.infrastructure.fixtures import FixtureRepository

ROOT = Path(__file__).resolve().parents[2]


def _setup() -> tuple[
    TestClient,
    InMemoryCaseRepository,
    InMemoryReviewRunRepository,
    InMemorySimulatedDecisionRepository,
]:
    case = FixtureRepository(ROOT / "fixtures").load_observable("CASE-VR-001")
    cases = InMemoryCaseRepository()
    cases.save(case, event_type="fixture_imported", expected_aggregate_version=None)
    runs = InMemoryReviewRunRepository()
    decisions = InMemorySimulatedDecisionRepository()
    return (
        TestClient(create_app(cases, runs, decision_repository=decisions)),
        cases,
        runs,
        decisions,
    )


def _initial_body() -> dict[str, object]:
    return {
        "command_schema_version": "decision-initial-response-command.v1",
        "option_id": "OPT-SW-GUARDED",
        "accepted_risks_ko": ["장시간 thermal 거동"],
        "safeguards_ko": ["feature flag로 즉시 철회"],
        "rationale_ko": "Freeze 전에 가역 경로를 확보합니다.",
    }


def _create_advice(
    client: TestClient,
    cases: InMemoryCaseRepository,
    runs: InMemoryReviewRunRepository,
) -> None:
    created = client.post(
        "/api/v1/decision-cases/CASE-VR-001/review-runs",
        headers={"Idempotency-Key": "ux-j-dossier", "If-Match": '"1"'},
        json={"command_schema_version": "review-run-command.v1", "scope": "dossier"},
    )
    run_id = created.json()["run_id"]
    claimed = runs.claim("ux-j-worker", 60)
    assert claimed is not None
    result = execute_claimed_run(
        claimed,
        cases,
        ReplayProvider(),
    )
    runs.complete(run_id, "ux-j-worker", result)
    decision = client.post(
        "/api/v1/decision-cases/CASE-VR-001/simulated-decisions",
        params={"review_run_id": run_id},
        headers={"Idempotency-Key": "ux-j-chair", "If-Match": '"1"'},
    )
    assert decision.status_code == 200


def test_evaluation_response_is_ordered_immutable_and_not_human_evidence() -> None:
    client, cases, runs, decisions = _setup()
    missing = client.get(
        "/api/v1/decision-cases/CASE-VR-001/evaluation-response"
    )
    initial = client.post(
        "/api/v1/decision-cases/CASE-VR-001/evaluation-response/initial",
        headers={"Idempotency-Key": "initial-1", "If-Match": '"1"'},
        json=_initial_body(),
    )
    replayed = client.post(
        "/api/v1/decision-cases/CASE-VR-001/evaluation-response/initial",
        headers={"Idempotency-Key": "initial-1", "If-Match": '"1"'},
        json=_initial_body(),
    )
    early_reveal = client.post(
        "/api/v1/decision-cases/CASE-VR-001/evaluation-response/advice-reveal",
        headers={"Idempotency-Key": "reveal-early", "If-Match": '"1"'},
        json={"command_schema_version": "decision-advice-reveal-command.v1"},
    )

    assert missing.status_code == 200
    assert missing.json() is None
    assert initial.status_code == 200
    assert replayed.json() == initial.json()
    assert initial.json()["participant_kind"] == "builder"
    assert initial.json()["interpretation"] == "engineering_proxy_only"
    assert "human" not in initial.text
    assert early_reveal.status_code == 409
    assert early_reveal.json()["detail"]["code"] == "SIMULATED_ADVICE_REQUIRED"

    case = cases.get("CASE-VR-001")
    assert case is not None
    _create_advice(client, cases, runs)
    advice_before = decisions.latest("CASE-VR-001")
    assert advice_before is not None
    reveal = client.post(
        "/api/v1/decision-cases/CASE-VR-001/evaluation-response/advice-reveal",
        headers={"Idempotency-Key": "reveal-1", "If-Match": '"1"'},
        json={"command_schema_version": "decision-advice-reveal-command.v1"},
    )
    assert reveal.status_code == 200
    assert reveal.json()["advice_snapshot"]["selected_option_id"] == (
        advice_before.decision.selected_option_id
    )

    wrong_accept = client.post(
        "/api/v1/decision-cases/CASE-VR-001/evaluation-response/final",
        headers={"Idempotency-Key": "final-wrong", "If-Match": '"1"'},
        json={
            "command_schema_version": "decision-final-response-command.v1",
            "adoption": "accept",
            "option_id": "OPT-DEFER-EIS",
            "accepted_risks_ko": ["일정 지연"],
            "safeguards_ko": ["Step 15 재검토"],
            "rationale_ko": "실측을 기다립니다.",
            "difference_reason_ko": None,
        },
    )
    assert wrong_accept.status_code == 409
    assert wrong_accept.json()["detail"]["code"] == "ACCEPT_MUST_MATCH_ADVICE"

    final_body = {
        "command_schema_version": "decision-final-response-command.v1",
        "adoption": "modify",
        "option_id": "OPT-DEFER-EIS",
        "accepted_risks_ko": ["Architecture Freeze 지연"],
        "safeguards_ko": ["Step 15 실측 직후 재검토"],
        "rationale_ko": "현재 불확실성에서는 잘못된 commit의 영향이 큽니다.",
        "difference_reason_ko": "장시간 thermal 근거가 없어 보수적으로 수정합니다.",
    }
    final = client.post(
        "/api/v1/decision-cases/CASE-VR-001/evaluation-response/final",
        headers={"Idempotency-Key": "final-1", "If-Match": '"1"'},
        json=final_body,
    )
    overwrite = client.post(
        "/api/v1/decision-cases/CASE-VR-001/evaluation-response/final",
        headers={"Idempotency-Key": "final-2", "If-Match": '"1"'},
        json=final_body,
    )

    assert final.status_code == 200
    assert final.json()["final_response"]["adoption"] == "modify"
    assert overwrite.status_code == 409
    assert overwrite.json()["detail"]["code"] == "FINAL_RESPONSE_IMMUTABLE"
    assert decisions.latest("CASE-VR-001") == advice_before
    assert cases.get("CASE-VR-001") == case


def test_modify_and_reject_require_a_difference_reason() -> None:
    with pytest.raises(ValueError, match="DIFFERENCE_REASON_REQUIRED"):
        DecisionFinalResponseCommand(
            adoption="reject",
            option_id="OPT-DEFER-EIS",
            accepted_risks_ko=["일정"],
            safeguards_ko=["재검토"],
            rationale_ko="거부합니다.",
        )


@pytest.mark.postgres
def test_postgres_response_repository_matches_in_memory_and_survives_restart() -> None:
    client, cases, runs, decisions = _setup()
    _create_advice(client, cases, runs)
    advice = decisions.latest("CASE-VR-001")
    assert advice is not None
    actor_id = f"ux-j-postgres-{uuid4()}"
    initial = DecisionInitialResponseCommand.model_validate(_initial_body())
    memory = InMemoryDecisionEvaluationResponseRepository()
    postgres = PostgresDecisionEvaluationResponseRepository(get_runtime_engine())
    kwargs = {
        "case_id": "CASE-VR-001",
        "actor_id": actor_id,
        "idempotency_key": f"initial-{uuid4()}",
        "expected_aggregate_version": 1,
        "actual_aggregate_version": 1,
        "allowed_option_ids": {"OPT-SW-GUARDED", "OPT-DEFER-EIS"},
        "command": initial,
    }

    expected = memory.record_initial(**kwargs)
    actual = postgres.record_initial(**kwargs)
    assert actual.initial_response is not None
    assert expected.initial_response is not None
    assert actual.initial_response.model_dump(exclude={"recorded_at"}) == (
        expected.initial_response.model_dump(exclude={"recorded_at"})
    )
    assert actual.participant_kind == "builder"

    reveal_key = f"reveal-{uuid4()}"
    postgres.reveal_advice(
        case_id="CASE-VR-001",
        actor_id=actor_id,
        idempotency_key=reveal_key,
        expected_aggregate_version=1,
        actual_aggregate_version=1,
        advice=advice,
    )
    restarted = PostgresDecisionEvaluationResponseRepository(get_runtime_engine()).get(
        case_id="CASE-VR-001",
        actor_id=actor_id,
    )
    assert restarted is not None
    assert restarted.advice_snapshot is not None
    with pytest.raises(
        DecisionEvaluationResponseConflict, match="ADVICE_REVEAL_IMMUTABLE"
    ):
        postgres.reveal_advice(
            case_id="CASE-VR-001",
            actor_id=actor_id,
            idempotency_key=f"reveal-{uuid4()}",
            expected_aggregate_version=1,
            actual_aggregate_version=1,
            advice=advice,
        )
