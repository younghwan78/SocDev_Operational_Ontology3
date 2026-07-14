import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Literal

import yaml
from pydantic import Field, field_validator, model_validator

from soc_ot.agents.prompts import PROMPT_BUNDLE_HASH, PROMPT_BUNDLE_VERSION
from soc_ot.domain.models import ObservableCase, StrictModel
from soc_ot.infrastructure.fixtures import FixtureRepository

PartitionName = Literal["development", "validation", "sealed-unseen"]
DEFAULT_EVALUATION_RELEASE = "eval-2026-07-14.2"


class EvaluationCaseSource(StrictModel):
    case_id: str
    partition: PartitionName
    observable_path: str | None = None
    hidden_path: str | None = None
    expected_path: str | None = None

    @field_validator("observable_path", "hidden_path", "expected_path")
    @classmethod
    def require_safe_relative_path(cls, value: str | None) -> str | None:
        if value is None:
            return value
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value:
            raise ValueError("evaluation source path must be a safe POSIX relative path")
        return value


class EvaluationManifestCase(EvaluationCaseSource):
    observable_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    hidden_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class EvaluationManifest(StrictModel):
    evaluation_release: str
    schema_version: Literal["evaluation-manifest.v1", "evaluation-manifest.v2"]
    policy_version: str
    prompt_bundle_version: str
    prompt_bundle_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    cases: list[EvaluationManifestCase]

    @model_validator(mode="after")
    def validate_release(self) -> "EvaluationManifest":
        case_ids = [item.case_id for item in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("evaluation manifest has duplicate case ids")
        if self.schema_version == "evaluation-manifest.v2" and any(
            not (item.observable_path and item.hidden_path and item.expected_path)
            for item in self.cases
        ):
            raise ValueError("evaluation manifest v2 requires explicit source paths")
        return self


_KNOWN_CASE_IDS = [
    "CASE-VR-001",
    "CASE-VR-002",
    "CASE-VR-003",
    "CASE-VR-004",
    "CASE-VR-005",
    "CASE-HO-001",
    "CASE-HO-002",
    "CASE-HO-003",
]
_DEVELOPMENT_CASE_IDS = ["CASE-DT-001", "CASE-DT-002"]
_SEALED_CASE_IDS = ["CASE-DT-003", "CASE-DT-004"]


def _v2_source(case_id: str, partition: PartitionName) -> EvaluationCaseSource:
    is_development_twin = case_id.startswith("CASE-DT-")
    expected_name = "CASE-VR-005.yaml" if case_id == "CASE-VR-005" else f"{case_id}.yaml"
    return EvaluationCaseSource(
        case_id=case_id,
        partition=partition,
        observable_path=(
            f"cases/development/{case_id}.yaml"
            if is_development_twin
            else f"cases/observable/{case_id}.yaml"
        ),
        hidden_path=(
            f"cases/hidden/v2/{case_id}.yaml"
            if is_development_twin
            else f"cases/hidden/{case_id}.yaml"
        ),
        expected_path=(
            f"expected/v2/{expected_name}"
            if is_development_twin or case_id == "CASE-VR-005"
            else f"expected/{case_id}.yaml"
        ),
    )


V2_CASE_SOURCES = [
    *[_v2_source(case_id, "development") for case_id in _KNOWN_CASE_IDS],
    *[_v2_source(case_id, "validation") for case_id in _DEVELOPMENT_CASE_IDS],
    *[_v2_source(case_id, "sealed-unseen") for case_id in _SEALED_CASE_IDS],
]

PARTITIONS: dict[str, list[str]] = {
    partition: [item.case_id for item in V2_CASE_SOURCES if item.partition == partition]
    for partition in ("development", "validation", "sealed-unseen")
}


def load_evaluation_manifest(manifest_path: Path) -> EvaluationManifest:
    return EvaluationManifest.model_validate(
        yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    )


def manifest_partitions(manifest: EvaluationManifest) -> dict[str, list[str]]:
    return {
        partition: [item.case_id for item in manifest.cases if item.partition == partition]
        for partition in ("development", "validation", "sealed-unseen")
    }


def manifest_case_source(item: EvaluationManifestCase) -> EvaluationCaseSource:
    return EvaluationCaseSource.model_validate(
        item.model_dump(
            mode="json",
            include={
                "case_id",
                "partition",
                "observable_path",
                "hidden_path",
                "expected_path",
            },
        )
    )


def freeze_evaluation_manifest(
    fixtures_root: Path,
    output_path: Path,
    *,
    evaluation_release: str = DEFAULT_EVALUATION_RELEASE,
    case_sources: list[EvaluationCaseSource] | None = None,
) -> EvaluationManifest:
    repository = FixtureRepository(fixtures_root)
    cases = [
        _freeze_case(repository, source)
        for source in (case_sources or V2_CASE_SOURCES)
    ]
    manifest = EvaluationManifest(
        evaluation_release=evaluation_release,
        schema_version="evaluation-manifest.v2",
        policy_version="decision-policy.v1",
        prompt_bundle_version=PROMPT_BUNDLE_VERSION,
        prompt_bundle_hash=PROMPT_BUNDLE_HASH,
        cases=cases,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(manifest.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    return manifest


def validate_evaluation_manifest(
    fixtures_root: Path, manifest_path: Path
) -> EvaluationManifest:
    manifest = load_evaluation_manifest(manifest_path)
    repository = FixtureRepository(fixtures_root)
    failures: list[str] = []
    for item in manifest.cases:
        current = _freeze_case(
            repository,
            manifest_case_source(item),
        )
        for field in ("observable_sha256", "hidden_sha256", "expected_sha256"):
            if getattr(item, field) != getattr(current, field):
                failures.append(f"{item.case_id}:{field}")
    if failures:
        raise ValueError("evaluation manifest hashes are stale: " + ", ".join(failures))
    return manifest


def _freeze_case(
    repository: FixtureRepository, source: EvaluationCaseSource
) -> EvaluationManifestCase:
    observable, hidden, expected = repository.validate_evaluation_case(
        source.case_id,
        observable_path=source.observable_path,
        hidden_path=source.hidden_path,
        expected_path=source.expected_path,
    )
    return EvaluationManifestCase(
        **source.model_dump(mode="python"),
        observable_sha256=_model_hash(_observable_manifest_payload(observable)),
        hidden_sha256=_model_hash(hidden.model_dump(mode="json")),
        expected_sha256=_model_hash(expected.model_dump(mode="json")),
    )


def _model_hash(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _observable_manifest_payload(observable: ObservableCase) -> object:
    """Keep historical v1 hashes stable for newly added empty collections."""
    payload = observable.model_dump(mode="json")
    if not payload["development_actions"]:
        payload.pop("development_actions")
    if not payload["development_events"]:
        payload.pop("development_events")
    return payload
