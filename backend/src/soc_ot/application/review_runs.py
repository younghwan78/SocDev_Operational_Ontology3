from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol, cast
from uuid import uuid4

from pydantic import TypeAdapter
from sqlalchemy import func, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from soc_ot.agents.contracts import (
    AgentRunBudgetPlan,
    ProviderAttemptMetadata,
    ProviderReviewResult,
)
from soc_ot.agents.multi_role import (
    ChairProviderResult,
    ChallengerProviderResult,
    DossierExecution,
)
from soc_ot.agents.prompts import PROMPT_BUNDLE_HASH, PROMPT_BUNDLE_VERSION
from soc_ot.agents.providers import ReviewProvider
from soc_ot.agents.runtime import AttemptSink, execute_grounded_review
from soc_ot.application.multi_role import (
    RELEASE_DOSSIER_TOPOLOGY,
    AgentRuntimeBudget,
    ChairCheckpointSink,
    ChallengerCheckpointSink,
    DossierTopology,
    ReviewCheckpointSink,
    run_dossier_round,
)
from soc_ot.application.packets import build_observable_case_packet
from soc_ot.application.repositories import CaseRepository
from soc_ot.domain.models import AgentRunStatus
from soc_ot.infrastructure.tables import (
    AgentAttemptRow,
    AgentRunEventRow,
    AgentRunRow,
    AgentRunStepRow,
)

AgentRunResult = ProviderReviewResult | DossierExecution
RESULT_ADAPTER: TypeAdapter[AgentRunResult] = TypeAdapter(AgentRunResult)


@dataclass(frozen=True)
class ReviewRun:
    run_id: str
    run_kind: Literal["role_review", "dossier"]
    topology: DossierTopology | None
    case_id: str
    packet_hash: str
    role_id: str
    provider: str
    requested_model: str
    returned_model: str | None
    contract_version: str
    prompt_bundle_version: str
    prompt_bundle_hash: str
    policy_version: str
    budget_plan: AgentRunBudgetPlan
    status: AgentRunStatus
    attempt_no: int
    max_attempts: int
    actor_id: str = "local-home-reviewer"
    cancel_requested: bool = False
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    heartbeat_at: datetime | None = None
    next_retry_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    result: AgentRunResult | None = None
    error_code: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RunConflictError(ValueError):
    pass


class ReviewRunRepository(Protocol):
    def enqueue(self, run: ReviewRun, *, idempotency_key: str) -> ReviewRun: ...
    def get(self, run_id: str) -> ReviewRun | None: ...
    def latest_for_case(
        self,
        case_id: str,
        *,
        run_kind: Literal["role_review", "dossier"] | None = None,
    ) -> ReviewRun | None: ...
    def claim(self, worker_id: str, lease_seconds: int) -> ReviewRun | None: ...
    def heartbeat(self, run_id: str, worker_id: str, lease_seconds: int) -> ReviewRun: ...
    def complete(self, run_id: str, worker_id: str, result: AgentRunResult) -> ReviewRun: ...
    def fail(
        self,
        run_id: str,
        worker_id: str,
        error_code: str,
        retryable: bool,
        retry_delay_seconds: int = 1,
    ) -> ReviewRun: ...
    def cancel(self, run_id: str) -> ReviewRun: ...
    def retry(self, run_id: str, *, idempotency_key: str) -> ReviewRun: ...
    def events(self, run_id: str) -> list[dict[str, object]]: ...
    def telemetry(self) -> dict[str, int | float]: ...
    def record_attempt(self, run_id: str, attempt: ProviderAttemptMetadata) -> None: ...
    def attempt_count(self, run_id: str) -> int: ...
    def review_checkpoints(
        self, run_id: str, review_round: int = 0
    ) -> list[ProviderReviewResult]: ...
    def save_review_checkpoint(
        self,
        run_id: str,
        worker_id: str,
        result: ProviderReviewResult,
        review_round: int = 0,
    ) -> None: ...
    def challenger_checkpoint(self, run_id: str) -> ChallengerProviderResult | None: ...
    def save_challenger_checkpoint(
        self, run_id: str, worker_id: str, result: ChallengerProviderResult
    ) -> None: ...
    def chair_checkpoint(self, run_id: str) -> ChairProviderResult | None: ...
    def save_chair_checkpoint(
        self, run_id: str, worker_id: str, result: ChairProviderResult
    ) -> None: ...


