from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from soc_ot.domain.models import HiddenCase
from soc_ot.infrastructure.fixtures import FixtureRepository
from soc_ot.infrastructure.tables import HiddenCaseRow


class FixtureHiddenCaseReader:
    def __init__(self, fixtures: FixtureRepository) -> None:
        self.fixtures = fixtures

    def get(self, case_id: str) -> HiddenCase | None:
        try:
            return self.fixtures.load_hidden(case_id)
        except FileNotFoundError:
            return None


class PostgresHiddenCaseRepository:
    """Outcome-only repository. Never inject this into role or Chair services."""

    def __init__(self, outcome_engine: Engine) -> None:
        self.engine = outcome_engine

    def get(self, case_id: str) -> HiddenCase | None:
        with Session(self.engine) as session:
            row = session.get(HiddenCaseRow, case_id)
            return HiddenCase.model_validate(row.payload) if row else None

    def upsert(self, hidden_case: HiddenCase) -> None:
        with Session(self.engine) as session, session.begin():
            row = session.get(HiddenCaseRow, hidden_case.case_id)
            if row is None:
                row = HiddenCaseRow(
                    case_id=hidden_case.case_id,
                    fixture_version=hidden_case.fixture_version,
                    payload=hidden_case.model_dump(mode="json"),
                )
                session.add(row)
            else:
                row.fixture_version = hidden_case.fixture_version
                row.payload = hidden_case.model_dump(mode="json")
