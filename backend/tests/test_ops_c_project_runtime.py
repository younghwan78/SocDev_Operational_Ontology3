from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from soc_ot.api.main import create_app
from soc_ot.application.contracts import CONTRACT_MODELS
from soc_ot.application.project_fixture_contracts import ProjectAttention, RiskLevel
from soc_ot.application.project_operations import (
    ProjectListItemProjection,
    ProjectRiskDetailProjection,
    ProjectRiskSummary,
    ProjectSituationProjection,
    ProjectTimelineProjection,
    build_project_list_item,
    build_project_risk_detail,
    build_project_risks,
    build_project_situation,
    build_project_timeline,
    sort_project_list_items,
)
from soc_ot.application.project_repositories import (
    InMemoryProjectRepository,
    ProjectVersionConflictError,
    StoredProject,
)
from soc_ot.application.repositories import InMemoryCaseRepository
from soc_ot.infrastructure.database import get_runtime_engine
from soc_ot.infrastructure.fixtures import FixtureRepository
from soc_ot.infrastructure.project_repository import PostgresProjectRepository

ROOT = Path(__file__).resolve().parents[2]


def _fixtures() -> FixtureRepository:
    return FixtureRepository(ROOT / "fixtures")


def _stored(project_id: str) -> StoredProject:
    return StoredProject(_fixtures().load_project(project_id), aggregate_version=1)


def test_in_memory_project_repository_tracks_aggregate_version() -> None:
    project = _fixtures().load_project("PROJECT-U")
    repository = InMemoryProjectRepository()

    first = repository.save(project, expected_aggregate_version=None)
    second = repository.save(project, expected_aggregate_version=first.aggregate_version)

    assert first.aggregate_version == 1
    assert len(first.fixture_hash) == 64
    assert first.contract_version == "development-project.v1"
    assert second.aggregate_version == 2
    assert repository.get(project.project_id) == second
    with pytest.raises(ProjectVersionConflictError, match="PROJECT_VERSION_CONFLICT"):
        repository.save(project, expected_aggregate_version=1)


def test_portfolio_attention_is_backend_derived_and_explained() -> None:
    items = sort_project_list_items(
        [build_project_list_item(_stored(project_id)) for project_id in _fixtures().project_ids()]
    )

    assert [item.project_id for item in items] == ["PROJECT-V", "PROJECT-W", "PROJECT-U"]
    assert [item.attention for item in items] == [
        ProjectAttention.BLOCKED,
        ProjectAttention.BLOCKED,
        ProjectAttention.AT_RISK,
    ]
    assert items[0].attention_reasons[0].code == "WORK_ITEM_BLOCKED"
    assert items[0].attention_reasons[0].source_refs == ["WORK-V-PRESI-VERIFY"]
    assert items[2].attention_policy_version == "project-attention.v1"
    assert all(item.attention_reasons for item in items)


def test_risk_policy_orders_by_level_without_composite_score() -> None:
    risks = build_project_risks(_stored("PROJECT-V"))

    assert [item.risk_id for item in risks] == [
        "RISK-V-WRONG-COMMIT",
        "RISK-V-RESOURCE-CONFLICT",
    ]
    assert [item.risk_level for item in risks] == [RiskLevel.CRITICAL, RiskLevel.HIGH]
    assert risks[0].policy_version == "project-risk-order.v1"
    assert "IRREVERSIBLE_COMMITMENT" in risks[0].ranking_reasons
    assert "CROSS-U-FIELD-LESSON" in risks[0].source_refs
    assert all("score" not in item.model_dump(mode="json") for item in risks)


def test_historical_project_resources_share_one_future_leakage_boundary() -> None:
    stored = _stored("PROJECT-U")
    situation = build_project_situation(stored, at_step=34)
    risks = build_project_risks(stored, at_step=34)
    timeline = build_project_timeline(stored, at_step=34)
    detail = build_project_risk_detail(stored, "RISK-U-REPEAT", at_step=34)

    evidence = next(item for item in situation.evidence if item.evidence_id == "EVD-U-LONG-RUN")
    assert evidence.status == "LATE"
    assert evidence.source_ref is None
    assert "RISK-U-NEXT-SILICON" not in {item.risk_id for item in risks}
    assert "EVENT-U-035-EVIDENCE-ARRIVED" not in {item.event_id for item in timeline.events}
    assert detail.risk.status == "OPEN"
    assert detail.risk.missing_evidence_ids == ["EVD-U-LONG-RUN"]
    with pytest.raises(ValueError, match="PROJECT_RISK_NOT_FOUND"):
        build_project_risk_detail(stored, "RISK-U-NEXT-SILICON", at_step=34)


