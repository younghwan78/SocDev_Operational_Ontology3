from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from soc_ot.agents.contracts import ProviderReviewResult, ProviderUsage
from soc_ot.agents.multi_role import (
    DecisionActionPlan,
    DossierExecution,
    Safeguard,
    SimulatedDecision,
)
from soc_ot.agents.providers import ReplayProvider
from soc_ot.api.main import create_app
from soc_ot.application.multi_role import (
    AgentRuntimeBudget,
    build_dossier,
    run_ablation,
    simulated_chair_decision,
    validate_decision_policy,
)
from soc_ot.application.packets import build_observable_case_packet
from soc_ot.application.repositories import InMemoryCaseRepository
from soc_ot.application.review_runs import (
    InMemoryReviewRunRepository,
    enqueue_dossier_review,
    execute_claimed_run,
)
from soc_ot.domain.models import DecisionType, Quantity, QuantityMode
from soc_ot.infrastructure.fixtures import FixtureRepository

ROOT = Path(__file__).resolve().parents[2]


def case_and_packet():
    case = FixtureRepository(ROOT / "fixtures").load_observable("CASE-VR-001")
    return case, build_observable_case_packet(case)


def test_all_ablation_topologies_share_one_interface() -> None:
    case, packet = case_and_packet()
    results = {
        topology: run_ablation(
            packet, ReplayProvider(), topology, allowed_decision_types=case.allowed_decision_types
        )
        for topology in ("B0", "B1", "B2", "B3")
    }

    assert results["B0"].role_count == 0
    assert results["B1"].role_count == 1
    assert results["B2"].role_count == len(packet.selected_role_ids)
    assert results["B3"].challenger_used is True
    assert all(results[item].chair_used is False for item in ("B0", "B1", "B2"))
    assert results["B3"].chair_used is True
    assert results["B2"].decision.decision_source == "deterministic_core"
    assert results["B3"].decision.decision_source == "simulated_chair"
    assert results["B0"].provider_attempts == 0
    assert results["B1"].provider_attempts == 1
    assert results["B2"].provider_attempts == len(packet.selected_role_ids)
    assert results["B3"].provider_attempts == len(packet.selected_role_ids) + 4


def test_dissent_survives_challenge_and_chair_acknowledges_it() -> None:
    case, packet = case_and_packet()
    result = run_ablation(
        packet, ReplayProvider(), "B3", allowed_decision_types=case.allowed_decision_types
    )

    assert result.dossier.dissent
    assert result.dossier.original_reviews
    assert len(result.dossier.revised_reviews) == 2
    assert set(result.decision.dissent_acknowledged) == {
        item.role_id for item in result.dossier.dissent
    }


def test_b3_invokes_and_accounts_for_chair_provider_once() -> None:
    case, packet = case_and_packet()

    class CountingChairProvider(ReplayProvider):
        chair_calls = 0

        def decide(self, packet, dossier, allowed_decision_types):
            self.chair_calls += 1
            return super().decide(packet, dossier, allowed_decision_types)

    provider = CountingChairProvider()
    result = run_ablation(
        packet,
        provider,
        "B3",
        allowed_decision_types=case.allowed_decision_types,
    )

    assert provider.chair_calls == 1
    assert result.provider_attempts == 8
    assert result.decision.decision_source == "simulated_chair"


def test_chair_uses_operability_policy_instead_of_role_majority() -> None:
    case, packet = case_and_packet()
    reviews = [
        ReplayProvider()
        .review(packet, role_id)
        .review.model_copy(update={"recommendation": DecisionType.COLLECT_MINIMUM_EVIDENCE})
        for role_id in packet.selected_role_ids
    ]
    unanimous_collect = build_dossier(packet, reviews)

    decision = simulated_chair_decision(
        packet, unanimous_collect, case.allowed_decision_types
    )

    assert decision.decision_type is DecisionType.APPROVE_WITH_GUARDRAILS
    assert "다수결이 아니라" in decision.rationale


def test_chair_requires_more_evidence_for_irreversible_low_recovery_option() -> None:
    case, packet = case_and_packet()
    unsafe = packet.option_operability[0].model_copy(
        update={"reversible": False, "recoverability": "low", "detectability": "unknown"}
    )
    unsafe_packet = packet.model_copy(update={"option_operability": [unsafe]})
    dossier = run_ablation(
        packet,
        ReplayProvider(),
        "B2",
        allowed_decision_types=case.allowed_decision_types,
    ).dossier

    decision = simulated_chair_decision(
        unsafe_packet,
        dossier,
        [DecisionType.RUN_REVERSIBLE_TRIAL, DecisionType.COLLECT_MINIMUM_EVIDENCE],
    )

    assert decision.decision_type is DecisionType.COLLECT_MINIMUM_EVIDENCE
    assert decision.selected_option_id is None


