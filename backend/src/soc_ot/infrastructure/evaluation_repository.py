import hashlib
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from soc_ot.application.evaluation import CaseEvaluation, evaluate_case
from soc_ot.infrastructure.fixtures import FixtureRepository
from soc_ot.infrastructure.tables import OutcomeEvaluationRow


class EvaluationConflict(ValueError):
    pass


class FixtureEvaluationRepository:
    """Evaluation-only port that owns access to hidden and expected fixtures."""

    def __init__(self, fixtures: FixtureRepository) -> None:
        self.fixtures = fixtures
        self.commands: dict[str, tuple[str, CaseEvaluation]] = {}
        self.latest_by_case: dict[str, CaseEvaluation] = {}

    def required_step(self, case_id: str) -> int:
        hidden = self.fixtures.load_hidden(case_id)
        case = self.fixtures.load_observable(case_id)
        return max(
            case.current_step + 1,
            *(
                int(path.parameters.get("reveal_measurement_at_step", case.current_step + 1))
                for path in hidden.outcome_paths
            ),
        )

    def evaluate(
        self,
        case_id: str,
        *,
        idempotency_key: str,
        aggregate_version: int,
        actor_id: str,
    ) -> CaseEvaluation:
        fingerprint = _fingerprint(case_id, aggregate_version, actor_id)
        existing = self.commands.get(idempotency_key)
        if existing:
            if existing[0] != fingerprint:
                raise EvaluationConflict("IDEMPOTENCY_KEY_REUSED")
            return existing[1]
        result = evaluate_case(self.fixtures, case_id)
        self.commands[idempotency_key] = (fingerprint, result)
        self.latest_by_case[case_id] = result
        return result

    def latest(self, case_id: str) -> CaseEvaluation | None:
        return self.latest_by_case.get(case_id)


class PostgresEvaluationRepository(FixtureEvaluationRepository):
    def __init__(self, fixtures: FixtureRepository, engine: Engine) -> None:
        super().__init__(fixtures)
        self.engine = engine

    def evaluate(
        self,
        case_id: str,
        *,
        idempotency_key: str,
        aggregate_version: int,
        actor_id: str,
    ) -> CaseEvaluation:
        fingerprint = _fingerprint(case_id, aggregate_version, actor_id)
        with Session(self.engine) as session:
            existing = session.scalar(
                select(OutcomeEvaluationRow).where(
                    OutcomeEvaluationRow.idempotency_key == idempotency_key
                )
            )
            if existing:
                if existing.command_fingerprint != fingerprint:
                    raise EvaluationConflict("IDEMPOTENCY_KEY_REUSED")
                return CaseEvaluation.model_validate(existing.payload)
        result = evaluate_case(self.fixtures, case_id)
        with Session(self.engine) as session, session.begin():
            session.add(
                OutcomeEvaluationRow(
                    evaluation_id=str(uuid4()),
                    case_id=case_id,
                    idempotency_key=idempotency_key,
                    command_fingerprint=fingerprint,
                    aggregate_version=aggregate_version,
                    actor_id=actor_id,
                    payload=result.model_dump(mode="json"),
                )
            )
        return result

    def latest(self, case_id: str) -> CaseEvaluation | None:
        with Session(self.engine) as session:
            row = session.scalar(
                select(OutcomeEvaluationRow)
                .where(OutcomeEvaluationRow.case_id == case_id)
                .order_by(OutcomeEvaluationRow.recorded_at.desc())
                .limit(1)
            )
            return CaseEvaluation.model_validate(row.payload) if row else None


def _fingerprint(case_id: str, aggregate_version: int, actor_id: str) -> str:
    value = f"case-evaluation.v1|{case_id}|{aggregate_version}|{actor_id}"
    return hashlib.sha256(value.encode()).hexdigest()
