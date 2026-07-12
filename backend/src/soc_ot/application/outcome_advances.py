import hashlib
import json
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from soc_ot.agents.multi_role import SimulatedDecision
from soc_ot.application.outcomes import OutcomeSnapshot, advance_outcome
from soc_ot.domain.models import HiddenCase, ObservableCase
from soc_ot.infrastructure.tables import (
    DecisionCaseRow,
    DomainEventRow,
    OutcomeAdvanceRow,
    SimulationStateRow,
)


class OutcomeAdvanceConflict(ValueError):
    pass


class OutcomeAdvanceRepository(Protocol):
    def advance(
        self,
        case: ObservableCase,
        hidden: HiddenCase,
        decision: SimulatedDecision,
        *,
        from_step: int,
        to_step: int,
        idempotency_key: str,
        expected_aggregate_version: int | None = None,
        actor_id: str = "local-home-reviewer",
    ) -> OutcomeSnapshot: ...


class InMemoryOutcomeAdvanceRepository:
    def __init__(self) -> None:
        self.current_steps: dict[str, int] = {}
        self.commands: dict[str, tuple[str, OutcomeSnapshot]] = {}

    def advance(
        self,
        case: ObservableCase,
        hidden: HiddenCase,
        decision: SimulatedDecision,
        *,
        from_step: int,
        to_step: int,
        idempotency_key: str,
        expected_aggregate_version: int | None = None,
        actor_id: str = "local-home-reviewer",
    ) -> OutcomeSnapshot:
        fingerprint = _fingerprint(case.case_id, decision, from_step, to_step, actor_id)
        existing = self.commands.get(idempotency_key)
        if existing:
            if existing[0] != fingerprint:
                raise OutcomeAdvanceConflict("IDEMPOTENCY_KEY_REUSED")
            return existing[1]
        current = self.current_steps.get(case.case_id, case.current_step)
        if current != from_step:
            raise OutcomeAdvanceConflict("SIMULATION_STEP_CONFLICT")
        effective_case = case.model_copy(update={"current_step": from_step})
        result = advance_outcome(effective_case, hidden, decision, target_step=to_step)
        self.current_steps[case.case_id] = to_step
        self.commands[idempotency_key] = (fingerprint, result)
        return result


class PostgresOutcomeAdvanceRepository:
    def __init__(self, outcome_engine: Engine) -> None:
        self.engine = outcome_engine

    def advance(
        self,
        case: ObservableCase,
        hidden: HiddenCase,
        decision: SimulatedDecision,
        *,
        from_step: int,
        to_step: int,
        idempotency_key: str,
        expected_aggregate_version: int | None = None,
        actor_id: str = "local-home-reviewer",
    ) -> OutcomeSnapshot:
        fingerprint = _fingerprint(case.case_id, decision, from_step, to_step, actor_id)
        with Session(self.engine) as session, session.begin():
            existing = session.scalar(
                select(OutcomeAdvanceRow).where(
                    OutcomeAdvanceRow.idempotency_key == idempotency_key
                )
            )
            if existing:
                if existing.command_fingerprint != fingerprint:
                    raise OutcomeAdvanceConflict("IDEMPOTENCY_KEY_REUSED")
                return OutcomeSnapshot.model_validate(existing.result)
            case_row = session.scalar(
                select(DecisionCaseRow)
                .where(DecisionCaseRow.case_id == case.case_id)
                .with_for_update()
            )
            if case_row is None:
                raise OutcomeAdvanceConflict("CASE_NOT_FOUND")
            if (
                expected_aggregate_version is not None
                and case_row.aggregate_version != expected_aggregate_version
            ):
                raise OutcomeAdvanceConflict("CASE_VERSION_CONFLICT")
            state = session.scalar(
                select(SimulationStateRow)
                .where(SimulationStateRow.case_id == case.case_id)
                .with_for_update()
            )
            current = case_row.current_step
            if current != from_step:
                raise OutcomeAdvanceConflict("SIMULATION_STEP_CONFLICT")
            effective_case = case.model_copy(update={"current_step": from_step})
            result = advance_outcome(effective_case, hidden, decision, target_step=to_step)
            if state is None:
                state = SimulationStateRow(
                    case_id=case.case_id,
                    current_step=to_step,
                    aggregate_version=1,
                )
                session.add(state)
            else:
                state.current_step = to_step
                state.aggregate_version += 1
            updated_case = case.model_copy(update={"current_step": to_step})
            next_version = case_row.aggregate_version + 1
            case_row.current_step = to_step
            case_row.aggregate_version = next_version
            case_row.payload = updated_case.model_dump(mode="json")
            session.add(
                DomainEventRow(
                    event_id=f"{case.case_id}:{next_version}:outcome_advanced",
                    case_id=case.case_id,
                    aggregate_version=next_version,
                    event_type="outcome_advanced",
                    actor_id=actor_id,
                    payload={
                        "decision_id": result.decision_id,
                        "from_step": from_step,
                        "to_step": to_step,
                    },
                )
            )
            session.add(
                OutcomeAdvanceRow(
                    advance_id=str(uuid4()),
                    idempotency_key=idempotency_key,
                    command_fingerprint=fingerprint,
                    case_id=case.case_id,
                    actor_id=actor_id,
                    decision_id=result.decision_id,
                    from_step=from_step,
                    to_step=to_step,
                    result=result.model_dump(mode="json"),
                )
            )
            session.flush()
            return result


def _fingerprint(
    case_id: str,
    decision: SimulatedDecision,
    from_step: int,
    to_step: int,
    actor_id: str,
) -> str:
    canonical = json.dumps(
        {
            "case_id": case_id,
            "decision": decision.model_dump(mode="json"),
            "from_step": from_step,
            "to_step": to_step,
            "actor_id": actor_id,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
