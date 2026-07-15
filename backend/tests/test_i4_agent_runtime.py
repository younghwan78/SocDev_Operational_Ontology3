import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Timer
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from soc_ot.agents.contracts import ProviderReviewResult, RoleReview
from soc_ot.agents.providers import ReplayProvider, StructuredReviewError
from soc_ot.agents.runtime import ReviewExecutionError, execute_grounded_review
from soc_ot.api.main import create_app
from soc_ot.application.packets import build_observable_case_packet
from soc_ot.application.repositories import InMemoryCaseRepository, PostgresCaseRepository
from soc_ot.application.review_runs import (
    InMemoryReviewRunRepository,
    PostgresReviewRunRepository,
    ReviewRun,
    RunConflictError,
    enqueue_dossier_review,
    enqueue_role_review,
    execute_claimed_run,
)
from soc_ot.domain.models import DecisionType
from soc_ot.infrastructure.database import get_runtime_engine
from soc_ot.infrastructure.fixtures import FixtureRepository
from soc_ot.infrastructure.tables import AgentAttemptRow, AgentRunRow, AgentRunStepRow
from soc_ot.worker.main import execute_with_lease_heartbeat

ROOT = Path(__file__).resolve().parents[2]


def setup_repositories() -> tuple[InMemoryCaseRepository, InMemoryReviewRunRepository]:
    fixture = FixtureRepository(ROOT / "fixtures").load_observable("CASE-VR-001")
    cases = InMemoryCaseRepository()
    cases.save(fixture, event_type="fixture_imported", expected_aggregate_version=None)
    return cases, InMemoryReviewRunRepository()


def test_replay_provider_is_deterministic_and_grounded() -> None:
    case = FixtureRepository(ROOT / "fixtures").load_observable("CASE-VR-001")
    packet = build_observable_case_packet(case)
    provider = ReplayProvider()

    first = provider.review(packet, packet.selected_role_ids[0])
    second = provider.review(packet, packet.selected_role_ids[0])

    assert first == second
    assert set(first.review.rationale_claim_ids) <= {item.claim_id for item in packet.claims}


def test_idempotent_enqueue_claim_and_duplicate_completion() -> None:
    cases, runs = setup_repositories()
    kwargs = dict(
        case_id="CASE-VR-001", role_id=cases.get("CASE-VR-001").case.required_role_ids[0],
        provider="replay", model="replay-v1", idempotency_key="same-command",
    )
    first = enqueue_role_review(cases, runs, **kwargs)
    second = enqueue_role_review(cases, runs, **kwargs)
    claimed = runs.claim("worker-1", 60)
    assert claimed is not None
    result = execute_claimed_run(claimed, cases, ReplayProvider())
    completed = runs.complete(claimed.run_id, "worker-1", result)

    assert first.run_id == second.run_id
    assert completed.status.value == "COMPLETED"
    assert completed.returned_model == "replay-v1"
    assert completed.prompt_bundle_version == "prompts.v2"
    assert len(completed.prompt_bundle_hash) == 64
    with pytest.raises(RunConflictError, match="RUN_LEASE_NOT_OWNED"):
        runs.complete(claimed.run_id, "worker-1", result)


def test_expired_lease_is_reclaimed_and_cancellation_wins_race() -> None:
    cases, runs = setup_repositories()
    role_id = cases.get("CASE-VR-001").case.required_role_ids[0]
    queued = enqueue_role_review(
        cases, runs, case_id="CASE-VR-001", role_id=role_id,
        provider="replay", model="replay-v1", idempotency_key="lease-test",
    )
    claimed = runs.claim("dead-worker", 60)
    assert claimed is not None
    runs.leases[queued.run_id] = ("dead-worker", datetime.now(UTC) - timedelta(seconds=1))
    reclaimed = runs.claim("new-worker", 60)
    assert reclaimed is not None and reclaimed.attempt_no == 2
    runs.cancel(reclaimed.run_id)
    result = execute_claimed_run(reclaimed, cases, ReplayProvider())
    with pytest.raises(RunConflictError, match="RUN_LEASE_NOT_OWNED"):
        runs.complete(reclaimed.run_id, "new-worker", result)


