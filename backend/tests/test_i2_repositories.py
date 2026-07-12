from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from soc_ot.api.main import create_app
from soc_ot.application.projections import build_workspace_projection
from soc_ot.application.repositories import (
    InMemoryCaseRepository,
    PostgresCaseRepository,
    VersionConflictError,
)
from soc_ot.infrastructure.database import get_runtime_engine
from soc_ot.infrastructure.fixtures import FixtureRepository
from soc_ot.infrastructure.tables import DecisionCaseRow

ROOT = Path(__file__).resolve().parents[2]


def test_in_memory_repository_tracks_version_and_event() -> None:
    case = FixtureRepository(ROOT / "fixtures").load_observable("CASE-VR-001")
    repository = InMemoryCaseRepository()

    stored = repository.save(case, event_type="fixture_imported", expected_aggregate_version=None)

    assert stored.aggregate_version == 1
    assert repository.events == [("CASE-VR-001", 1, "fixture_imported")]
    with pytest.raises(VersionConflictError):
        repository.save(case, event_type="duplicate", expected_aggregate_version=None)


def test_workspace_projection_is_consumer_shaped() -> None:
    case = FixtureRepository(ROOT / "fixtures").load_observable("CASE-VR-001")
    repository = InMemoryCaseRepository()
    stored = repository.save(case, event_type="fixture_imported", expected_aggregate_version=None)

    projection = build_workspace_projection(stored)

    assert projection.case_id == "CASE-VR-001"
    assert projection.aggregate_version == 1
    assert projection.alternative_count == 2
    assert sum(track.blocker_count for track in projection.tracks) == 3


@pytest.mark.postgres
def test_postgres_repository_matches_in_memory() -> None:
    case = FixtureRepository(ROOT / "fixtures").load_observable("CASE-VR-001")
    memory = InMemoryCaseRepository()
    expected = memory.save(case, event_type="fixture_imported", expected_aggregate_version=None)
    postgres = PostgresCaseRepository(get_runtime_engine())
    current = postgres.get(case.case_id)
    actual = postgres.save(
        case,
        event_type="fixture_reimported" if current else "fixture_imported",
        expected_aggregate_version=current.aggregate_version if current else None,
    )

    assert actual.case == expected.case
    assert any(item.case.case_id == memory.list()[0].case.case_id for item in postgres.list())


@pytest.mark.postgres
def test_api_restart_reads_the_same_imported_postgres_state() -> None:
    engine = get_runtime_engine()
    case = FixtureRepository(ROOT / "fixtures").load_observable("CASE-VR-001")
    first_repository = PostgresCaseRepository(engine)
    current = first_repository.get(case.case_id)
    saved = first_repository.save(
        case,
        event_type="restart_gate_import",
        expected_aggregate_version=current.aggregate_version if current else None,
    )

    before_restart = TestClient(create_app(first_repository)).get(
        f"/api/v1/decision-cases/{case.case_id}/workspace"
    )
    after_restart = TestClient(create_app(PostgresCaseRepository(engine))).get(
        f"/api/v1/decision-cases/{case.case_id}/workspace"
    )

    assert before_restart.status_code == 200
    assert after_restart.status_code == 200
    assert after_restart.json() == before_restart.json()
    assert after_restart.json()["aggregate_version"] == saved.aggregate_version


@pytest.mark.postgres
def test_case_row_update_rolls_back_when_domain_event_insert_fails() -> None:
    engine = get_runtime_engine()
    repository = PostgresCaseRepository(engine)
    case = FixtureRepository(ROOT / "fixtures").load_observable("CASE-VR-002")
    current = repository.get(case.case_id)
    assert current is not None

    def fail_domain_event_insert(
        _connection, _cursor, statement, parameters, _context, _executemany
    ) -> None:
        if "INSERT INTO audit.domain_events" in statement:
            raise IntegrityError(statement, parameters, RuntimeError("synthetic failure"))

    event.listen(engine, "before_cursor_execute", fail_domain_event_insert)
    try:
        with pytest.raises(VersionConflictError, match="CASE_VERSION_CONFLICT"):
            repository.save(
                case.model_copy(update={"title_ko": "rollback 되어야 하는 제목"}),
                event_type="atomic_gate_write",
                expected_aggregate_version=current.aggregate_version,
            )
        with Session(engine) as session:
            row = session.scalar(
                select(DecisionCaseRow).where(DecisionCaseRow.case_id == case.case_id)
            )
            assert row is not None
            assert row.aggregate_version == current.aggregate_version
            assert row.title_ko == current.case.title_ko
    finally:
        event.remove(engine, "before_cursor_execute", fail_domain_event_insert)