def test_conditional_decision_has_complete_safeguard() -> None:
    case, packet = case_and_packet()
    result = run_ablation(
        packet, ReplayProvider(), "B3", allowed_decision_types=case.allowed_decision_types
    )
    safeguard = result.decision.safeguards[0]

    assert safeguard.rollback_trigger
    assert safeguard.owner
    assert safeguard.verification


@pytest.mark.parametrize(
    ("decision_type", "action_type"),
    [
        (DecisionType.APPROVE, "execute"),
        (DecisionType.APPROVE_WITH_GUARDRAILS, "execute"),
        (DecisionType.RUN_REVERSIBLE_TRIAL, "execute"),
        (DecisionType.COLLECT_MINIMUM_EVIDENCE, "collect_evidence"),
        (DecisionType.DEFER_UNTIL_TRIGGER, "defer"),
        (DecisionType.ESCALATE, "escalate"),
        (DecisionType.REJECT, "reject"),
    ],
)
def test_every_decision_type_has_an_executable_action_plan(
    decision_type: DecisionType, action_type: str
) -> None:
    case, packet = case_and_packet()
    dossier = run_ablation(
        packet, ReplayProvider(), "B2", allowed_decision_types=case.allowed_decision_types
    ).dossier

    decision = simulated_chair_decision(packet, dossier, [decision_type])

    assert decision.schema_version == "simulated-decision.v2"
    assert decision.action_plan.action_type == action_type
    assert decision.action_plan.owner
    assert decision.action_plan.action
    assert decision.action_plan.due_at_step >= packet.current_step
    assert decision.action_plan.trigger
    assert decision.action_plan.verification
    assert decision.action_plan.fallback_action


def test_collect_decision_requires_named_evidence() -> None:
    with pytest.raises(ValueError, match="COLLECT_REQUIRES_EVIDENCE_LIST"):
        SimulatedDecision(
            case_id="CASE-X",
            decision_type=DecisionType.COLLECT_MINIMUM_EVIDENCE,
            rationale="test",
            safeguards=[],
            action_plan=DecisionActionPlan(
                action_type="collect_evidence",
                owner="evidence_owner",
                action="collect",
                due_at_step=15,
                trigger="available",
                verification="packet updated",
                fallback_action="defer",
            ),
            dissent_acknowledged=[],
        )


def test_escalation_requires_target_and_questions() -> None:
    with pytest.raises(ValueError, match="ESCALATE_REQUIRES_TARGET_AND_QUESTIONS"):
        SimulatedDecision(
            case_id="CASE-X",
            decision_type=DecisionType.ESCALATE,
            rationale="test",
            safeguards=[],
            action_plan=DecisionActionPlan(
                action_type="escalate",
                owner="decision_chair",
                action="escalate",
                due_at_step=15,
                trigger="authority boundary",
                verification="response recorded",
                fallback_action="defer",
            ),
            dissent_acknowledged=[],
        )


def test_policy_rejects_action_plan_due_in_the_past() -> None:
    case, packet = case_and_packet()
    result = run_ablation(
        packet, ReplayProvider(), "B3", allowed_decision_types=case.allowed_decision_types
    )
    decision = result.decision.model_copy(
        update={
            "action_plan": result.decision.action_plan.model_copy(
                update={"due_at_step": packet.current_step - 1}
            )
        }
    )

    with pytest.raises(ValueError, match="ACTION_PLAN_DUE_STEP_IN_PAST"):
        validate_decision_policy(
            decision,
            case.allowed_decision_types,
            current_step=packet.current_step,
        )


