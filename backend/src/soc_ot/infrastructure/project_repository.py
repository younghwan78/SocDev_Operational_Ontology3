from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from soc_ot.application.project_fixture_contracts import DevelopmentProject
from soc_ot.application.project_repositories import (
    ProjectVersionConflictError,
    StoredProject,
    project_content_hash,
)
from soc_ot.infrastructure.tables import DevelopmentProjectRow


class PostgresProjectRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def get(self, project_id: str) -> StoredProject | None:
        with Session(self.engine) as session:
            row = session.get(DevelopmentProjectRow, project_id)
            return _stored_from_row(row) if row else None

    def save(
        self,
        project: DevelopmentProject,
        *,
        expected_aggregate_version: int | None,
        fixture_hash: str | None = None,
    ) -> StoredProject:
        try:
            with Session(self.engine) as session, session.begin():
                row = session.scalar(
                    select(DevelopmentProjectRow)
                    .where(DevelopmentProjectRow.project_id == project.project_id)
                    .with_for_update()
                )
                current_version = row.aggregate_version if row else None
                if current_version != expected_aggregate_version:
                    raise ProjectVersionConflictError("PROJECT_VERSION_CONFLICT")
                version = 1 if row is None else row.aggregate_version + 1
                payload = project.model_dump(mode="json")
                resolved_hash = fixture_hash or project_content_hash(project)
                if row is None:
                    row = DevelopmentProjectRow(
                        project_id=project.project_id,
                        fixture_version=project.fixture_version,
                        aggregate_version=version,
                        current_step=project.current_step,
                        lifecycle_stage=project.lifecycle_stage,
                        title_ko=project.title_ko,
                        fixture_hash=resolved_hash,
                        contract_version=project.schema_version,
                        payload=payload,
                    )
                    session.add(row)
                else:
                    row.fixture_version = project.fixture_version
                    row.aggregate_version = version
                    row.current_step = project.current_step
                    row.lifecycle_stage = project.lifecycle_stage
                    row.title_ko = project.title_ko
                    row.fixture_hash = resolved_hash
                    row.contract_version = project.schema_version
                    row.payload = payload
            return StoredProject(
                project=project,
                aggregate_version=version,
                fixture_hash=resolved_hash,
                contract_version=project.schema_version,
            )
        except IntegrityError as error:
            raise ProjectVersionConflictError("PROJECT_VERSION_CONFLICT") from error

    def list(self) -> list[StoredProject]:
        with Session(self.engine) as session:
            rows = session.scalars(
                select(DevelopmentProjectRow).order_by(DevelopmentProjectRow.project_id)
            ).all()
            return [_stored_from_row(row) for row in rows]


def _stored_from_row(row: DevelopmentProjectRow) -> StoredProject:
    return StoredProject(
        project=DevelopmentProject.model_validate(row.payload),
        aggregate_version=row.aggregate_version,
        fixture_hash=row.fixture_hash,
        contract_version=row.contract_version,
    )