class InMemoryReviewRunRepository:
    def __init__(self) -> None:
        self.items: dict[str, ReviewRun] = {}
        self.keys: dict[str, str] = {}
        self.leases: dict[str, tuple[str, datetime]] = {}
        self.event_log: dict[str, list[dict[str, object]]] = {}
        self.accepted_steps: dict[tuple[str, str, str, int], object] = {}
        self.attempt_log: dict[str, list[ProviderAttemptMetadata]] = {}

    def enqueue(self, run: ReviewRun, *, idempotency_key: str) -> ReviewRun:
        existing = self.keys.get(idempotency_key)
        if existing:
            current = self.items[existing]
            if _command_fingerprint(current) != _command_fingerprint(run):
                raise RunConflictError("IDEMPOTENCY_KEY_REUSED")
            return current
        self.items[run.run_id] = run
        self.keys[idempotency_key] = run.run_id
        self._event(run.run_id, "run.queued")
        return run

    def get(self, run_id: str) -> ReviewRun | None:
        return self.items.get(run_id)

    def latest_for_case(
        self,
        case_id: str,
        *,
        run_kind: Literal["role_review", "dossier"] | None = None,
    ) -> ReviewRun | None:
        matches = [
            item
            for item in self.items.values()
            if item.case_id == case_id and (run_kind is None or item.run_kind == run_kind)
        ]
        return max(matches, key=lambda item: (item.created_at, item.run_id), default=None)

    def claim(self, worker_id: str, lease_seconds: int) -> ReviewRun | None:
        now = datetime.now(UTC)
        for run_id in sorted(self.items):
            run = self.items[run_id]
            lease = self.leases.get(run_id)
            eligible = run.status is AgentRunStatus.QUEUED or (
                run.status is AgentRunStatus.RUNNING and lease is not None and lease[1] <= now
            )
            retry_ready = run.next_retry_at is None or run.next_retry_at <= now
            if (
                eligible
                and retry_ready
                and not run.cancel_requested
                and run.attempt_no < run.max_attempts
            ):
                if run.status is AgentRunStatus.RUNNING:
                    self._close_abandoned_attempts(run_id, now)
                expires_at = now + timedelta(seconds=lease_seconds)
                claimed = _replace_run(
                    run,
                    status=AgentRunStatus.RUNNING,
                    attempt_no=run.attempt_no + 1,
                    lease_owner=worker_id,
                    lease_expires_at=expires_at,
                    heartbeat_at=now,
                    next_retry_at=None,
                )
                self.items[run_id] = claimed
                self.leases[run_id] = (worker_id, expires_at)
                self._event(run_id, "run.claimed")
                return claimed
        return None

    def heartbeat(self, run_id: str, worker_id: str, lease_seconds: int) -> ReviewRun:
        run = self._require_owned(run_id, worker_id)
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=lease_seconds)
        updated = _replace_run(run, heartbeat_at=now, lease_expires_at=expires_at)
        self.items[run_id] = updated
        self.leases[run_id] = (worker_id, expires_at)
        self._event(run_id, "run.heartbeat")
        return updated

    def complete(self, run_id: str, worker_id: str, result: AgentRunResult) -> ReviewRun:
        run = self._require_owned(run_id, worker_id)
        if run.cancel_requested:
            raise RunConflictError("RUN_CANCELLED_DURING_EXECUTION")
        final_status = (
            AgentRunStatus.PARTIALLY_COMPLETED
            if isinstance(result, DossierExecution) and result.failed_roles
            else AgentRunStatus.COMPLETED
        )
        completed = _replace_run(
            run,
            status=final_status,
            result=result,
            returned_model=_returned_model(result),
            lease_owner=None,
            lease_expires_at=None,
        )
        self.items[run_id] = completed
        for step_key, normalized in _logical_steps(run, result):
            existing = self.accepted_steps.get(step_key)
            if existing is not None and existing != normalized:
                raise RunConflictError("LOGICAL_STEP_ALREADY_ACCEPTED")
            self.accepted_steps[step_key] = normalized
        self.leases.pop(run_id, None)
        self._event(
            run_id,
            "run.partially_completed"
            if final_status is AgentRunStatus.PARTIALLY_COMPLETED
            else "run.completed",
        )
        return completed

    def fail(
        self,
        run_id: str,
        worker_id: str,
        error_code: str,
        retryable: bool,
        retry_delay_seconds: int = 1,
    ) -> ReviewRun:
        run = self._require_owned(run_id, worker_id)
        status = (
            AgentRunStatus.QUEUED
            if retryable and run.attempt_no < run.max_attempts
            else AgentRunStatus.FAILED
        )
        next_retry_at = (
            datetime.now(UTC) + timedelta(seconds=retry_delay_seconds)
            if status is AgentRunStatus.QUEUED
            else None
        )
        failed = _replace_run(
            run,
            status=status,
            error_code=error_code,
            lease_owner=None,
            lease_expires_at=None,
            next_retry_at=next_retry_at,
        )
        self.items[run_id] = failed
        self.leases.pop(run_id, None)
        self._event(run_id, "run.retry_queued" if status is AgentRunStatus.QUEUED else "run.failed")
        return failed

    def cancel(self, run_id: str) -> ReviewRun:
        run = self.items[run_id]
        cancelled = _replace_run(
            run,
            status=AgentRunStatus.CANCELLED,
            cancel_requested=True,
            cancel_requested_at=datetime.now(UTC),
            lease_owner=None,
            lease_expires_at=None,
        )
        self.items[run_id] = cancelled
        self.leases.pop(run_id, None)
        self._event(run_id, "run.cancel_requested")
        return cancelled

    def retry(self, run_id: str, *, idempotency_key: str) -> ReviewRun:
        failed = self.items[run_id]
        if failed.status not in {
            AgentRunStatus.PARTIALLY_COMPLETED,
            AgentRunStatus.FAILED,
            AgentRunStatus.CANCELLED,
        }:
            raise RunConflictError("RUN_NOT_RETRYABLE")
        return self.enqueue(
            ReviewRun(
                run_id=str(uuid4()),
                run_kind=failed.run_kind,
                topology=failed.topology,
                case_id=failed.case_id,
                packet_hash=failed.packet_hash,
                role_id=failed.role_id,
                provider=failed.provider,
                requested_model=failed.requested_model,
                returned_model=None,
                contract_version=failed.contract_version,
                prompt_bundle_version=failed.prompt_bundle_version,
                prompt_bundle_hash=failed.prompt_bundle_hash,
                policy_version=failed.policy_version,
                budget_plan=failed.budget_plan,
                status=AgentRunStatus.QUEUED,
                attempt_no=0,
                max_attempts=failed.max_attempts,
                actor_id=failed.actor_id,
            ),
            idempotency_key=idempotency_key,
        )

    def events(self, run_id: str) -> list[dict[str, object]]:
        return list(self.event_log.get(run_id, []))

    def telemetry(self) -> dict[str, int | float]:
        completed = [item for item in self.items.values() if item.result is not None]
        return {
            "run_count": len(self.items),
            "completed_count": len(completed),
            "input_tokens": sum(_result_usage(item.result)[0] for item in completed),
            "output_tokens": sum(_result_usage(item.result)[1] for item in completed),
            "estimated_cost_usd": sum(_result_usage(item.result)[2] for item in completed),
            "provider_attempts": sum(len(items) for items in self.attempt_log.values()),
        }

    def record_attempt(self, run_id: str, attempt: ProviderAttemptMetadata) -> None:
        run = self.items[run_id]
        effective = attempt.model_copy(
            update={
                "final_status": (
                    "discarded_after_cancel"
                    if run.cancel_requested or run.status is not AgentRunStatus.RUNNING
                    else attempt.final_status
                ),
            }
        )
        attempts = self.attempt_log.setdefault(run_id, [])
        for index, current in enumerate(attempts):
            if current.attempt_id == effective.attempt_id:
                attempts[index] = effective
                break
        else:
            attempts.append(effective)

    def attempt_count(self, run_id: str) -> int:
        return len(self.attempt_log.get(run_id, []))

    def review_checkpoints(
        self, run_id: str, review_round: int = 0
    ) -> list[ProviderReviewResult]:
        results = []
        for (
            saved_run_id,
            step_kind,
            _role_id,
            saved_round,
        ), value in self.accepted_steps.items():
            if (
                saved_run_id != run_id
                or step_kind != "role_review"
                or saved_round != review_round
            ):
                continue
            if isinstance(value, dict) and "review" in value:
                results.append(ProviderReviewResult.model_validate(value))
        return results

    def save_review_checkpoint(
        self,
        run_id: str,
        worker_id: str,
        result: ProviderReviewResult,
        review_round: int = 0,
    ) -> None:
        self._require_owned(run_id, worker_id)
        key = (run_id, "role_review", result.review.role_id, review_round)
        normalized = result.model_dump(mode="json")
        existing = self.accepted_steps.get(key)
        if existing is not None and existing != normalized:
            raise RunConflictError("LOGICAL_STEP_ALREADY_ACCEPTED")
        self.accepted_steps[key] = normalized

    def challenger_checkpoint(self, run_id: str) -> ChallengerProviderResult | None:
        value = self.accepted_steps.get((run_id, "challenger", "challenger", 0))
        if isinstance(value, dict) and "challenger" in value:
            return ChallengerProviderResult.model_validate(value)
        return None

    def save_challenger_checkpoint(
        self, run_id: str, worker_id: str, result: ChallengerProviderResult
    ) -> None:
        self._require_owned(run_id, worker_id)
        key = (run_id, "challenger", "challenger", 0)
        normalized = result.model_dump(mode="json")
        existing = self.accepted_steps.get(key)
        if existing is not None and existing != normalized:
            raise RunConflictError("LOGICAL_STEP_ALREADY_ACCEPTED")
        self.accepted_steps[key] = normalized

    def chair_checkpoint(self, run_id: str) -> ChairProviderResult | None:
        value = self.accepted_steps.get((run_id, "chair", "decision_chair", 0))
        if isinstance(value, dict) and "decision" in value:
            return ChairProviderResult.model_validate(value)
        return None

    def save_chair_checkpoint(
        self, run_id: str, worker_id: str, result: ChairProviderResult
    ) -> None:
        self._require_owned(run_id, worker_id)
        key = (run_id, "chair", "decision_chair", 0)
        normalized = result.model_dump(mode="json")
        existing = self.accepted_steps.get(key)
        if existing is not None and existing != normalized:
            raise RunConflictError("LOGICAL_STEP_ALREADY_ACCEPTED")
        self.accepted_steps[key] = normalized

    def _require_owned(self, run_id: str, worker_id: str) -> ReviewRun:
        run = self.items[run_id]
        lease = self.leases.get(run_id)
        if run.status is not AgentRunStatus.RUNNING or lease is None or lease[0] != worker_id:
            raise RunConflictError("RUN_LEASE_NOT_OWNED")
        return run

    def _close_abandoned_attempts(self, run_id: str, now: datetime) -> None:
        attempts = self.attempt_log.get(run_id, [])
        self.attempt_log[run_id] = [
            item.model_copy(
                update={
                    "completed_at": now,
                    "duration_ms": max(
                        0, int((now - item.started_at).total_seconds() * 1000)
                    ),
                    "retry_reason": "lease_expired",
                    "validation_result": "WORKER_LEASE_EXPIRED",
                    "final_status": "failed",
                }
            )
            if item.final_status == "running"
            else item
            for item in attempts
        ]

    def _event(self, run_id: str, event_type: str) -> None:
        events = self.event_log.setdefault(run_id, [])
        events.append({"sequence": len(events) + 1, "event_type": event_type})


class PostgresReviewRunRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def enqueue(self, run: ReviewRun, *, idempotency_key: str) -> ReviewRun:
        with Session(self.engine) as session, session.begin():
            existing = session.scalar(
                select(AgentRunRow).where(AgentRunRow.idempotency_key == idempotency_key)
            )
            if existing:
                current = _run_from_row(existing)
                if _command_fingerprint(current) != _command_fingerprint(run):
                    raise RunConflictError("IDEMPOTENCY_KEY_REUSED")
                return current
            row = AgentRunRow(
                run_id=run.run_id, case_id=run.case_id, packet_hash=run.packet_hash,
                run_kind=run.run_kind,
                topology=run.topology,
                actor_id=run.actor_id,
                role_id=run.role_id,
                provider=run.provider,
                requested_model=run.requested_model,
                returned_model=run.returned_model,
                contract_version=run.contract_version,
                prompt_bundle_version=run.prompt_bundle_version,
                prompt_bundle_hash=run.prompt_bundle_hash,
                policy_version=run.policy_version,
                budget_plan=run.budget_plan.model_dump(mode="json"),
                status=run.status, attempt_no=0, max_attempts=run.max_attempts,
                idempotency_key=idempotency_key,
            )
            session.add(row)
            session.add(_event_row(run.run_id, 1, "run.queued"))
        return run

    def get(self, run_id: str) -> ReviewRun | None:
        with Session(self.engine) as session:
            row = session.get(AgentRunRow, run_id)
            return _run_from_row(row) if row else None

    def latest_for_case(
        self,
        case_id: str,
        *,
        run_kind: Literal["role_review", "dossier"] | None = None,
    ) -> ReviewRun | None:
        filters = [AgentRunRow.case_id == case_id]
        if run_kind is not None:
            filters.append(AgentRunRow.run_kind == run_kind)
        with Session(self.engine) as session:
            row = session.scalar(
                select(AgentRunRow)
                .where(*filters)
                .order_by(AgentRunRow.created_at.desc(), AgentRunRow.run_id.desc())
                .limit(1)
            )
            return _run_from_row(row) if row else None

    def claim(self, worker_id: str, lease_seconds: int) -> ReviewRun | None:
        now = datetime.now(UTC)
        with Session(self.engine) as session, session.begin():
            row = session.scalar(
                select(AgentRunRow).where(
                    AgentRunRow.cancel_requested.is_(False),
                    AgentRunRow.attempt_no < AgentRunRow.max_attempts,
                    or_(AgentRunRow.next_retry_at.is_(None), AgentRunRow.next_retry_at <= now),
                    or_(
                        AgentRunRow.status == AgentRunStatus.QUEUED,
                        (AgentRunRow.status == AgentRunStatus.RUNNING)
                        & (AgentRunRow.lease_expires_at <= now),
                    ),
                ).order_by(AgentRunRow.created_at).with_for_update(skip_locked=True).limit(1)
            )
            if row is None:
                return None
            if row.status == AgentRunStatus.RUNNING:
                abandoned = session.scalars(
                    select(AgentAttemptRow).where(
                        AgentAttemptRow.run_id == row.run_id,
                        AgentAttemptRow.final_status == "running",
                    )
                ).all()
                for attempt in abandoned:
                    attempt.completed_at = now
                    attempt.duration_ms = max(
                        0, int((now - attempt.started_at).total_seconds() * 1000)
                    )
                    attempt.retry_reason = "lease_expired"
                    attempt.validation_result = "WORKER_LEASE_EXPIRED"
                    attempt.final_status = "failed"
            row.status = AgentRunStatus.RUNNING
            row.attempt_no += 1
            row.lease_owner = worker_id
            row.lease_expires_at = now + timedelta(seconds=lease_seconds)
            row.heartbeat_at = now
            row.next_retry_at = None
            session.add(
                _event_row(row.run_id, self._next_sequence(session, row.run_id), "run.claimed")
            )
            session.flush()
            return _run_from_row(row)

    def heartbeat(self, run_id: str, worker_id: str, lease_seconds: int) -> ReviewRun:
        now = datetime.now(UTC)
        with Session(self.engine) as session, session.begin():
            row = self._locked_owned(session, run_id, worker_id)
            row.heartbeat_at = now
            row.lease_expires_at = now + timedelta(seconds=lease_seconds)
            session.add(
                _event_row(run_id, self._next_sequence(session, run_id), "run.heartbeat")
            )
            session.flush()
            return _run_from_row(row)

    def complete(self, run_id: str, worker_id: str, result: AgentRunResult) -> ReviewRun:
        with Session(self.engine) as session, session.begin():
            row = self._locked_owned(session, run_id, worker_id)
            if row.cancel_requested:
                raise RunConflictError("RUN_CANCELLED_DURING_EXECUTION")
            row.status = (
                AgentRunStatus.PARTIALLY_COMPLETED
                if isinstance(result, DossierExecution) and result.failed_roles
                else AgentRunStatus.COMPLETED
            )
            row.result = result.model_dump(mode="json")
            input_tokens, output_tokens, cost = _result_usage(result)
            row.input_tokens = input_tokens
            row.output_tokens = output_tokens
            row.estimated_cost_usd = cost
            row.returned_model = _returned_model(result)
            row.lease_owner = None
            row.lease_expires_at = None
            for step_key, normalized in _logical_steps(_run_from_row(row), result):
                _, step_kind, role_id, review_round = step_key
                step_id = f"{run_id}:{step_kind}:{role_id}:{review_round}"
                existing = session.get(AgentRunStepRow, step_id)
                if existing:
                    if existing.normalized_output != normalized:
                        raise RunConflictError("LOGICAL_STEP_ALREADY_ACCEPTED")
                    continue
                session.add(
                    AgentRunStepRow(
                        step_id=step_id,
                        run_id=run_id,
                        step_kind=step_kind,
                        role_id=role_id,
                        review_round=review_round,
                        normalized_output=normalized,
                    )
                )
            event_type = (
                "run.partially_completed"
                if row.status == AgentRunStatus.PARTIALLY_COMPLETED
                else "run.completed"
            )
            session.add(_event_row(run_id, self._next_sequence(session, run_id), event_type))
            session.flush()
            return _run_from_row(row)

    def fail(
        self,
        run_id: str,
        worker_id: str,
        error_code: str,
        retryable: bool,
        retry_delay_seconds: int = 1,
    ) -> ReviewRun:
        with Session(self.engine) as session, session.begin():
            row = self._locked_owned(session, run_id, worker_id)
            row.status = (
                AgentRunStatus.QUEUED
                if retryable and row.attempt_no < row.max_attempts
                else AgentRunStatus.FAILED
            )
            row.error_code = error_code
            row.lease_owner = None
            row.lease_expires_at = None
            row.next_retry_at = (
                datetime.now(UTC) + timedelta(seconds=retry_delay_seconds)
                if row.status == AgentRunStatus.QUEUED
                else None
            )
            event = "run.retry_queued" if row.status == AgentRunStatus.QUEUED else "run.failed"
            session.add(_event_row(run_id, self._next_sequence(session, run_id), event))
            session.flush()
            return _run_from_row(row)

    def cancel(self, run_id: str) -> ReviewRun:
        with Session(self.engine) as session, session.begin():
            row = session.scalar(
                select(AgentRunRow).where(AgentRunRow.run_id == run_id).with_for_update()
            )
            if row is None:
                raise KeyError(run_id)
            row.cancel_requested = True
            row.cancel_requested_at = datetime.now(UTC)
            row.status = AgentRunStatus.CANCELLED
            row.lease_owner = None
            row.lease_expires_at = None
            session.add(
                _event_row(run_id, self._next_sequence(session, run_id), "run.cancel_requested")
            )
            session.flush()
            return _run_from_row(row)

    def retry(self, run_id: str, *, idempotency_key: str) -> ReviewRun:
        failed = self.get(run_id)
        if failed is None:
            raise KeyError(run_id)
        if failed.status not in {
            AgentRunStatus.PARTIALLY_COMPLETED,
            AgentRunStatus.FAILED,
            AgentRunStatus.CANCELLED,
        }:
            raise RunConflictError("RUN_NOT_RETRYABLE")
        return self.enqueue(
            ReviewRun(
                run_id=str(uuid4()),
                run_kind=failed.run_kind,
                topology=failed.topology,
                case_id=failed.case_id,
                packet_hash=failed.packet_hash,
                role_id=failed.role_id,
                provider=failed.provider,
                requested_model=failed.requested_model,
                returned_model=None,
                contract_version=failed.contract_version,
                prompt_bundle_version=failed.prompt_bundle_version,
                prompt_bundle_hash=failed.prompt_bundle_hash,
                policy_version=failed.policy_version,
                budget_plan=failed.budget_plan,
                status=AgentRunStatus.QUEUED,
                attempt_no=0,
                max_attempts=failed.max_attempts,
                actor_id=failed.actor_id,
            ),
            idempotency_key=idempotency_key,
        )

    def events(self, run_id: str) -> list[dict[str, object]]:
        with Session(self.engine) as session:
            rows = session.scalars(
                select(AgentRunEventRow).where(AgentRunEventRow.run_id == run_id)
                .order_by(AgentRunEventRow.sequence)
            ).all()
            return [{"sequence": row.sequence, "event_type": row.event_type} for row in rows]

    def telemetry(self) -> dict[str, int | float]:
        with Session(self.engine) as session:
            values = session.execute(
                select(
                    func.count(AgentRunRow.run_id),
                    func.count(AgentRunRow.run_id).filter(
                        AgentRunRow.status == AgentRunStatus.COMPLETED
                    ),
                    func.coalesce(func.sum(AgentRunRow.input_tokens), 0),
                    func.coalesce(func.sum(AgentRunRow.output_tokens), 0),
                    func.coalesce(func.sum(AgentRunRow.estimated_cost_usd), 0.0),
                )
            ).one()
            attempt_count = session.scalar(select(func.count(AgentAttemptRow.attempt_id)))
            return {
                "run_count": int(values[0]),
                "completed_count": int(values[1]),
                "input_tokens": int(values[2]),
                "output_tokens": int(values[3]),
                "estimated_cost_usd": float(values[4]),
                "provider_attempts": int(attempt_count or 0),
            }

    def record_attempt(self, run_id: str, attempt: ProviderAttemptMetadata) -> None:
        with Session(self.engine) as session, session.begin():
            run = session.get(AgentRunRow, run_id)
            if run is None:
                raise KeyError(run_id)
            final_status = (
                "discarded_after_cancel"
                if run.cancel_requested or run.status != AgentRunStatus.RUNNING
                else attempt.final_status
            )
            row = session.get(AgentAttemptRow, attempt.attempt_id)
            if row is None:
                row = AgentAttemptRow(
                    attempt_id=attempt.attempt_id,
                    run_id=run_id,
                    case_id=run.case_id,
                    role_id=attempt.role_id,
                    review_round=attempt.review_round,
                    provider=attempt.provider,
                    requested_model=attempt.requested_model,
                    returned_model=attempt.returned_model,
                    prompt_bundle_version=run.prompt_bundle_version,
                    policy_version=run.policy_version,
                    contract_version=run.contract_version,
                    observable_packet_hash=run.packet_hash,
                    started_at=attempt.started_at,
                    completed_at=attempt.completed_at,
                    duration_ms=attempt.duration_ms,
                    input_tokens=attempt.input_tokens,
                    output_tokens=attempt.output_tokens,
                    estimated_cost_usd=attempt.estimated_cost_usd,
                    retry_reason=attempt.retry_reason,
                    validation_result=attempt.validation_result,
                    final_status=final_status,
                )
                session.add(row)
                return
            row.returned_model = attempt.returned_model
            row.completed_at = attempt.completed_at
            row.duration_ms = attempt.duration_ms
            row.input_tokens = attempt.input_tokens
            row.output_tokens = attempt.output_tokens
            row.estimated_cost_usd = attempt.estimated_cost_usd
            row.retry_reason = attempt.retry_reason
            row.validation_result = attempt.validation_result
            row.final_status = final_status

    def attempt_count(self, run_id: str) -> int:
        with Session(self.engine) as session:
            value = session.scalar(
                select(func.count(AgentAttemptRow.attempt_id)).where(
                    AgentAttemptRow.run_id == run_id
                )
            )
            return int(value or 0)

    def review_checkpoints(
        self, run_id: str, review_round: int = 0
    ) -> list[ProviderReviewResult]:
        with Session(self.engine) as session:
            rows = session.scalars(
                select(AgentRunStepRow).where(
                    AgentRunStepRow.run_id == run_id,
                    AgentRunStepRow.step_kind == "role_review",
                    AgentRunStepRow.review_round == review_round,
                )
            ).all()
            return [
                ProviderReviewResult.model_validate(row.normalized_output)
                for row in rows
                if "review" in row.normalized_output
            ]

    def save_review_checkpoint(
        self,
        run_id: str,
        worker_id: str,
        result: ProviderReviewResult,
        review_round: int = 0,
    ) -> None:
        with Session(self.engine) as session, session.begin():
            self._locked_owned(session, run_id, worker_id)
            step_id = (
                f"{run_id}:role_review:{result.review.role_id}:{review_round}"
            )
            normalized = result.model_dump(mode="json")
            existing = session.get(AgentRunStepRow, step_id)
            if existing:
                if existing.normalized_output != normalized:
                    raise RunConflictError("LOGICAL_STEP_ALREADY_ACCEPTED")
                return
            session.add(
                AgentRunStepRow(
                    step_id=step_id,
                    run_id=run_id,
                    step_kind="role_review",
                    role_id=result.review.role_id,
                    review_round=review_round,
                    normalized_output=normalized,
                )
            )

    def challenger_checkpoint(self, run_id: str) -> ChallengerProviderResult | None:
        step_id = f"{run_id}:challenger:challenger:0"
        with Session(self.engine) as session:
            row = session.get(AgentRunStepRow, step_id)
            if row and "challenger" in row.normalized_output:
                return ChallengerProviderResult.model_validate(row.normalized_output)
            return None

    def save_challenger_checkpoint(
        self, run_id: str, worker_id: str, result: ChallengerProviderResult
    ) -> None:
        step_id = f"{run_id}:challenger:challenger:0"
        normalized = result.model_dump(mode="json")
        with Session(self.engine) as session, session.begin():
            self._locked_owned(session, run_id, worker_id)
            existing = session.get(AgentRunStepRow, step_id)
            if existing:
                if existing.normalized_output != normalized:
                    raise RunConflictError("LOGICAL_STEP_ALREADY_ACCEPTED")
                return
            session.add(
                AgentRunStepRow(
                    step_id=step_id,
                    run_id=run_id,
                    step_kind="challenger",
                    role_id="challenger",
                    review_round=0,
                    normalized_output=normalized,
                )
            )

    def chair_checkpoint(self, run_id: str) -> ChairProviderResult | None:
        step_id = f"{run_id}:chair:decision_chair:0"
        with Session(self.engine) as session:
            row = session.get(AgentRunStepRow, step_id)
            if row and "decision" in row.normalized_output:
                return ChairProviderResult.model_validate(row.normalized_output)
            return None

    def save_chair_checkpoint(
        self, run_id: str, worker_id: str, result: ChairProviderResult
    ) -> None:
        step_id = f"{run_id}:chair:decision_chair:0"
        normalized = result.model_dump(mode="json")
        with Session(self.engine) as session, session.begin():
            self._locked_owned(session, run_id, worker_id)
            existing = session.get(AgentRunStepRow, step_id)
            if existing:
                if existing.normalized_output != normalized:
                    raise RunConflictError("LOGICAL_STEP_ALREADY_ACCEPTED")
                return
            session.add(
                AgentRunStepRow(
                    step_id=step_id,
                    run_id=run_id,
                    step_kind="chair",
                    role_id="decision_chair",
                    review_round=0,
                    normalized_output=normalized,
                )
            )

    def _locked_owned(self, session: Session, run_id: str, worker_id: str) -> AgentRunRow:
        row = session.scalar(
            select(AgentRunRow).where(AgentRunRow.run_id == run_id).with_for_update()
        )
        if row is None or row.status != AgentRunStatus.RUNNING or row.lease_owner != worker_id:
            raise RunConflictError("RUN_LEASE_NOT_OWNED")
        return row

    @staticmethod
    def _next_sequence(session: Session, run_id: str) -> int:
        last = session.scalar(
            select(AgentRunEventRow.sequence).where(AgentRunEventRow.run_id == run_id)
            .order_by(AgentRunEventRow.sequence.desc()).limit(1)
        )
        return (last or 0) + 1


