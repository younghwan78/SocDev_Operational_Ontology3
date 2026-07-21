import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

from soc_ot.application.project_fixture_contracts import DevelopmentProject


class ProjectVersionConflictError(ValueError):
    pass


@dataclass(frozen=True)
class StoredProject:
    project: DevelopmentProject
    aggregate_version: int
    fixture_hash: str = ""
    contract_version: str = "development-project.v1"


class ProjectRepository(Protocol):
    def get(self, project_id: str) -> StoredProject | None: ...

    def save(
        self,
        project: DevelopmentProject,
        *,
        expected_aggregate_version: int | None,
        fixture_hash: str | None = None,
    ) -> StoredProject: ...

    def list(self) -> list[StoredProject]: ...


class InMemoryProjectRepository:
    def __init__(self) -> None:
        self._items: dict[str, StoredProject] = {}

    def get(self, project_id: str) -> StoredProject | None:
        return self._items.get(project_id)

    def save(
        self,
        project: DevelopmentProject,
        *,
        expected_aggregate_version: int | None,
        fixture_hash: str | None = None,
    ) -> StoredProject:
        current = self._items.get(project.project_id)
        current_version = current.aggregate_version if current else None
        if current_version != expected_aggregate_version:
            raise ProjectVersionConflictError("PROJECT_VERSION_CONFLICT")
        version = 1 if current is None else current.aggregate_version + 1
        stored = StoredProject(
            project=project,
            aggregate_version=version,
            fixture_hash=fixture_hash or project_content_hash(project),
        )
        self._items[project.project_id] = stored
        return stored

    def list(self) -> list[StoredProject]:
        return [self._items[key] for key in sorted(self._items)]


def project_content_hash(project: DevelopmentProject) -> str:
    canonical = json.dumps(
        project.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
