import hashlib
from collections.abc import Callable
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from soc_ot.agents.multi_role import AblationResult
from soc_ot.infrastructure.tables import SimulatedDecisionRow

DecisionFactory = Callable[[], AblationResult]


class SimulatedDecisionConflict(ValueError):
    pass


class SimulatedDecisionRepository(Protocol):
    def create(
        self,
        *,
        case_id: str,
        review_run_id: str,
        idempotency_key: str,
        expected_aggregate_version: int,
        actual_aggregate_version: int,
        actor_id: str,
        factory: DecisionFactory,
    ) -> AblationResult: ...


class InMemorySimulatedDecisionRepository:
    def __init__(self) -> None:
        self.commands: dict[str, tuple[str, AblationResult]] = {}

    def create(
        self,
        *,
        case_id: str,
        review_run_id: str,
        idempotency_key: str,
        expected_aggregate_version: int,
        actual_aggregate_version: int,
        actor_id: str,
        factory: DecisionFactory,
    ) -> AblationResult:
        fingerprint = _fingerprint(
            case_id, review_run_id, expected_aggregate_version, actor_id
        )
        existing = self.commands.get(idempotency_key)
        if existing:
            if existing[0] != fingerprint:
                raise SimulatedDecisionConflict("IDEMPOTENCY_KEY_REUSED")
            return existing[1]
        if expected_aggregate_version != actual_aggregate_version:
            raise SimulatedDecisionConflict("CASE_VERSION_CONFLICT")
        result = factory()
        self.commands[idempotency_key] = (fingerprint, result)
        return result


class PostgresSimulatedDecisionRepository(InMemorySimulatedDecisionRepository):
    def __init__(self, engine: Engine) -> None:
        super().__init__()
        self.engine = engine

    def create(
        self,
        *,
        case_id: str,
        review_run_id: str,
        idempotency_key: str,
        expected_aggregate_version: int,
        actual_aggregate_version: int,
        actor_id: str,
        factory: DecisionFactory,
    ) -> AblationResult:
        fingerprint = _fingerprint(
            case_id, review_run_id, expected_aggregate_version, actor_id
        )
        with Session(self.engine) as session:
            existing = session.scalar(
                select(SimulatedDecisionRow).where(
                    SimulatedDecisionRow.idempotency_key == idempotency_key
                )
            )
            if existing:
                if existing.command_fingerprint != fingerprint:
                    raise SimulatedDecisionConflict("IDEMPOTENCY_KEY_REUSED")
                return AblationResult.model_validate(existing.payload)
        if expected_aggregate_version != actual_aggregate_version:
            raise SimulatedDecisionConflict("CASE_VERSION_CONFLICT")
        result = factory()
        with Session(self.engine) as session, session.begin():
            session.add(
                SimulatedDecisionRow(
                    command_id=str(uuid4()),
                    idempotency_key=idempotency_key,
                    command_fingerprint=fingerprint,
                    case_id=case_id,
                    aggregate_version=expected_aggregate_version,
                    review_run_id=review_run_id,
                    actor_id=actor_id,
                    payload=result.model_dump(mode="json"),
                )
            )
        return result


def _fingerprint(
    case_id: str, review_run_id: str, aggregate_version: int, actor_id: str
) -> str:
    value = (
        f"simulated-decision-command.v1|{case_id}|{review_run_id}|"
        f"{aggregate_version}|{actor_id}"
    )
    return hashlib.sha256(value.encode()).hexdigest()