def enqueue_role_review(
    case_repository: CaseRepository,
    run_repository: ReviewRunRepository,
    *,
    case_id: str,
    role_id: str,
    provider: str,
    model: str,
    idempotency_key: str,
    actor_id: str = "local-home-reviewer",
    max_case_cost_usd: float = 2.0,
) -> ReviewRun:
    stored = case_repository.get(case_id)
    if stored is None:
        raise KeyError(case_id)
    packet = build_observable_case_packet(stored.case)
    if role_id not in packet.selected_role_ids:
        raise ValueError("ROLE_NOT_ALLOWED_FOR_CASE")
    return run_repository.enqueue(
        ReviewRun(
            run_id=str(uuid4()), case_id=case_id, packet_hash=packet.packet_hash,
            run_kind="role_review",
            topology=None,
            role_id=role_id,
            provider=provider,
            requested_model=model,
            returned_model=None,
            contract_version="role-review.v1",
            prompt_bundle_version=PROMPT_BUNDLE_VERSION,
            prompt_bundle_hash=PROMPT_BUNDLE_HASH,
            policy_version="decision-policy.v1",
            budget_plan=_build_budget_plan("role_review", 1, max_case_cost_usd),
            status=AgentRunStatus.QUEUED,
            attempt_no=0, max_attempts=2,
            actor_id=actor_id,
        ),
        idempotency_key=idempotency_key,
    )