def test_policy_rejects_incomplete_safeguard() -> None:
    decision = SimulatedDecision(
        case_id="CASE-X",
        decision_type=DecisionType.RUN_REVERSIBLE_TRIAL,
        selected_option_id="OPTION-X",
        rationale="test",
        safeguards=[
            Safeguard(
                safeguard_id="SG-X", metric_id="DDR_BANDWIDTH",
                operator="lte",
                threshold=Quantity(mode=QuantityMode.EXACT, unit="GB/s", value=20),
                check_at_step=15,
                expires_at_step=16,
                violation_action="rollback",
                condition="limited", rollback_trigger="",
                owner="owner", verification="next step",
            )
        ],
        action_plan=DecisionActionPlan(
            action_type="execute",
            owner="owner",
            action="run option",
            due_at_step=15,
            trigger="decision recorded",
            verification="next step",
            fallback_action="rollback",
        ),
        dissent_acknowledged=[],
    )
    with pytest.raises(ValueError, match="INCOMPLETE_SAFEGUARD"):
        validate_decision_policy(decision, [DecisionType.RUN_REVERSIBLE_TRIAL])


def test_policy_rejects_non_executable_guardrail_threshold() -> None:
    decision = SimulatedDecision(
        case_id="CASE-X",
        decision_type=DecisionType.RUN_REVERSIBLE_TRIAL,
        selected_option_id="OPTION-X",
        rationale="test",
        safeguards=[
            Safeguard(
                safeguard_id="SG-X",
                metric_id="DDR_BANDWIDTH",
                operator="lte",
                threshold=Quantity(
                    mode=QuantityMode.RANGE,
                    unit="GB/s",
                    lower_bound=18,
                    upper_bound=20,
                ),
                check_at_step=15,
                expires_at_step=16,
                violation_action="rollback",
                condition="limited",
                rollback_trigger="threshold exceeded",
                owner="owner",
                verification="next step",
            )
        ],
        action_plan=DecisionActionPlan(
            action_type="execute",
            owner="owner",
            action="run option",
            due_at_step=15,
            trigger="decision recorded",
            verification="next step",
            fallback_action="rollback",
        ),
        dissent_acknowledged=[],
    )

    with pytest.raises(ValueError, match="GUARDRAIL_THRESHOLD_NOT_EXACT"):
        validate_decision_policy(decision, [DecisionType.RUN_REVERSIBLE_TRIAL])


def test_chair_output_has_no_hidden_world_fields() -> None:
    case, packet = case_and_packet()
    result = run_ablation(
        packet, ReplayProvider(), "B3", allowed_decision_types=case.allowed_decision_types
    )
    serialized = result.model_dump_json()

    assert "hidden_root_causes" not in serialized
    assert "outcome_paths" not in serialized


def test_each_role_declares_unique_concern() -> None:
    case, packet = case_and_packet()
    result = run_ablation(
        packet, ReplayProvider(), "B2", allowed_decision_types=case.allowed_decision_types
    )
    concerns = [review.unique_concern for review in result.dossier.original_reviews]
    assert all(concerns)
    assert len(set(concerns)) == len(concerns)


def test_runtime_budget_rejects_excessive_output() -> None:
    case, packet = case_and_packet()

    class ExpensiveProvider:
        name = "expensive"

        def review(self, packet, role_id):
            result = ReplayProvider().review(packet, role_id)
            return ProviderReviewResult(
                review=result.review,
                usage=ProviderUsage(output_tokens=10_001),
            )

    with pytest.raises(ValueError, match="AGENT_BUDGET_EXCEEDED:ROLE_OUTPUT_TOKENS"):
        run_ablation(
            packet,
            ExpensiveProvider(),
            "B2",
            allowed_decision_types=case.allowed_decision_types,
            budget=AgentRuntimeBudget(max_output_tokens=20_000),
        )


def test_durable_dossier_run_stores_bounded_logical_steps() -> None:
    fixture = FixtureRepository(ROOT / "fixtures").load_observable("CASE-VR-001")
    cases = InMemoryCaseRepository()
    cases.save(fixture, event_type="fixture_imported", expected_aggregate_version=None)
    runs = InMemoryReviewRunRepository()
    queued = enqueue_dossier_review(
        cases,
        runs,
        case_id=fixture.case_id,
        provider="replay",
        model="replay-v1",
        idempotency_key="dossier-run",
        topology="B3",
    )
    claimed = runs.claim("dossier-worker", 60)
    assert claimed is not None and claimed.run_id == queued.run_id
    result = execute_claimed_run(claimed, cases, ReplayProvider())
    assert isinstance(result, DossierExecution)
    completed = runs.complete(claimed.run_id, "dossier-worker", result)
    assert completed.status.value == "COMPLETED"
    assert len(result.dossier.revised_reviews) == 2
    assert len(runs.accepted_steps) == 9
    assert result.chair_provider_result is not None
    assert runs.chair_checkpoint(queued.run_id) == result.chair_provider_result


