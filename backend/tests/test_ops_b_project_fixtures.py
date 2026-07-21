import hashlib
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from soc_ot.application.contracts import CONTRACT_MODELS
from soc_ot.application.project_fixture_contracts import (
    DevelopmentProject,
    EvidenceStatus,
    ProjectLifecycleStage,
    RiskStatus,
    reconstruct_project_fixture_at_step,
)
from soc_ot.infrastructure.fixtures import FixtureRepository

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"
PROJECTS = FIXTURES / "projects"


def _repository() -> FixtureRepository:
    return FixtureRepository(FIXTURES)


def _payload(project_id: str) -> dict[str, object]:
    loaded = yaml.safe_load((PROJECTS / f"{project_id}.yaml").read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_project_corpus_is_lifecycle_and_evidence_distinct() -> None:
    projects = _repository().validate_project_corpus()

    assert [item.project_id for item in projects] == ["PROJECT-U", "PROJECT-V", "PROJECT-W"]
    assert {item.lifecycle_stage for item in projects} == set(ProjectLifecycleStage)
    evidence_types = {
        project.project_id: {item.evidence_type for item in project.evidence}
        for project in projects
    }
    assert "field_measurement" in evidence_types["PROJECT-U"]
    assert "presilicon_model" in evidence_types["PROJECT-V"]
    assert {"architecture_model", "historical_lesson"} <= evidence_types["PROJECT-W"]


def test_project_corpus_covers_required_operational_patterns_without_scores() -> None:
    projects = _repository().validate_project_corpus()

    assert {item.status for project in projects for item in project.evidence} == set(
        EvidenceStatus
    )
    assert {item.status for project in projects for item in project.risks} == set(RiskStatus)
    event_types = {
        str(item.event_type) for project in projects for item in project.development_events
    }
    assert {"REWORK", "RESOURCE_CONFLICT", "EVIDENCE_CHANGE"} <= event_types
    assert any(project.cross_project_sources for project in projects)
    for project in projects:
        for risk in project.risks:
            fields = risk.model_dump(mode="json")
            assert "risk_level" not in fields
            assert "attention" not in fields
            assert "score" not in fields


def test_project_risk_provenance_reaches_milestone_and_decision() -> None:
    projects = _repository().validate_project_corpus()

    paths = []
    for project in projects:
        issue_ids = {item.issue_id for item in project.issues}
        milestone_ids = {item.milestone_id for item in project.milestones}
        decision_ids = {item.case_id for item in project.decision_case_refs}
        for risk in project.risks:
            if (
                set(risk.source_issue_ids) <= issue_ids
                and risk.source_issue_ids
                and set(risk.affected_milestone_ids) <= milestone_ids
                and risk.affected_milestone_ids
                and set(risk.treatment_decision_case_ids) <= decision_ids
                and risk.treatment_decision_case_ids
            ):
                paths.append((project.project_id, risk.risk_id))
    assert {project_id for project_id, _ in paths} == {"PROJECT-U", "PROJECT-V"}


def test_cross_project_lineage_resolves_to_source_event() -> None:
    projects = _repository().validate_project_corpus()
    project_v = next(item for item in projects if item.project_id == "PROJECT-V")
    source = project_v.cross_project_sources[0]
    project_u = next(item for item in projects if item.project_id == source.source_project_id)

    assert source.source_event_id in {item.event_id for item in project_u.development_events}
    risk = next(item for item in project_v.risks if item.risk_id in source.target_risk_ids)
    assert source.source_id in risk.cross_project_source_ids


def test_historical_reconstruction_hides_future_evidence_and_decisions() -> None:
    project_u = _repository().load_project("PROJECT-U")
    before_arrival = reconstruct_project_fixture_at_step(project_u, 34)

    assert before_arrival.evidence_states["EVD-U-LONG-RUN"].status is EvidenceStatus.LATE
    assert "EVD-U-LONG-RUN" not in before_arrival.available_evidence_source_refs
    assert "CLM-U-MITIGATION" not in before_arrival.claim_ids
    assert "RISK-U-NEXT-SILICON" not in before_arrival.risk_states
    assert "EVENT-U-035-EVIDENCE-ARRIVED" not in before_arrival.event_ids

    project_w = _repository().load_project("PROJECT-W")
    before_requirement_gap = reconstruct_project_fixture_at_step(project_w, 5)
    assert "ISSUE-W-REQUIREMENT-GAP" not in before_requirement_gap.issue_states
    assert before_requirement_gap.risk_states["RISK-W-LATE-REQUIREMENT"].status is RiskStatus.OPEN
    assert "CASE-VR-005" not in before_requirement_gap.decision_case_ids


def test_project_contract_rejects_dangling_reference_and_discontinuous_history() -> None:
    dangling = _payload("PROJECT-U")
    assert isinstance(dangling["risks"], list)
    dangling["risks"][0]["affected_milestone_ids"] = ["MISSING"]  # type: ignore[index]
    with pytest.raises(ValidationError, match="unknown risk milestone reference"):
        DevelopmentProject.model_validate(dangling)

    discontinuous = _payload("PROJECT-U")
    assert isinstance(discontinuous["development_events"], list)
    discontinuous["development_events"][4]["evidence_changes"][0]["before"] = {  # type: ignore[index]
        "status": "REQUESTED",
        "expected_at_step": 33,
    }
    with pytest.raises(ValidationError, match="project event chain is discontinuous"):
        DevelopmentProject.model_validate(discontinuous)


def test_development_project_contract_and_generated_schema_are_registered() -> None:
    assert CONTRACT_MODELS["development-project.v1"] is DevelopmentProject
    assert (ROOT / "contracts/generated/development-project.v1.schema.json").exists()


def test_project_manifest_pins_fixture_and_reference_hashes() -> None:
    manifest = yaml.safe_load((PROJECTS / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "development-project-manifest.v1"
    assert manifest["reference"]["usage"] == "top-level events idea catalog only"
    assert (
        manifest["reference"]["sha256"]
        == "108e5bfc2311b90e0264ed470d081920f4f414cbe3072f663dec47abeba72759"
    )
    for entry in manifest["projects"]:
        actual = hashlib.sha256((PROJECTS / entry["path"]).read_bytes()).hexdigest()
        assert actual == entry["sha256"]


def test_ops_b_does_not_change_ux_h_baseline() -> None:
    baseline = FIXTURES / "usability/CASE-VR-001.baseline-pack.v1.yaml"
    assert hashlib.sha256(baseline.read_bytes()).hexdigest() == (
        "658c4d87f0ce5fb863c2635232ce41bec06fa95bd0ea0918d353da08115ef70c"
    )