def enqueue_dossier_review(
    case_repository: CaseRepository,
    run_repository: ReviewRunRepository,
    *,
    case_id: str,
    provider: str,
    model: str,
    idempotency_key: str,
    actor_id: str = "local-home-reviewer",
    max_case_cost_usd: float = 2.0,
    topology: DossierTopology = RELEASE_DOSSIER_TOPOLOGY,
) -> ReviewRun:
    stored = case_repository.get(case_id)
    if stored is None:
        raise KeyError(case_id)
    packet = build_observable_case_packet(stored.case)
    return run_repository.enqueue(
        ReviewRun(
            run_id=str(uuid4()),
            run_kind="dossier",
            topology=topology,
            case_id=case_id,
            packet_hash=packet.packet_hash,
            role_id="__routed__",
            provider=provider,
            requested_model=model,
            returned_model=None,
            contract_version="decision-dossier.v1",
            prompt_bundle_version=PROMPT_BUNDLE_VERSION,
            prompt_bundle_hash=PROMPT_BUNDLE_HASH,
            policy_version="decision-policy.v1",
            budget_plan=_build_budget_plan(
                "dossier", len(packet.selected_role_ids), max_case_cost_usd, topology
            ),
            status=AgentRunStatus.QUEUED,
            attempt_no=0,
            max_attempts=2,
            actor_id=actor_id,
        ),
        idempotency_key=idempotency_key,
    )


