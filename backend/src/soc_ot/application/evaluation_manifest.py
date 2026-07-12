import hashlib
import json
from pathlib import Path

import yaml

from soc_ot.agents.prompts import PROMPT_BUNDLE_HASH, PROMPT_BUNDLE_VERSION
from soc_ot.infrastructure.fixtures import FixtureRepository

PARTITIONS = {
    "development": ["CASE-VR-001", "CASE-VR-002", "CASE-VR-003"],
    "validation": ["CASE-VR-004", "CASE-VR-005"],
    "sealed-unseen": ["CASE-HO-001", "CASE-HO-002", "CASE-HO-003"],
}


def _model_hash(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def freeze_evaluation_manifest(fixtures_root: Path, output_path: Path) -> dict[str, object]:
    repository = FixtureRepository(fixtures_root)
    cases: list[dict[str, object]] = []
    for partition, case_ids in PARTITIONS.items():
        for case_id in case_ids:
            observable = repository.load_observable(case_id)
            hidden = repository.load_hidden(case_id)
            expected = repository.load_expected(case_id)
            repository.validate_case(case_id, include_hidden=True)
            cases.append(
                {
                    "case_id": case_id,
                    "partition": partition,
                    "observable_sha256": _model_hash(observable.model_dump(mode="json")),
                    "hidden_sha256": _model_hash(hidden.model_dump(mode="json")),
                    "expected_sha256": _model_hash(expected.model_dump(mode="json")),
                }
            )
    manifest: dict[str, object] = {
        "evaluation_release": "eval-2026-07-11.1",
        "schema_version": "evaluation-manifest.v1",
        "policy_version": "decision-policy.v1",
        "prompt_bundle_version": PROMPT_BUNDLE_VERSION,
        "prompt_bundle_hash": PROMPT_BUNDLE_HASH,
        "cases": cases,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return manifest


def validate_evaluation_manifest(fixtures_root: Path, manifest_path: Path) -> None:
    existing = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    temporary = manifest_path.with_suffix(".check.yaml")
    generated = freeze_evaluation_manifest(fixtures_root, temporary)
    temporary.unlink()
    if existing != generated:
        raise ValueError("evaluation manifest hashes are stale")