def test_simulated_decision_consumes_completed_b2_dossier_run() -> None:
    fixture = FixtureRepository(ROOT / "fixtures").load_observable("CASE-VR-001")
    cases = InMemoryCaseRepository()
    cases.save(fixture, event_type="fixture_imported", expected_aggregate_version=None)
    runs = InMemoryReviewRunRepository()
    client = TestClient(create_app(cases, runs))
    created = client.post(
        f"/api/v1/decision-cases/{fixture.case_id}/review-runs",
        headers={"Idempotency-Key": "api-dossier", "If-Match": '"1"'},
        json={"command_schema_version": "review-run-command.v1", "scope": "dossier"},
    )
    run_id = created.json()["run_id"]
    claimed = runs.claim("worker", 60)
    assert claimed is not None
    result = execute_claimed_run(claimed, cases, ReplayProvider())
    runs.complete(run_id, "worker", result)
    decision = client.post(
        f"/api/v1/decision-cases/{fixture.case_id}/simulated-decisions",
        params={"review_run_id": run_id},
        headers={"Idempotency-Key": "api-chair", "If-Match": '"1"'},
    )
    assert created.json()["run_kind"] == "dossier"
    assert created.json()["topology"] == "B2"
    assert result.topology == "B2"
    assert result.chair_provider_result is None
    assert decision.status_code == 200
    assert decision.json()["topology"] == "B2"
    assert decision.json()["chair_used"] is False
    assert decision.json()["decision"]["decision_source"] == "deterministic_core"
    assert decision.json()["dossier"]["dissent"]
    cases.save(
        fixture,
        event_type="state_changed_after_decision",
        expected_aggregate_version=1,
    )
    replayed = client.post(
        f"/api/v1/decision-cases/{fixture.case_id}/simulated-decisions",
        params={"review_run_id": run_id},
        headers={"Idempotency-Key": "api-chair", "If-Match": '"1"'},
    )
    assert replayed.status_code == 200
    assert replayed.json() == decision.json()


def test_partial_dossier_preserves_completed_roles_and_blocks_chair() -> None:
    fixture = FixtureRepository(ROOT / "fixtures").load_observable("CASE-VR-001")
    cases = InMemoryCaseRepository()
    cases.save(fixture, event_type="fixture_imported", expected_aggregate_version=None)
    runs = InMemoryReviewRunRepository()
    queued = enqueue_dossier_review(
        cases,
        runs,
        case_id=fixture.case_id,
        provider="partial",
        model="partial-v1",
        idempotency_key="partial-dossier",
    )
    claimed = runs.claim("partial-worker", 60)
    assert claimed is not None

    class PartiallyFailingProvider(ReplayProvider):
        name = "partial"

        def review(self, packet, role_id):
            if role_id == "sw":
                raise ConnectionError("synthetic provider failure")
            return super().review(packet, role_id)

    result = execute_claimed_run(claimed, cases, PartiallyFailingProvider())
    assert isinstance(result, DossierExecution)
    completed = runs.complete(queued.run_id, "partial-worker", result)

    assert completed.status.value == "PARTIALLY_COMPLETED"
    assert [failure.role_id for failure in result.failed_roles] == ["sw"]
    assert {review.role_id for review in result.dossier.original_reviews} == {
        "architecture_system",
        "verification_measurement",
        "program_risk",
    }
    client = TestClient(create_app(cases, runs))
    chair = client.post(
        f"/api/v1/decision-cases/{fixture.case_id}/simulated-decisions",
        params={"review_run_id": queued.run_id},
        headers={"Idempotency-Key": "partial-chair", "If-Match": '"1"'},
    )
    assert chair.status_code == 409
    assert chair.json()["detail"]["code"] == "DOSSIER_RUN_NOT_READY"


def test_dossier_fails_when_all_mandatory_roles_fail() -> None:
    case, packet = case_and_packet()

    class FailingProvider:
        name = "failed"

        def review(self, packet, role_id):
            raise ConnectionError(role_id)

    with pytest.raises(RuntimeError, match="ALL_MANDATORY_ROLES_FAILED"):
        run_ablation(
            packet,
            FailingProvider(),
            "B3",
            allowed_decision_types=case.allowed_decision_types,
        )