def test_historical_track_status_does_not_reuse_current_blocker_state() -> None:
    situation = build_project_situation(_stored("PROJECT-V"), at_step=20)

    verification = next(
        item for item in situation.tracks if item.track_id == "TRACK-V-VERIF"
    )
    work_item = next(
        item
        for item in situation.work_items
        if item.work_item_id == "WORK-V-PRESI-VERIFY"
    )
    assert work_item.status == "READY"
    assert verification.status == "READY"
    assert verification.blocked_work_item_count == 0


def test_project_read_api_exposes_situation_risk_detail_and_timeline() -> None:
    client = TestClient(create_app(InMemoryCaseRepository()))

    portfolio = client.get("/api/v1/projects")
    situation = client.get("/api/v1/projects/PROJECT-V/situation")
    risks = client.get("/api/v1/projects/PROJECT-V/risks")
    detail = client.get("/api/v1/projects/PROJECT-V/risks/RISK-V-WRONG-COMMIT")
    timeline = client.get("/api/v1/projects/PROJECT-V/timeline?at_step=20")

    assert portfolio.status_code == 200
    assert len(portfolio.json()) == 3
    assert situation.json()["attention"] == "BLOCKED"
    assert risks.json()[0]["risk_level"] == "CRITICAL"
    assert detail.json()["decisions"][0]["href"] == "/decisions/CASE-HO-002"
    assert detail.json()["cross_project_sources"][0]["source_project_id"] == "PROJECT-U"
    assert detail.json()["treatment_actions"][0]["rollback_condition"]
    assert timeline.json()["reconstructed_at_step"] == 20
    assert all(item["observed_at_step"] <= 20 for item in timeline.json()["events"])


def test_project_read_api_has_stable_not_found_and_step_errors() -> None:
    client = TestClient(create_app(InMemoryCaseRepository()))

    missing_project = client.get("/api/v1/projects/MISSING/situation")
    missing_risk = client.get("/api/v1/projects/PROJECT-U/risks/MISSING")
    future = client.get("/api/v1/projects/PROJECT-W/timeline?at_step=11")

    assert missing_project.status_code == 404
    assert missing_project.json()["detail"]["code"] == "PROJECT_NOT_FOUND"
    assert missing_risk.status_code == 404
    assert missing_risk.json()["detail"]["code"] == "PROJECT_RISK_NOT_FOUND"
    assert future.status_code == 422
    assert future.json()["detail"]["code"] == "PROJECT_STEP_OUT_OF_RANGE"


def test_project_contracts_are_registered_without_changing_observable_case_v1() -> None:
    assert CONTRACT_MODELS["project-list-item.v1"] is ProjectListItemProjection
    assert CONTRACT_MODELS["project-situation.v1"] is ProjectSituationProjection
    assert CONTRACT_MODELS["project-risk-summary.v1"] is ProjectRiskSummary
    assert CONTRACT_MODELS["project-risk-detail.v1"] is ProjectRiskDetailProjection
    assert CONTRACT_MODELS["project-timeline.v1"] is ProjectTimelineProjection
    assert _fixtures().load_observable("CASE-VR-001").schema_version == "observable-case.v1"
    assert len(_fixtures().case_ids()) + len(_fixtures().development_case_ids()) == 12


@pytest.mark.postgres
def test_postgres_project_repository_matches_in_memory() -> None:
    project = _fixtures().load_project("PROJECT-U")
    memory = InMemoryProjectRepository()
    expected = memory.save(project, expected_aggregate_version=None)
    postgres = PostgresProjectRepository(get_runtime_engine())
    current = postgres.get(project.project_id)
    actual = postgres.save(
        project,
        expected_aggregate_version=current.aggregate_version if current else None,
    )

    assert actual.project == expected.project
    assert len(actual.fixture_hash) == 64
    assert actual.contract_version == "development-project.v1"
    assert any(item.project.project_id == project.project_id for item in postgres.list())


@pytest.mark.postgres
def test_project_api_restart_reads_same_postgres_projection() -> None:
    engine = get_runtime_engine()
    first = TestClient(
        create_app(
            InMemoryCaseRepository(),
            project_repository=PostgresProjectRepository(engine),
        )
    ).get("/api/v1/projects/PROJECT-U/situation")
    restarted = TestClient(
        create_app(
            InMemoryCaseRepository(),
            project_repository=PostgresProjectRepository(engine),
        )
    ).get("/api/v1/projects/PROJECT-U/situation")

    assert first.status_code == 200
    assert restarted.status_code == 200
    assert restarted.json() == first.json()