def execute_claimed_run(
    run: ReviewRun,
    case_repository: CaseRepository,
    provider: ReviewProvider,
    attempt_sink: AttemptSink | None = None,
    initial_role_results: dict[str, ProviderReviewResult] | None = None,
    review_checkpoint_sink: ReviewCheckpointSink | None = None,
    prior_provider_attempts: int = 0,
    initial_revision_results: dict[str, ProviderReviewResult] | None = None,
    initial_challenger_result: ChallengerProviderResult | None = None,
    challenger_checkpoint_sink: ChallengerCheckpointSink | None = None,
    initial_chair_result: ChairProviderResult | None = None,
    chair_checkpoint_sink: ChairCheckpointSink | None = None,
    runtime_budget: AgentRuntimeBudget | None = None,
) -> AgentRunResult:
    stored = case_repository.get(run.case_id)
    if stored is None:
        raise ValueError("CASE_NOT_FOUND")
    packet = build_observable_case_packet(stored.case)
    if packet.packet_hash != run.packet_hash:
        raise ValueError("OBSERVABLE_PACKET_CHANGED")
    if run.run_kind == "dossier":
        if run.topology is None:
            raise ValueError("DOSSIER_TOPOLOGY_REQUIRED")
        return run_dossier_round(
            packet,
            provider,
            run.topology,
            budget=runtime_budget or AgentRuntimeBudget(),
            attempt_sink=attempt_sink,
            initial_role_results=initial_role_results,
            review_checkpoint_sink=review_checkpoint_sink,
            prior_provider_attempts=prior_provider_attempts,
            initial_revision_results=initial_revision_results,
            initial_challenger_result=initial_challenger_result,
            challenger_checkpoint_sink=challenger_checkpoint_sink,
            initial_chair_result=initial_chair_result,
            chair_checkpoint_sink=chair_checkpoint_sink,
            allowed_decision_types=stored.case.allowed_decision_types,
        )
    return execute_grounded_review(
        packet,
        run.role_id,
        provider,
        validator=lambda result: _validate_grounding(result, packet),
        max_provider_attempts=3,
        attempt_sink=attempt_sink,
    )


