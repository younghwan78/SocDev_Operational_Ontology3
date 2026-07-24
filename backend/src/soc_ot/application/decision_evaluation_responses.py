import hashlib
import json
from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import uuid4

from pydantic import Field, model_validator
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from soc_ot.agents.multi_role import AblationResult
from soc_ot.domain.models import StrictModel
from soc_ot.infrastructure.tables import DecisionEvaluationResponseRow

AdviceAdoption = Literal["accept", "modify", "reject"]


class DecisionInitialResponseCommand(StrictModel):
    command_schema_version: Literal["decision-initial-response-command.v1"] = (
        "decision-initial-response-command.v1"
    )
    option_id: str = Field(min_length=1)
    accepted_risks_ko: list[str] = Field(min_length=1)
    safeguards_ko: list[str] = Field(min_length=1)
    rationale_ko: str = Field(min_length=1)


class DecisionFinalResponseCommand(StrictModel):
    command_schema_version: Literal["decision-final-response-command.v1"] = (
        "decision-final-response-command.v1"
    )
    adoption: AdviceAdoption
    option_id: str = Field(min_length=1)
    accepted_risks_ko: list[str] = Field(min_length=1)
    safeguards_ko: list[str] = Field(min_length=1)
    rationale_ko: str = Field(min_length=1)
    difference_reason_ko: str | None = None

    @model_validator(mode="after")
    def require_difference_reason(self) -> "DecisionFinalResponseCommand":
        if self.adoption in {"modify", "reject"} and not (
            self.difference_reason_ko and self.difference_reason_ko.strip()
        ):
            raise ValueError("DIFFERENCE_REASON_REQUIRED")
        return self


class DecisionAdviceRevealCommand(StrictModel):
    command_schema_version: Literal["decision-advice-reveal-command.v1"] = (
        "decision-advice-reveal-command.v1"
    )


class DecisionInitialResponseRecord(StrictModel):
    option_id: str
    accepted_risks_ko: list[str]
    safeguards_ko: list[str]
    rationale_ko: str
    recorded_at: datetime


class DecisionAdviceSnapshot(StrictModel):
    advice_snapshot_id: str
    decision_type: str
    selected_option_id: str | None
    decision_source: str
    revealed_at: datetime


class DecisionFinalResponseRecord(StrictModel):
    adoption: AdviceAdoption
    option_id: str
    accepted_risks_ko: list[str]
    safeguards_ko: list[str]
    rationale_ko: str
    difference_reason_ko: str | None
    recorded_at: datetime


class DecisionEvaluationResponseState(StrictModel):
    response_schema_version: Literal["decision-evaluation-response.v1"] = (
        "decision-evaluation-response.v1"
    )
    response_id: str
    case_id: str
    actor_id: str
    participant_kind: Literal["builder"] = "builder"
    interpretation: Literal["engineering_proxy_only"] = "engineering_proxy_only"
    initial_response: DecisionInitialResponseRecord | None = None
    advice_snapshot: DecisionAdviceSnapshot | None = None
    final_response: DecisionFinalResponseRecord | None = None


class DecisionEvaluationResponseConflict(ValueError):
    pass


class DecisionEvaluationResponseRepository(Protocol):
    def get(
        self, *, case_id: str, actor_id: str
    ) -> DecisionEvaluationResponseState | None: ...

    def record_initial(
        self,
        *,
        case_id: str,
        actor_id: str,
        idempotency_key: str,
        expected_aggregate_version: int,
        actual_aggregate_version: int,
        allowed_option_ids: set[str],
        command: DecisionInitialResponseCommand,
    ) -> DecisionEvaluationResponseState: ...

    def reveal_advice(
        self,
        *,
        case_id: str,
        actor_id: str,
        idempotency_key: str,
        expected_aggregate_version: int,
        actual_aggregate_version: int,
        advice: AblationResult,
    ) -> DecisionEvaluationResponseState: ...

    def record_final(
        self,
        *,
        case_id: str,
        actor_id: str,
        idempotency_key: str,
        expected_aggregate_version: int,
        actual_aggregate_version: int,
        allowed_option_ids: set[str],
        command: DecisionFinalResponseCommand,
    ) -> DecisionEvaluationResponseState: ...


