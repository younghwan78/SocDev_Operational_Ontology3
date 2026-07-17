from pathlib import Path

from fastapi.testclient import TestClient

from soc_ot.agents.providers import ReplayProvider
from soc_ot.api.main import create_app
from soc_ot.application.evaluation import evaluate_case
from soc_ot.application.multi_role import run_ablation
from soc_ot.application.outcome_advances import InMemoryOutcomeAdvanceRepository
from soc_ot.application.outcomes import advance_outcome
from soc_ot.application.packets import build_observable_case_packet
from soc_ot.application.repositories import InMemoryCaseRepository, StoredCase
from soc_ot.application.simulated_decisions import InMemorySimulatedDecisionRepository
from soc_ot.application.workspace_projection_v2 import build_workspace_projection_v2
from soc_ot.domain.models import AgentRunStatus
from soc_ot.infrastructure.evaluation_repository import FixtureEvaluationRepository
from soc_ot.infrastructure.fixtures import FixtureRepository

ROOT = Path(__file__).resolve().parents[2]


def _fixtures() -> FixtureRepository:
    return FixtureRepository(ROOT / "fixtures")


def _case_and_result():
    case = _fixtures().load_observable("CASE-VR-001")
    result = run_ablation(
        build_observable_case_packet(case),
        ReplayProvider(),
        "B2",
        allowed_decision_types=case.allowed_decision_types,
    )
    return case, result


def _workspace(*, result=None, outcome=None, evaluation=None, at_step=None):
    case, default_result = _case_and_result()
    effective_result = result or default_result
    return build_workspace_projection_v2(
        StoredCase(case=case, aggregate_version=4),
        at_step=at_step,
        content=_fixtures().load_workspace_ux(case.case_id),
        dossier=effective_result.dossier,
        dossier_run_status=AgentRunStatus.COMPLETED,
        dossier_run_id="RUN-UX-E",
        decision_result=effective_result,
        outcome=outcome,
        evaluation=evaluation,
    )


def test_decision_projects_one_action_flow_with_safeguards_and_rollback() -> None:
    workspace = _workspace()

    assert workspace.header.workspace_phase == "OUTCOME_RUNNING"
    assert workspace.workflow.primary_action == "ADVANCE_SIMULATION"
    assert workspace.workflow.allowed_actions == ["ADVANCE_SIMULATION"]
    assert workspace.workflow.dossier_run_id == "RUN-UX-E"
    assert workspace.controls.action_plan is not None
    assert workspace.controls.action_plan.owner == "Technical PM"
    assert workspace.controls.action_plan.verification_ko
    assert workspace.controls.action_plan.fallback_action_ko
    assert workspace.controls.action_plan.status == "in_progress"
    assert "OPT-" not in workspace.controls.action_plan.action_ko
    assert "observable risk" not in workspace.controls.action_plan.decision_rationale_ko
    assert workspace.controls.safeguards
    assert workspace.controls.safeguards[0].metric_label_ko == "DDR 대역폭"
    assert workspace.controls.safeguards[0].operator_ko == "≤"
    assert workspace.controls.safeguards[0].rollback_trigger_ko
    assert workspace.observed_decision_transitions.available is True
    assert workspace.observed_decision_transitions.state_changes[0].entity_type == "action"
    assert workspace.outcome_and_evaluation.outcome_state == "running"


def test_revealed_outcome_separates_expected_actual_and_guardrail_result() -> None:
    case, result = _case_and_result()
    outcome = advance_outcome(
        case,
        _fixtures().load_hidden(case.case_id),
        result.decision,
        target_step=15,
    )
    workspace = _workspace(result=result, outcome=outcome)

    assert workspace.header.workspace_phase == "EVALUATION_READY"
    assert workspace.workflow.primary_action == "VIEW_EVALUATION"
    assert workspace.controls.action_plan is not None
    assert workspace.controls.action_plan.status == "cancelled"
    assert workspace.outcome_and_evaluation.outcome_state == "available"
    assert workspace.outcome_and_evaluation.hidden_until_step_advance is False
    assert workspace.outcome_and_evaluation.expected_ko
    assert any("DDR 대역폭" in item for item in workspace.outcome_and_evaluation.actual_ko)
    assert all("DDR_BANDWIDTH" not in item for item in workspace.outcome_and_evaluation.actual_ko)
    assert any("rollback" in item for item in workspace.outcome_and_evaluation.guardrail_results_ko)
    assert workspace.observed_decision_transitions.guardrail_events_ko
    assert all(
        change.provenance == "observed_event"
        for change in workspace.observed_decision_transitions.state_changes
    )


