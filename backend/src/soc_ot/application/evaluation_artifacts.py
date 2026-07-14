import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from pydantic import BaseModel

from soc_ot.agents.prompts import PROMPT_BUNDLE_HASH, PROMPT_BUNDLE_VERSION


def write_evaluation_artifacts(
    summary: BaseModel,
    *,
    manifest_path: Path,
    output_root: Path,
    provider: str,
    model_identifier: str,
    runtime_settings: dict[str, object],
    run_id: str | None = None,
    batch_estimate: BaseModel | None = None,
) -> Path:
    """Write one immutable, self-describing evaluation result directory."""
    manifest_bytes = manifest_path.read_bytes()
    manifest_value: object = yaml.safe_load(manifest_bytes)
    if not isinstance(manifest_value, dict):
        raise ValueError("evaluation manifest has no release identifier")
    manifest = {str(key): value for key, value in manifest_value.items()}
    release_value = manifest.get("evaluation_release")
    if not isinstance(release_value, str):
        raise ValueError("evaluation manifest has no release identifier")
    release_id: str = release_value
    actual_run_id = run_id or _new_run_id(provider)
    target = output_root / release_id / actual_run_id
    target.mkdir(parents=True, exist_ok=False)

    payload = summary.model_dump(mode="json")
    results = payload.get("results", [])
    if not isinstance(results, list):
        raise ValueError("evaluation summary results must be a list")
    failures = payload.get("failures", [])
    if not isinstance(failures, list):
        raise ValueError("evaluation summary failures must be a list")

    (target / "manifest.snapshot.yaml").write_bytes(manifest_bytes)
    environment = {
        "schema_version": "evaluation-environment.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "code_revision": _source_revision(manifest_path.parents[2]),
        "provider": provider,
        "model_identifier": model_identifier,
        "prompt_bundle_version": PROMPT_BUNDLE_VERSION,
        "prompt_bundle_hash": PROMPT_BUNDLE_HASH,
        "contract_versions": {
            "observable_case_packet": "observable-case-packet.v1",
            "case_evaluation": "case-evaluation.v1",
        },
        "policy_version": manifest.get("policy_version", "decision-policy.v1"),
        "runtime_settings": runtime_settings,
        "batch_estimate": (
            batch_estimate.model_dump(mode="json") if batch_estimate is not None else None
        ),
        "actual": {
            "result_count": len(results),
            "failure_count": len(failures),
            "estimated_cost_usd": float(payload.get("estimated_cost_usd", 0.0)),
        },
    }
    _write_json(target / "environment.json", environment)
    with (target / "normalized_results.jsonl").open("x", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")

    process_scores = [_score_projection(item, "process_evaluation") for item in results]
    outcome_scores = [_score_projection(item, "outcome_evaluation") for item in results]
    selected_topology = payload.get("selected_topology")
    violations = _policy_violations(
        results,
        selected_topology=(
            selected_topology if isinstance(selected_topology, str) else None
        ),
    )
    _write_json(target / "process_scores.json", process_scores)
    _write_json(target / "outcome_scores.json", outcome_scores)
    _write_json(target / "policy_violations.json", violations)
    if failures:
        _write_json(target / "runtime_failures.json", failures)
    (target / "report.md").write_text(
        _render_report(
            release_id=release_id,
            run_id=actual_run_id,
            provider=provider,
            model_identifier=model_identifier,
            results=results,
            failures=failures,
            violations=violations,
            payload=payload,
        ),
        encoding="utf-8",
    )
    return target


def _new_run_id(provider: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{provider}-{uuid4().hex[:8]}"


def _source_revision(root: Path) -> str:
    digest = hashlib.sha256()
    candidates = [root / "pyproject.toml", root / "uv.lock"]
    candidates.extend(sorted((root / "backend" / "src").rglob("*.py")))
    for path in candidates:
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _score_projection(item: object, key: str) -> dict[str, object]:
    if not isinstance(item, dict):
        return {"case_id": "unknown", "error": "INVALID_RESULT"}
    score = item.get(key, {})
    return {
        "case_id": item.get("case_id", "unknown"),
        "partition": item.get("partition", "unknown"),
        "topology": item.get("topology", "unknown"),
        **(score if isinstance(score, dict) else {"error": "INVALID_SCORE"}),
    }


def _policy_violations(
    results: list[object], *, selected_topology: str | None = None
) -> list[dict[str, object]]:
    violations: list[dict[str, object]] = []
    for item in results:
        if not isinstance(item, dict):
            violations.append({"case_id": "unknown", "code": "CONTRACT_INVALID"})
            continue
        if selected_topology is not None and item.get("topology") != selected_topology:
            continue
        process = item.get("process_evaluation", {})
        if not isinstance(process, dict):
            violations.append(
                {"case_id": item.get("case_id", "unknown"), "code": "CONTRACT_INVALID"}
            )
            continue
        for field, value in process.items():
            if field != "passed" and value is False:
                violations.append(
                    {
                        "case_id": item.get("case_id", "unknown"),
                        "topology": item.get("topology", "unknown"),
                        "code": f"PROCESS_{field.upper()}",
                    }
                )
    return violations


def _render_report(
    *,
    release_id: str,
    run_id: str,
    provider: str,
    model_identifier: str,
    results: list[object],
    failures: list[object],
    violations: list[dict[str, object]],
    payload: dict[str, Any],
) -> str:
    selected_topology = payload.get("selected_topology")
    gate_results = [
        item
        for item in results
        if isinstance(item, dict)
        and (
            not isinstance(selected_topology, str)
            or item.get("topology") == selected_topology
        )
    ]
    passed = sum(bool(item.get("passed")) for item in gate_results)
    total_runs = int(payload.get("total_runs", len(results)))
    gate = bool(
        payload.get(
            "release_gate_passed",
            passed == total_runs and not violations and not failures,
        )
    ) and not failures
    topology_lines = (
        f"- Selected topology: `{selected_topology}`\n"
        f"- Stop rule: `{payload.get('stop_rule', 'unknown')}`\n"
        "- Scope: adjacent-topology ablation; stability is not evaluated here\n"
        if isinstance(selected_topology, str)
        else ""
    )
    return (
        "# Evaluation report\n\n"
        f"> Release: `{release_id}`  \n"
        f"> Run: `{run_id}`  \n"
        f"> Provider/model: `{provider}` / `{model_identifier}`\n\n"
        "## Result\n\n"
        f"- Gate: **{'PASS' if gate else 'FAIL'}**\n"
        + topology_lines
        + f"- Selected case runs passed: {passed}/{len(gate_results)}\n"
        f"- Total comparison runs: {total_runs}\n"
        f"- Runtime failures: {len(failures)}\n"
        f"- Policy violations: {len(violations)}\n"
        f"- Estimated provider cost: ${float(payload.get('estimated_cost_usd', 0.0)):.4f}\n\n"
        "Process and outcome scores are intentionally reported separately. A sound process can "
        "still encounter a poor hidden outcome under uncertainty.\n"
    )


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