class _StoredEvaluationResponse:
    def __init__(
        self,
        state: DecisionEvaluationResponseState,
        *,
        initial_key: str,
        initial_fingerprint: str,
        reveal_key: str | None = None,
        reveal_fingerprint: str | None = None,
        final_key: str | None = None,
        final_fingerprint: str | None = None,
    ) -> None:
        self.state = state
        self.initial_key = initial_key
        self.initial_fingerprint = initial_fingerprint
        self.reveal_key = reveal_key
        self.reveal_fingerprint = reveal_fingerprint
        self.final_key = final_key
        self.final_fingerprint = final_fingerprint


class InMemoryDecisionEvaluationResponseRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], _StoredEvaluationResponse] = {}
        self._command_keys: dict[str, tuple[str, str]] = {}

    def get(
        self, *, case_id: str, actor_id: str
    ) -> DecisionEvaluationResponseState | None:
        stored = self._items.get((case_id, actor_id))
        return stored.state if stored else None

    def record_initial(
        self,
        *,
        case_id: str,
        actor_id: str,
        idempotency_key: str,
        expected_aggregate_version: int,
        actual_aggregate_version: int,
        allowed_option_ids: set[str],
        command: DecisionInitialResponseCommand,
    ) -> DecisionEvaluationResponseState:
        fingerprint = _command_fingerprint(case_id, actor_id, command)
        existing_command = self._command_keys.get(idempotency_key)
        if existing_command:
            if existing_command != ("initial", fingerprint):
                raise DecisionEvaluationResponseConflict("IDEMPOTENCY_KEY_REUSED")
            state = self.get(case_id=case_id, actor_id=actor_id)
            if state is None:
                raise DecisionEvaluationResponseConflict("INITIAL_RESPONSE_NOT_FOUND")
            return state
        _require_version(expected_aggregate_version, actual_aggregate_version)
        _require_option(command.option_id, allowed_option_ids)
        key = (case_id, actor_id)
        if key in self._items:
            raise DecisionEvaluationResponseConflict("INITIAL_RESPONSE_IMMUTABLE")
        now = datetime.now(UTC)
        state = DecisionEvaluationResponseState(
            response_id=str(uuid4()),
            case_id=case_id,
            actor_id=actor_id,
            initial_response=DecisionInitialResponseRecord(
                option_id=command.option_id,
                accepted_risks_ko=command.accepted_risks_ko,
                safeguards_ko=command.safeguards_ko,
                rationale_ko=command.rationale_ko,
                recorded_at=now,
            ),
        )
        self._items[key] = _StoredEvaluationResponse(
            state,
            initial_key=idempotency_key,
            initial_fingerprint=fingerprint,
        )
        self._command_keys[idempotency_key] = ("initial", fingerprint)
        return state

    def reveal_advice(
        self,
        *,
        case_id: str,
        actor_id: str,
        idempotency_key: str,
        expected_aggregate_version: int,
        actual_aggregate_version: int,
        advice: AblationResult,
    ) -> DecisionEvaluationResponseState:
        fingerprint = _advice_fingerprint(case_id, actor_id, advice)
        existing_command = self._command_keys.get(idempotency_key)
        if existing_command:
            if existing_command != ("reveal", fingerprint):
                raise DecisionEvaluationResponseConflict("IDEMPOTENCY_KEY_REUSED")
            state = self.get(case_id=case_id, actor_id=actor_id)
            if state is None:
                raise DecisionEvaluationResponseConflict("INITIAL_RESPONSE_REQUIRED")
            return state
        _require_version(expected_aggregate_version, actual_aggregate_version)
        stored = self._items.get((case_id, actor_id))
        if stored is None:
            raise DecisionEvaluationResponseConflict("INITIAL_RESPONSE_REQUIRED")
        if stored.state.advice_snapshot is not None:
            raise DecisionEvaluationResponseConflict("ADVICE_REVEAL_IMMUTABLE")
        snapshot = _build_advice_snapshot(advice)
        stored.state = stored.state.model_copy(update={"advice_snapshot": snapshot})
        stored.reveal_key = idempotency_key
        stored.reveal_fingerprint = fingerprint
        self._command_keys[idempotency_key] = ("reveal", fingerprint)
        return stored.state

    def record_final(
        self,
        *,
        case_id: str,
        actor_id: str,
        idempotency_key: str,
        expected_aggregate_version: int,
        actual_aggregate_version: int,
        allowed_option_ids: set[str],
        command: DecisionFinalResponseCommand,
    ) -> DecisionEvaluationResponseState:
        fingerprint = _command_fingerprint(case_id, actor_id, command)
        existing_command = self._command_keys.get(idempotency_key)
        if existing_command:
            if existing_command != ("final", fingerprint):
                raise DecisionEvaluationResponseConflict("IDEMPOTENCY_KEY_REUSED")
            state = self.get(case_id=case_id, actor_id=actor_id)
            if state is None:
                raise DecisionEvaluationResponseConflict("INITIAL_RESPONSE_REQUIRED")
            return state
        _require_version(expected_aggregate_version, actual_aggregate_version)
        _require_option(command.option_id, allowed_option_ids)
        stored = self._items.get((case_id, actor_id))
        if stored is None:
            raise DecisionEvaluationResponseConflict("INITIAL_RESPONSE_REQUIRED")
        advice = stored.state.advice_snapshot
        if advice is None:
            raise DecisionEvaluationResponseConflict("ADVICE_REVEAL_REQUIRED")
        if stored.state.final_response is not None:
            raise DecisionEvaluationResponseConflict("FINAL_RESPONSE_IMMUTABLE")
        if (
            command.adoption == "accept"
            and advice.selected_option_id is not None
            and command.option_id != advice.selected_option_id
        ):
            raise DecisionEvaluationResponseConflict("ACCEPT_MUST_MATCH_ADVICE")
        final = DecisionFinalResponseRecord(
            adoption=command.adoption,
            option_id=command.option_id,
            accepted_risks_ko=command.accepted_risks_ko,
            safeguards_ko=command.safeguards_ko,
            rationale_ko=command.rationale_ko,
            difference_reason_ko=command.difference_reason_ko,
            recorded_at=datetime.now(UTC),
        )
        stored.state = stored.state.model_copy(update={"final_response": final})
        stored.final_key = idempotency_key
        stored.final_fingerprint = fingerprint
        self._command_keys[idempotency_key] = ("final", fingerprint)
        return stored.state


class PostgresDecisionEvaluationResponseRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def get(
        self, *, case_id: str, actor_id: str
    ) -> DecisionEvaluationResponseState | None:
        with Session(self.engine) as session:
            row = session.scalar(
                select(DecisionEvaluationResponseRow).where(
                    DecisionEvaluationResponseRow.case_id == case_id,
                    DecisionEvaluationResponseRow.actor_id == actor_id,
                )
            )
            return _row_state(row) if row else None

    def record_initial(
        self,
        *,
        case_id: str,
        actor_id: str,
        idempotency_key: str,
        expected_aggregate_version: int,
        actual_aggregate_version: int,
        allowed_option_ids: set[str],
        command: DecisionInitialResponseCommand,
    ) -> DecisionEvaluationResponseState:
        fingerprint = _command_fingerprint(case_id, actor_id, command)
        _require_version(expected_aggregate_version, actual_aggregate_version)
        _require_option(command.option_id, allowed_option_ids)
        with Session(self.engine) as session, session.begin():
            existing = _row_by_command_key(session, idempotency_key)
            if existing:
                _require_same_command(
                    existing.initial_key,
                    existing.initial_fingerprint,
                    idempotency_key,
                    fingerprint,
                )
                return _row_state(existing)
            row = session.scalar(
                select(DecisionEvaluationResponseRow).where(
                    DecisionEvaluationResponseRow.case_id == case_id,
                    DecisionEvaluationResponseRow.actor_id == actor_id,
                )
            )
            if row:
                raise DecisionEvaluationResponseConflict("INITIAL_RESPONSE_IMMUTABLE")
            now = datetime.now(UTC)
            state = DecisionEvaluationResponseState(
                response_id=str(uuid4()),
                case_id=case_id,
                actor_id=actor_id,
                initial_response=DecisionInitialResponseRecord(
                    option_id=command.option_id,
                    accepted_risks_ko=command.accepted_risks_ko,
                    safeguards_ko=command.safeguards_ko,
                    rationale_ko=command.rationale_ko,
                    recorded_at=now,
                ),
            )
            assert state.initial_response is not None
            session.add(
                DecisionEvaluationResponseRow(
                    response_id=state.response_id,
                    case_id=case_id,
                    actor_id=actor_id,
                    participant_kind=state.participant_kind,
                    interpretation=state.interpretation,
                    initial_response=state.initial_response.model_dump(mode="json"),
                    initial_key=idempotency_key,
                    initial_fingerprint=fingerprint,
                )
            )
            return state

    def reveal_advice(
        self,
        *,
        case_id: str,
        actor_id: str,
        idempotency_key: str,
        expected_aggregate_version: int,
        actual_aggregate_version: int,
        advice: AblationResult,
    ) -> DecisionEvaluationResponseState:
        fingerprint = _advice_fingerprint(case_id, actor_id, advice)
        _require_version(expected_aggregate_version, actual_aggregate_version)
        with Session(self.engine) as session, session.begin():
            existing = _row_by_command_key(session, idempotency_key)
            if existing:
                _require_same_command(
                    existing.reveal_key,
                    existing.reveal_fingerprint,
                    idempotency_key,
                    fingerprint,
                )
                return _row_state(existing)
            row = _locked_row(session, case_id, actor_id)
            if row is None:
                raise DecisionEvaluationResponseConflict("INITIAL_RESPONSE_REQUIRED")
            if row.advice_snapshot is not None:
                raise DecisionEvaluationResponseConflict("ADVICE_REVEAL_IMMUTABLE")
            row.advice_snapshot = _build_advice_snapshot(advice).model_dump(mode="json")
            row.reveal_key = idempotency_key
            row.reveal_fingerprint = fingerprint
            session.flush()
            return _row_state(row)

    def record_final(
        self,
        *,
        case_id: str,
        actor_id: str,
        idempotency_key: str,
        expected_aggregate_version: int,
        actual_aggregate_version: int,
        allowed_option_ids: set[str],
        command: DecisionFinalResponseCommand,
    ) -> DecisionEvaluationResponseState:
        fingerprint = _command_fingerprint(case_id, actor_id, command)
        _require_version(expected_aggregate_version, actual_aggregate_version)
        _require_option(command.option_id, allowed_option_ids)
        with Session(self.engine) as session, session.begin():
            existing = _row_by_command_key(session, idempotency_key)
            if existing:
                _require_same_command(
                    existing.final_key,
                    existing.final_fingerprint,
                    idempotency_key,
                    fingerprint,
                )
                return _row_state(existing)
            row = _locked_row(session, case_id, actor_id)
            if row is None:
                raise DecisionEvaluationResponseConflict("INITIAL_RESPONSE_REQUIRED")
            if row.advice_snapshot is None:
                raise DecisionEvaluationResponseConflict("ADVICE_REVEAL_REQUIRED")
            if row.final_response is not None:
                raise DecisionEvaluationResponseConflict("FINAL_RESPONSE_IMMUTABLE")
            advice = DecisionAdviceSnapshot.model_validate(row.advice_snapshot)
            if (
                command.adoption == "accept"
                and advice.selected_option_id is not None
                and command.option_id != advice.selected_option_id
            ):
                raise DecisionEvaluationResponseConflict("ACCEPT_MUST_MATCH_ADVICE")
            final = DecisionFinalResponseRecord(
                adoption=command.adoption,
                option_id=command.option_id,
                accepted_risks_ko=command.accepted_risks_ko,
                safeguards_ko=command.safeguards_ko,
                rationale_ko=command.rationale_ko,
                difference_reason_ko=command.difference_reason_ko,
                recorded_at=datetime.now(UTC),
            )
            row.final_response = final.model_dump(mode="json")
            row.final_key = idempotency_key
            row.final_fingerprint = fingerprint
            session.flush()
            return _row_state(row)