def _validate_grounding(result: ProviderReviewResult, packet: object) -> None:
    from soc_ot.application.packets import ObservableCasePacket

    typed = (
        packet
        if isinstance(packet, ObservableCasePacket)
        else ObservableCasePacket.model_validate(packet)
    )
    valid_claim_ids = {claim.claim_id for claim in typed.claims}
    used_claim_ids = set(result.review.rationale_claim_ids)
    for risk in result.review.risks:
        used_claim_ids.update(risk.claim_ids)
    if not used_claim_ids <= valid_claim_ids:
        raise ValueError("UNSUPPORTED_AUTHORITATIVE_CLAIM")
    valid_options = {item.option_id for item in typed.alternatives}
    if (
        result.review.recommended_option_id
        and result.review.recommended_option_id not in valid_options
    ):
        raise ValueError("UNKNOWN_RECOMMENDED_OPTION")


def _replace_run(run: ReviewRun, **changes: object) -> ReviewRun:
    return replace(run, **changes)  # type: ignore[arg-type]


def _run_from_row(row: AgentRunRow) -> ReviewRun:
    return ReviewRun(
        run_id=row.run_id,
        run_kind=cast(Literal["role_review", "dossier"], row.run_kind),
        topology=cast(DossierTopology | None, row.topology),
        case_id=row.case_id,
        actor_id=row.actor_id,
        packet_hash=row.packet_hash,
        role_id=row.role_id,
        provider=row.provider,
        requested_model=row.requested_model,
        returned_model=row.returned_model,
        contract_version=row.contract_version,
        prompt_bundle_version=row.prompt_bundle_version,
        prompt_bundle_hash=row.prompt_bundle_hash,
        policy_version=row.policy_version,
        budget_plan=AgentRunBudgetPlan.model_validate(row.budget_plan),
        status=AgentRunStatus(row.status),
        attempt_no=row.attempt_no,
        max_attempts=row.max_attempts,
        cancel_requested=row.cancel_requested,
        lease_owner=row.lease_owner,
        lease_expires_at=row.lease_expires_at,
        heartbeat_at=row.heartbeat_at,
        next_retry_at=row.next_retry_at,
        cancel_requested_at=row.cancel_requested_at,
        result=RESULT_ADAPTER.validate_python(row.result) if row.result else None,
        error_code=row.error_code, created_at=row.created_at, updated_at=row.updated_at,
    )