def test_heartbeat_extends_lease_and_explicit_retry_creates_new_run() -> None:
    cases, runs = setup_repositories()
    role_id = cases.get("CASE-VR-001").case.required_role_ids[0]
    queued = enqueue_role_review(
        cases, runs, case_id="CASE-VR-001", role_id=role_id,
        provider="replay", model="replay-v1", idempotency_key="heartbeat-test",
    )
    claimed = runs.claim("worker", 1)
    assert claimed is not None
    previous_expiry = claimed.lease_expires_at
    heartbeat = runs.heartbeat(queued.run_id, "worker", 2)
    assert heartbeat.heartbeat_at is not None
    assert previous_expiry is not None and heartbeat.lease_expires_at > previous_expiry
    failed = runs.fail(queued.run_id, "worker", "TERMINAL", retryable=False)
    retried = runs.retry(failed.run_id, idempotency_key="manual-retry")
    assert retried.run_id != failed.run_id
    assert retried.status.value == "QUEUED"
    assert retried.attempt_no == 0


def test_idempotency_key_reuse_with_different_command_fails() -> None:
    cases, runs = setup_repositories()
    roles = cases.get("CASE-VR-001").case.required_role_ids
    enqueue_role_review(
        cases, runs, case_id="CASE-VR-001", role_id=roles[0],
        provider="replay", model="replay-v1", idempotency_key="reused-key",
    )
    with pytest.raises(RunConflictError, match="IDEMPOTENCY_KEY_REUSED"):
        enqueue_role_review(
            cases, runs, case_id="CASE-VR-001", role_id=roles[1],
            provider="replay", model="replay-v1", idempotency_key="reused-key",
        )


def test_role_timeout_is_enforced_before_slow_provider_returns() -> None:
    cases, runs = setup_repositories()
    role_id = cases.get("CASE-VR-001").case.required_role_ids[0]
    enqueue_role_review(
        cases, runs, case_id="CASE-VR-001", role_id=role_id,
        provider="slow", model="slow", idempotency_key="timeout-test",
    )
    claimed = runs.claim("worker", 1)
    assert claimed is not None

    class SlowProvider:
        name = "slow"

        def review(self, packet, role_id):
            time.sleep(0.1)
            return ReplayProvider().review(packet, role_id)

    started = time.monotonic()
    with pytest.raises(TimeoutError, match="ROLE_TIMEOUT"):
        execute_with_lease_heartbeat(
            claimed,
            cases,
            runs,
            SlowProvider(),
            worker_id="worker",
            timeout_seconds=0.02,
            lease_seconds=1,
            heartbeat_interval_seconds=0.005,
        )
    assert time.monotonic() - started < 0.08


def test_unsupported_authoritative_claim_is_rejected() -> None:
    cases, runs = setup_repositories()
    role_id = cases.get("CASE-VR-001").case.required_role_ids[0]
    enqueue_role_review(
        cases, runs, case_id="CASE-VR-001", role_id=role_id,
        provider="replay", model="bad", idempotency_key="bad-grounding",
    )
    claimed = runs.claim("worker", 60)
    assert claimed is not None

    class BadProvider:
        name = "bad"

        def review(self, packet: object, role_id: str) -> ProviderReviewResult:
            return ProviderReviewResult(
                review=RoleReview(
                    role_id=role_id,
                    recommendation=DecisionType.COLLECT_MINIMUM_EVIDENCE,
                    rationale="근거 없는 단정",
                    rationale_claim_ids=["CLAIM-DOES-NOT-EXIST"],
                    risks=[], information_gaps=[], confidence="high",
                    unique_concern="근거 없이 단정한 concern",
                )
            )

    with pytest.raises(ReviewExecutionError, match="POLICY_RETRY_EXHAUSTED"):
        execute_claimed_run(claimed, cases, BadProvider())