def _require_version(expected: int, actual: int) -> None:
    if expected != actual:
        raise DecisionEvaluationResponseConflict("CASE_VERSION_CONFLICT")


def _require_option(option_id: str, allowed_option_ids: set[str]) -> None:
    if option_id not in allowed_option_ids:
        raise DecisionEvaluationResponseConflict("OPTION_NOT_FOUND")


def _command_fingerprint(
    case_id: str,
    actor_id: str,
    command: DecisionInitialResponseCommand | DecisionFinalResponseCommand,
) -> str:
    payload = command.model_dump(mode="json")
    value = json.dumps(
        {"case_id": case_id, "actor_id": actor_id, "command": payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(value.encode()).hexdigest()


def _advice_fingerprint(
    case_id: str, actor_id: str, advice: AblationResult
) -> str:
    payload = json.dumps(
        advice.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(f"{case_id}|{actor_id}|{payload}".encode()).hexdigest()


def _build_advice_snapshot(advice: AblationResult) -> DecisionAdviceSnapshot:
    fingerprint = hashlib.sha256(
        json.dumps(
            advice.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return DecisionAdviceSnapshot(
        advice_snapshot_id=fingerprint,
        decision_type=str(advice.decision.decision_type),
        selected_option_id=advice.decision.selected_option_id,
        decision_source=advice.decision.decision_source,
        revealed_at=datetime.now(UTC),
    )


def _locked_row(
    session: Session, case_id: str, actor_id: str
) -> DecisionEvaluationResponseRow | None:
    return session.scalar(
        select(DecisionEvaluationResponseRow)
        .where(
            DecisionEvaluationResponseRow.case_id == case_id,
            DecisionEvaluationResponseRow.actor_id == actor_id,
        )
        .with_for_update()
    )


def _row_by_command_key(
    session: Session, idempotency_key: str
) -> DecisionEvaluationResponseRow | None:
    return session.scalar(
        select(DecisionEvaluationResponseRow).where(
            (DecisionEvaluationResponseRow.initial_key == idempotency_key)
            | (DecisionEvaluationResponseRow.reveal_key == idempotency_key)
            | (DecisionEvaluationResponseRow.final_key == idempotency_key)
        )
    )


def _require_same_command(
    stored_key: str | None,
    stored_fingerprint: str | None,
    idempotency_key: str,
    fingerprint: str,
) -> None:
    if stored_key != idempotency_key or stored_fingerprint != fingerprint:
        raise DecisionEvaluationResponseConflict("IDEMPOTENCY_KEY_REUSED")


def _row_state(row: DecisionEvaluationResponseRow) -> DecisionEvaluationResponseState:
    return DecisionEvaluationResponseState(
        response_id=row.response_id,
        case_id=row.case_id,
        actor_id=row.actor_id,
        participant_kind=row.participant_kind,
        interpretation=row.interpretation,
        initial_response=row.initial_response,
        advice_snapshot=row.advice_snapshot,
        final_response=row.final_response,
    )
