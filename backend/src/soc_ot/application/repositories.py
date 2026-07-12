from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from soc_ot.domain.models import ObservableCase
from soc_ot.infrastructure.tables import DecisionCaseRow, DomainEventRow


class VersionConflictError(ValueError):
    pass


@dataclass(frozen=True)
class StoredCase:
    case: ObservableCase
    aggregate_version: int


class CaseRepository(Protocol):
    def get(self, case_id: str) -> StoredCase | None: ...

    def save(
        self,
        case: ObservableCase,
        *,
        event_type: str,
        expected_aggregate_version: int | None,
    ) -> StoredCase: ...

    def list(self) -> list[StoredCase]: ...


class InMemoryCaseRepository:
    def __init__(self) -> None:
        self._items: dict[str, StoredCase] = {}
        self.events: list[tuple[str, int, str]] = []

    def get(self, case_id: str) -> StoredCase | None:
        return self._items.get(case_id)

    def save(
        self,
        case: ObservableCase,
        *,
        event_type: str,
        expected_aggregate_version: int | None,
    ) -> StoredCase:
        current = self._items.get(case.case_id)
        current_version = current.aggregate_version if current else None
        if current_version != expected_aggregate_version:
            raise VersionConflictError("CASE_VERSION_CONFLICT")
        version = 1 if current is None else current.aggregate_version + 1
        stored = StoredCase(case=case, aggregate_version=version)
        self._items[case.case_id] = stored
        self.events.append((case.case_id, version, event_type))
        return stored

    def list(self) -> list[StoredCase]:
        return [self._items[key] for key in sorted(self._items)]


class PostgresCaseRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def get(self, case_id: str) -> StoredCase | None:
        with Session(self.engine) as session:
            row = session.get(DecisionCaseRow, case_id)
            return _stored_from_row(row) if row else None

    def save(
        self,
        case: ObservableCase,
        *,
        event_type: str,
        expected_aggregate_version: int | None,
    ) -> StoredCase:
        try:
            with Session(self.engine) as session, session.begin():
                row = session.scalar(
                    select(DecisionCaseRow)
                    .where(DecisionCaseRow.case_id == case.case_id)
                    .with_for_update()
                )
                current_version = row.aggregate_version if row else None
                if current_version != expected_aggregate_version:
                    raise VersionConflictError("CASE_VERSION_CONFLICT")
                version = 1 if row is None else row.aggregate_version + 1
                payload = case.model_dump(mode="json")
                if row is None:
                    row = DecisionCaseRow(
                        case_id=case.case_id,
                        fixture_version=case.fixture_version,
                        aggregate_version=version,
                        current_step=case.current_step,
                        status=case.status,
                        title_ko=case.title_ko,
                        payload=payload,
                    )
                    session.add(row)
                else:
                    row.fixture_version = case.fixture_version
                    row.aggregate_version = version
                    row.current_step = case.current_step
                    row.status = case.status
                    row.title_ko = case.title_ko
                    row.payload = payload
                session.add(
                    DomainEventRow(
                        event_id=f"{case.case_id}:{version}:{event_type}",
                        case_id=case.case_id,
                        aggregate_version=version,
                        event_type=event_type,
                        payload={"fixture_version": case.fixture_version},
                    )
                )
            return StoredCase(case=case, aggregate_version=version)
        except IntegrityError as error:
            raise VersionConflictError("CASE_VERSION_CONFLICT") from error

    def list(self) -> list[StoredCase]:
        with Session(self.engine) as session:
            rows = session.scalars(select(DecisionCaseRow).order_by(DecisionCaseRow.case_id)).all()
            return [_stored_from_row(row) for row in rows]


def _stored_from_row(row: DecisionCaseRow) -> StoredCase:
    return StoredCase(
        case=ObservableCase.model_validate(row.payload), aggregate_version=row.aggregate_version
    )