def test_transport_schema_and_policy_retries_are_bounded_and_audited() -> None:
    case = FixtureRepository(ROOT / "fixtures").load_observable("CASE-VR-001")
    packet = build_observable_case_packet(case)
    role_id = packet.selected_role_ids[0]

    class TransientProvider(ReplayProvider):
        calls = 0

        def review(self, packet, role_id):
            self.calls += 1
            if self.calls == 1:
                raise ConnectionError("synthetic transient")
            return super().review(packet, role_id)

    transport_attempts = []
    transport = execute_grounded_review(
        packet,
        role_id,
        TransientProvider(),
        validator=lambda _result: None,
        max_provider_attempts=3,
        attempt_sink=transport_attempts.append,
    )
    assert transport.usage.provider_attempts == 2
    transport_final = list(
        {item.attempt_id: item for item in transport_attempts}.values()
    )
    assert [item.final_status for item in transport_final] == [
        "retryable_failed",
        "accepted",
    ]
    assert transport_final[1].retry_reason == "transport_error"

    class SchemaRepairProvider(ReplayProvider):
        feedback: str | None = None

        def review(self, packet, role_id):
            raise StructuredReviewError("SYNTHETIC_SCHEMA_INVALID")

        def review_with_feedback(self, packet, role_id, feedback):
            self.feedback = feedback
            return super().review(packet, role_id)

    schema_provider = SchemaRepairProvider()
    schema_attempts = []
    repaired = execute_grounded_review(
        packet,
        role_id,
        schema_provider,
        validator=lambda _result: None,
        max_provider_attempts=3,
        attempt_sink=schema_attempts.append,
    )
    assert repaired.usage.provider_attempts == 2
    assert schema_provider.feedback and "valid RoleReview" in schema_provider.feedback
    schema_final = list({item.attempt_id: item for item in schema_attempts}.values())
    assert schema_final[1].retry_reason == "schema_invalid"

    class PolicyRepairProvider(ReplayProvider):
        def review(self, packet, role_id):
            valid = super().review(packet, role_id)
            return valid.model_copy(
                update={
                    "review": valid.review.model_copy(
                        update={"rationale_claim_ids": ["UNKNOWN-CLAIM"]}
                    )
                }
            )

        def review_with_feedback(self, packet, role_id, feedback):
            return super().review(packet, role_id)

    policy_attempts = []
    corrected = execute_grounded_review(
        packet,
        role_id,
        PolicyRepairProvider(),
        validator=lambda result: (
            None
            if set(result.review.rationale_claim_ids)
            <= {claim.claim_id for claim in packet.claims}
            else (_ for _ in ()).throw(ValueError("UNSUPPORTED_AUTHORITATIVE_CLAIM"))
        ),
        max_provider_attempts=3,
        attempt_sink=policy_attempts.append,
    )
    assert corrected.usage.provider_attempts == 2
    policy_final = list({item.attempt_id: item for item in policy_attempts}.values())
    assert policy_final[1].retry_reason == "policy_violation"


def test_provider_call_timeout_is_terminal_and_audited() -> None:
    case = FixtureRepository(ROOT / "fixtures").load_observable("CASE-VR-001")
    packet = build_observable_case_packet(case)
    attempts = []

    class SlowProvider(ReplayProvider):
        def review(self, packet, role_id):
            time.sleep(0.05)
            return super().review(packet, role_id)

    with pytest.raises(ReviewExecutionError, match="ROLE_TIMEOUT"):
        execute_grounded_review(
            packet,
            packet.selected_role_ids[0],
            SlowProvider(),
            validator=lambda _result: None,
            max_provider_attempts=3,
            attempt_sink=attempts.append,
            timeout_seconds=0.005,
        )
    final_attempts = list({item.attempt_id: item for item in attempts}.values())
    assert len(final_attempts) == 1
    assert final_attempts[0].validation_result == "ROLE_TIMEOUT"
    assert final_attempts[0].final_status == "failed"