def _event_row(run_id: str, sequence: int, event_type: str) -> AgentRunEventRow:
    return AgentRunEventRow(
        event_id=f"{run_id}:{sequence}", run_id=run_id, sequence=sequence,
        event_type=event_type, payload={},
    )


def _command_fingerprint(
    run: ReviewRun,
) -> tuple[str, str, str, str, str, str, str, str, DossierTopology | None]:
    return (
        run.case_id,
        run.packet_hash,
        run.run_kind,
        run.role_id,
        run.provider,
        run.requested_model,
        run.prompt_bundle_hash,
        run.actor_id,
        run.topology,
    )


def _result_usage(result: AgentRunResult | None) -> tuple[int, int, float]:
    if result is None:
        return (0, 0, 0.0)
    if isinstance(result, ProviderReviewResult):
        return (
            result.usage.input_tokens,
            result.usage.output_tokens,
            result.usage.estimated_cost_usd,
        )
    return (result.input_tokens, result.output_tokens, result.estimated_cost_usd)


def _build_budget_plan(
    run_kind: Literal["role_review", "dossier"],
    role_count: int,
    maximum_cost_usd: float,
    topology: DossierTopology | None = None,
) -> AgentRunBudgetPlan:
    if run_kind == "role_review":
        logical_calls = 1
        provider_attempts = 3
        output_tokens = 1_500
        timeout_seconds = 120
    else:
        if topology is None:
            raise ValueError("DOSSIER_TOPOLOGY_REQUIRED")
        effective_roles = 1 if topology == "B1" else role_count
        revisions = min(2, effective_roles) if topology == "B3" else 0
        logical_calls = effective_roles + (2 + revisions if topology == "B3" else 0)
        provider_attempts = logical_calls
        output_tokens = effective_roles * 1_500
        if topology == "B3":
            output_tokens += 2_000 + revisions * 1_500 + 3_000
        timeout_seconds = 900
    return AgentRunBudgetPlan(
        reserved_logical_calls=logical_calls,
        remaining_logical_calls=9 - logical_calls,
        reserved_provider_attempts=provider_attempts,
        remaining_provider_attempts=12 - provider_attempts,
        reserved_output_tokens=output_tokens,
        remaining_output_tokens=20_000 - output_tokens,
        timeout_envelope_seconds=timeout_seconds,
        maximum_cost_usd=maximum_cost_usd,
    )


def _returned_model(result: AgentRunResult) -> str | None:
    if isinstance(result, ProviderReviewResult):
        return result.returned_model
    return ",".join(result.returned_models) or None


def _logical_steps(
    run: ReviewRun, result: AgentRunResult
) -> list[tuple[tuple[str, str, str, int], dict[str, object]]]:
    if isinstance(result, ProviderReviewResult):
        return [
            (
                (run.run_id, "role_review", run.role_id, 0),
                result.model_dump(mode="json"),
            )
        ]
    steps: list[tuple[tuple[str, str, str, int], dict[str, object]]] = []
    role_results = {item.review.role_id: item for item in result.accepted_role_results}
    for review in result.dossier.original_reviews:
        normalized = (
            role_results[review.role_id].model_dump(mode="json")
            if review.role_id in role_results
            else review.model_dump(mode="json")
        )
        steps.append(
            (
                (run.run_id, "role_review", review.role_id, 0),
                normalized,
            )
        )
    if result.dossier.challenger:
        normalized = (
            result.challenger_provider_result.model_dump(mode="json")
            if result.challenger_provider_result
            else result.dossier.challenger.model_dump(mode="json")
        )
        steps.append(
            (
                (run.run_id, "challenger", "challenger", 0),
                normalized,
            )
        )
    if result.chair_provider_result:
        steps.append(
            (
                (run.run_id, "chair", "decision_chair", 0),
                result.chair_provider_result.model_dump(mode="json"),
            )
        )
    revision_results = {
        item.review.role_id: item for item in result.accepted_revision_results
    }
    for review in result.dossier.revised_reviews:
        normalized = (
            revision_results[review.role_id].model_dump(mode="json")
            if review.role_id in revision_results
            else review.model_dump(mode="json")
        )
        steps.append(
            (
                (run.run_id, "role_review", review.role_id, 1),
                normalized,
            )
        )
    steps.append(
        (
            (run.run_id, "dossier", "orchestrator", 0),
            result.dossier.model_dump(mode="json"),
        )
    )
    return steps