def test_observed_outcome_links_selected_option_to_work_and_action_changes() -> None:
    case, result = _case_and_result()
    deferred_decision = result.decision.model_copy(
        update={"selected_option_id": "OPT-DEFER-EIS"}
    )
    deferred_result = result.model_copy(update={"decision": deferred_decision})
    outcome = advance_outcome(
        case,
        _fixtures().load_hidden(case.case_id),
        deferred_decision,
        target_step=15,
    )
    workspace = _workspace(result=deferred_result, outcome=outcome)

    entity_types = {
        item.entity_type for item in workspace.observed_decision_transitions.state_changes
    }
    assert entity_types == {"work_item", "action"}
    assert all(
        item.basis_refs == outcome.event_ids
        for item in workspace.observed_decision_transitions.state_changes
    )


def test_evaluation_closes_loop_without_combining_process_and_outcome() -> None:
    case, result = _case_and_result()
    outcome = advance_outcome(
        case,
        _fixtures().load_hidden(case.case_id),
        result.decision,
        target_step=15,
    )
    evaluation = evaluate_case(_fixtures(), case.case_id, topology="B2")
    workspace = _workspace(result=result, outcome=outcome, evaluation=evaluation)

    assert workspace.header.workspace_phase == "CLOSED"
    assert workspace.workflow.primary_action == "VIEW_LEARNING_SUMMARY"
    assert workspace.outcome_and_evaluation.process_evaluation_ko
    assert workspace.outcome_and_evaluation.outcome_evaluation_ko
    assert workspace.outcome_and_evaluation.lessons_ko

    historical = _workspace(
        result=result,
        outcome=outcome,
        evaluation=evaluation,
        at_step=9,
    )
    assert historical.controls.action_plan is None
    assert historical.observed_decision_transitions.available is False
    assert historical.outcome_and_evaluation.outcome_state == "not_available"
    assert historical.workflow.dossier_run_id is None


def test_workspace_api_reloads_persisted_decision_outcome_and_evaluation() -> None:
    fixtures = _fixtures()
    case, result = _case_and_result()
    cases = InMemoryCaseRepository()
    stored = cases.save(
        case,
        event_type="fixture_imported",
        expected_aggregate_version=None,
    )
    decisions = InMemorySimulatedDecisionRepository()
    decisions.create(
        case_id=case.case_id,
        review_run_id="RUN-UX-E",
        idempotency_key="decision-ux-e",
        expected_aggregate_version=stored.aggregate_version,
        actual_aggregate_version=stored.aggregate_version,
        actor_id="test",
        factory=lambda: result,
    )
    outcomes = InMemoryOutcomeAdvanceRepository()
    evaluations = FixtureEvaluationRepository(fixtures)
    client = TestClient(
        create_app(
            cases,
            outcome_repository=outcomes,
            evaluation_repository=evaluations,
            decision_repository=decisions,
        )
    )

    decision_workspace = client.get(
        f"/api/v1/decision-cases/{case.case_id}/workspace"
    )
    assert decision_workspace.json()["header"]["workspace_phase"] == "OUTCOME_RUNNING"

    outcome_response = client.post(
        f"/api/v1/decision-cases/{case.case_id}/outcome-advances",
        headers={"Idempotency-Key": "outcome-ux-e", "If-Match": '"1"'},
        json={
            "command_schema_version": "outcome-advance-command.v1",
            "from_step": 12,
            "to_step": 15,
        },
    )
    assert outcome_response.status_code == 200
    outcome_workspace = client.get(
        f"/api/v1/decision-cases/{case.case_id}/workspace"
    ).json()
    assert outcome_workspace["time_context"]["current_step"] == 15
    assert outcome_workspace["header"]["workspace_phase"] == "EVALUATION_READY"

    evaluation_response = client.post(
        f"/api/v1/decision-cases/{case.case_id}/evaluations",
        headers={"Idempotency-Key": "evaluation-ux-e", "If-Match": '"1"'},
    )
    assert evaluation_response.status_code == 200
    closed_workspace = client.get(
        f"/api/v1/decision-cases/{case.case_id}/workspace"
    ).json()
    assert closed_workspace["header"]["workspace_phase"] == "CLOSED"
    assert closed_workspace["outcome_and_evaluation"]["lessons_ko"]