def test_late_provider_response_after_cancel_is_audited_as_discarded() -> None:
    cases, runs = setup_repositories()
    role_id = cases.get("CASE-VR-001").case.required_role_ids[0]
    queued = enqueue_role_review(
        cases,
        runs,
        case_id="CASE-VR-001",
        role_id=role_id,
        provider="slow",
        model="slow-v1",
        idempotency_key="late-after-cancel",
    )
    claimed = runs.claim("cancel-worker", 60)
    assert claimed is not None

    class SlowProvider(ReplayProvider):
        def review(self, packet, role_id):
            time.sleep(0.05)
            return super().review(packet, role_id)

    cancel = Timer(0.01, lambda: runs.cancel(queued.run_id))
    cancel.start()
    try:
        with pytest.raises(RunConflictError, match="RUN_CANCELLED_DURING_EXECUTION"):
            execute_with_lease_heartbeat(
                claimed,
                cases,
                runs,
                SlowProvider(),
                worker_id="cancel-worker",
                timeout_seconds=1,
                lease_seconds=60,
                heartbeat_interval_seconds=0.005,
            )
    finally:
        cancel.join()
    time.sleep(0.06)
    assert runs.attempt_log[queued.run_id][0].final_status == "discarded_after_cancel"


def test_dossier_reclaim_resumes_role_checkpoints_and_counts_abandoned_attempt() -> None:
    cases, runs = setup_repositories()
    queued = enqueue_dossier_review(
        cases,
        runs,
        case_id="CASE-VR-001",
        provider="crashing",
        model="crashing-v1",
        idempotency_key="dossier-checkpoint-crash",
        topology="B3",
    )
    claimed = runs.claim("crashing-worker", 60)
    assert claimed is not None
    role_ids = cases.get("CASE-VR-001").case.required_role_ids

    class CrashDuringSecondRole(ReplayProvider):
        def review(self, packet, role_id):
            if role_id == role_ids[1]:
                raise KeyboardInterrupt("synthetic worker crash")
            return super().review(packet, role_id)

    with pytest.raises(KeyboardInterrupt, match="synthetic worker crash"):
        execute_claimed_run(
            claimed,
            cases,
            CrashDuringSecondRole(),
            lambda attempt: runs.record_attempt(queued.run_id, attempt),
            {},
            lambda result, review_round: runs.save_review_checkpoint(
                queued.run_id, "crashing-worker", result, review_round
            ),
            0,
        )
    assert [item.review.role_id for item in runs.review_checkpoints(queued.run_id)] == [
        role_ids[0]
    ]
    assert runs.attempt_count(queued.run_id) == 2
    assert any(
        item.final_status == "running" for item in runs.attempt_log[queued.run_id]
    )

    runs.leases[queued.run_id] = (
        "crashing-worker",
        datetime.now(UTC) - timedelta(seconds=1),
    )
    reclaimed = runs.claim("recovery-worker", 60)
    assert reclaimed is not None and reclaimed.run_id == queued.run_id
    resumed_calls: list[str] = []
    revision_calls: list[str] = []

    class CountingProvider(ReplayProvider):
        def review(self, packet, role_id):
            resumed_calls.append(role_id)
            return super().review(packet, role_id)

        def review_with_feedback(self, packet, role_id, feedback):
            revision_calls.append(role_id)
            return ReplayProvider().review_with_feedback(
                packet, role_id, feedback
            )

    checkpoints = {
        item.review.role_id: item for item in runs.review_checkpoints(queued.run_id)
    }
    result = execute_claimed_run(
        reclaimed,
        cases,
        CountingProvider(),
        lambda attempt: runs.record_attempt(queued.run_id, attempt),
        checkpoints,
        lambda accepted, review_round: runs.save_review_checkpoint(
            queued.run_id, "recovery-worker", accepted, review_round
        ),
        runs.attempt_count(queued.run_id),
    )
    completed = runs.complete(queued.run_id, "recovery-worker", result)

    assert completed.status.value == "COMPLETED"
    assert role_ids[0] not in resumed_calls
    assert set(resumed_calls) == set(role_ids[1:])
    assert revision_calls == role_ids[:2]
    assert result.provider_attempts == 9
    assert all(
        item.final_status != "running" for item in runs.attempt_log[queued.run_id]
    )
    assert len(runs.accepted_steps) == 9


def test_review_run_api_supports_polling_and_sse() -> None:
    cases, runs = setup_repositories()
    client = TestClient(create_app(cases, runs))

    created = client.post(
        "/api/v1/decision-cases/CASE-VR-001/review-runs",
        headers={"Idempotency-Key": "api-test", "If-Match": '"1"'},
    )
    run_id = created.json()["run_id"]
    polled = client.get(f"/api/v1/runs/{run_id}")
    events = client.get(f"/api/v1/runs/{run_id}/events?follow=false")

    assert created.status_code == 200
    assert polled.json()["status"] == "QUEUED"
    assert events.headers["content-type"].startswith("text/event-stream")
    assert "run.queued" in events.text
    assert created.json()["status_url"] == f"/api/v1/runs/{run_id}"
    assert created.json()["topology"] == "B2"
    assert created.json()["budget_plan"] == {
        "max_logical_calls": 9,
        "reserved_logical_calls": 4,
        "remaining_logical_calls": 5,
        "max_provider_attempts": 12,
        "reserved_provider_attempts": 4,
        "remaining_provider_attempts": 8,
        "max_output_tokens": 20_000,
        "reserved_output_tokens": 6_000,
        "remaining_output_tokens": 14_000,
        "timeout_envelope_seconds": 900,
        "maximum_cost_usd": 2.0,
    }
    cancelled = client.post(
        f"/api/v1/runs/{run_id}/cancel",
        headers={"Idempotency-Key": "api-cancel", "If-Match": '"1"'},
    )
    retried = client.post(
        f"/api/v1/runs/{run_id}/retry",
        headers={"Idempotency-Key": "api-retry", "If-Match": '"1"'},
    )
    assert cancelled.json()["status"] == "CANCELLED"
    assert retried.status_code == 200
    assert retried.json()["run_id"] != run_id
    assert retried.json()["topology"] == "B2"


def test_command_rejects_outdated_aggregate_version() -> None:
    cases, runs = setup_repositories()
    client = TestClient(create_app(cases, runs))
    response = client.post(
        "/api/v1/decision-cases/CASE-VR-001/review-runs",
        headers={"Idempotency-Key": "stale", "If-Match": '"0"'},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CASE_VERSION_CONFLICT"


@pytest.mark.postgres
def test_postgres_crash_after_provider_response_accepts_one_logical_step() -> None:
    engine = get_runtime_engine()
    cases = PostgresCaseRepository(engine)
    runs = PostgresReviewRunRepository(engine)
    stored = cases.get("CASE-VR-001")
    assert stored is not None
    role_id = stored.case.required_role_ids[0]
    queued = enqueue_role_review(
        cases,
        runs,
        case_id=stored.case.case_id,
        role_id=role_id,
        provider="replay",
        model="replay-v1",
        idempotency_key=f"pg-crash-{uuid4()}",
    )
    claimed = _claim_target(runs, queued.run_id, "worker-before-crash")
    execute_claimed_run(claimed, cases, ReplayProvider())
    with Session(engine) as session, session.begin():
        session.execute(
            update(AgentRunRow)
            .where(AgentRunRow.run_id == queued.run_id)
            .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    reclaimed = _claim_target(runs, queued.run_id, "worker-after-crash")
    accepted = execute_claimed_run(reclaimed, cases, ReplayProvider())
    completed = runs.complete(reclaimed.run_id, "worker-after-crash", accepted)
    assert completed.status.value == "COMPLETED"
    with Session(engine) as session:
        step_count = session.scalar(
            select(func.count(AgentRunStepRow.step_id)).where(
                AgentRunStepRow.run_id == queued.run_id
            )
        )
    assert step_count == 1


@pytest.mark.postgres
def test_postgres_worker_records_redacted_attempt_audit() -> None:
    engine = get_runtime_engine()
    cases = PostgresCaseRepository(engine)
    runs = PostgresReviewRunRepository(engine)
    stored = cases.get("CASE-VR-001")
    assert stored is not None
    queued = enqueue_role_review(
        cases,
        runs,
        case_id=stored.case.case_id,
        role_id=stored.case.required_role_ids[0],
        provider="replay",
        model="replay-v1",
        idempotency_key=f"pg-attempt-{uuid4()}",
    )
    claimed = _claim_target(runs, queued.run_id, "audit-worker")
    result = execute_with_lease_heartbeat(
        claimed,
        cases,
        runs,
        ReplayProvider(),
        worker_id="audit-worker",
        timeout_seconds=2,
        lease_seconds=60,
    )
    runs.complete(queued.run_id, "audit-worker", result)

    with Session(engine) as session:
        attempts = session.scalars(
            select(AgentAttemptRow).where(AgentAttemptRow.run_id == queued.run_id)
        ).all()
    assert len(attempts) == 1
    assert attempts[0].final_status == "accepted"
    assert attempts[0].requested_model == "replay-v1"
    assert attempts[0].observable_packet_hash == queued.packet_hash
    assert attempts[0].validation_result == "accepted"


@pytest.mark.postgres
def test_postgres_dossier_reclaim_skips_checkpointed_role() -> None:
    engine = get_runtime_engine()
    cases = PostgresCaseRepository(engine)
    runs = PostgresReviewRunRepository(engine)
    stored = cases.get("CASE-VR-001")
    assert stored is not None
    queued = enqueue_dossier_review(
        cases,
        runs,
        case_id=stored.case.case_id,
        provider="crashing",
        model="crashing-v1",
        idempotency_key=f"pg-dossier-checkpoint-{uuid4()}",
        topology="B3",
    )
    first_claim = _claim_target(runs, queued.run_id, "pg-crash-worker")
    assert queued.topology == first_claim.topology == "B3"
    role_ids = stored.case.required_role_ids

    class CrashDuringSecondRole(ReplayProvider):
        def review(self, packet, role_id):
            if role_id == role_ids[1]:
                raise KeyboardInterrupt("synthetic postgres worker crash")
            return super().review(packet, role_id)

    with pytest.raises(KeyboardInterrupt, match="synthetic postgres worker crash"):
        execute_claimed_run(
            first_claim,
            cases,
            CrashDuringSecondRole(),
            lambda attempt: runs.record_attempt(queued.run_id, attempt),
            {},
            lambda result, review_round: runs.save_review_checkpoint(
                queued.run_id, "pg-crash-worker", result, review_round
            ),
            0,
        )
    with Session(engine) as session, session.begin():
        session.execute(
            update(AgentRunRow)
            .where(AgentRunRow.run_id == queued.run_id)
            .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
    reclaimed = _claim_target(runs, queued.run_id, "pg-recovery-worker")
    assert reclaimed.topology == "B3"
    resumed_calls: list[str] = []
    revision_calls: list[str] = []

    class CountingProvider(ReplayProvider):
        def review(self, packet, role_id):
            resumed_calls.append(role_id)
            return super().review(packet, role_id)

        def review_with_feedback(self, packet, role_id, feedback):
            revision_calls.append(role_id)
            return ReplayProvider().review_with_feedback(
                packet, role_id, feedback
            )

    checkpoints = {
        item.review.role_id: item for item in runs.review_checkpoints(queued.run_id)
    }
    result = execute_claimed_run(
        reclaimed,
        cases,
        CountingProvider(),
        lambda attempt: runs.record_attempt(queued.run_id, attempt),
        checkpoints,
        lambda accepted, review_round: runs.save_review_checkpoint(
            queued.run_id, "pg-recovery-worker", accepted, review_round
        ),
        runs.attempt_count(queued.run_id),
    )
    runs.complete(queued.run_id, "pg-recovery-worker", result)

    with Session(engine) as session:
        role_step_count = session.scalar(
            select(func.count(AgentRunStepRow.step_id)).where(
                AgentRunStepRow.run_id == queued.run_id,
                AgentRunStepRow.step_kind == "role_review",
                AgentRunStepRow.review_round == 0,
            )
        )
        attempts = session.scalars(
            select(AgentAttemptRow).where(AgentAttemptRow.run_id == queued.run_id)
        ).all()
    assert role_ids[0] not in resumed_calls
    assert set(resumed_calls) == set(role_ids[1:])
    assert revision_calls == role_ids[:2]
    assert role_step_count == len(role_ids)
    assert len(attempts) == 9
    assert all(item.final_status != "running" for item in attempts)


def _claim_target(
    runs: PostgresReviewRunRepository, run_id: str, worker_id: str
) -> ReviewRun:
    for _ in range(20):
        claimed = runs.claim(worker_id, 60)
        assert claimed is not None
        if claimed.run_id == run_id:
            return claimed
        runs.cancel(claimed.run_id)
    raise AssertionError("target run was not claimable")
