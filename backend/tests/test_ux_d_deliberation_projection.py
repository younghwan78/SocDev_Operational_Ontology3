from pathlib import Path

from fastapi.testclient import TestClient

from soc_ot.agents.providers import ReplayProvider
from soc_ot.api.main import create_app
from soc_ot.application.multi_role import run_ablation, run_dossier_round
from soc_ot.application.packets import build_observable_case_packet
from soc_ot.application.repositories import InMemoryCaseRepository, StoredCase
from soc_ot.application.review_runs import (
    InMemoryReviewRunRepository,
    enqueue_dossier_review,
    enqueue_role_review,
)
from soc_ot.application.workspace_projection_v2 import build_workspace_projection_v2
from soc_ot.domain.models import AgentRunStatus
from soc_ot.infrastructure.fixtures import FixtureRepository

ROOT = Path(__file__).resolve().parents[2]


def _fixtures() -> FixtureRepository:
    return FixtureRepository(ROOT / "fixtures")


def _case_and_dossier():
    case = _fixtures().load_observable("CASE-VR-001")
    packet = build_observable_case_packet(case)
    result = run_ablation(
        packet,
        ReplayProvider(),
        "B3",
        allowed_decision_types=case.allowed_decision_types,
    )
    return case, result.dossier


def test_workspace_projects_option_comparison_and_epistemic_categories() -> None:
    case, dossier = _case_and_dossier()
    workspace = build_workspace_projection_v2(
        StoredCase(case=case, aggregate_version=9),
        content=_fixtures().load_workspace_ux(case.case_id),
        dossier=dossier,
        dossier_run_status=AgentRunStatus.COMPLETED,
    )

    assert workspace.header.workspace_phase == "DOSSIER_READY"
    assert workspace.workflow.primary_action == "VIEW_DOSSIER"
    assert workspace.alternatives.comparison_dimensions_ko == [
        "기대 효과",
        "일정 영향",
        "실패 영향",
        "되돌리기와 전환 비용",
        "필요한 근거",
        "안전 조건",
        "남는 위험",
    ]
    assert all(item.expected_effect_ko for item in workspace.alternatives.items)
    assert all(item.reversibility_ko for item in workspace.alternatives.items)
    assert any(item.recommended for item in workspace.alternatives.items)
    assert {item.epistemic_status for item in workspace.deliberation.epistemic_items} == {
        "fact",
        "inference",
        "assumption",
        "unknown",
    }


def test_dossier_alignment_preserves_dissent_and_keeps_role_originals_in_detail() -> None:
    case, dossier = _case_and_dossier()
    workspace = build_workspace_projection_v2(
        StoredCase(case=case, aggregate_version=9),
        content=_fixtures().load_workspace_ux(case.case_id),
        dossier=dossier,
        dossier_run_status=AgentRunStatus.COMPLETED,
    )
    deliberation = workspace.deliberation

    assert deliberation.alignment_available is True
    assert deliberation.agreement_groups
    assert deliberation.dissent_items
    assert deliberation.role_reviews
    assert deliberation.challenge_changes
    assert "ROLE-" not in deliberation.model_dump_json()
    assert workspace.details.role_originals_available is True


def test_historical_workspace_does_not_leak_later_dossier_or_unversioned_claims() -> None:
    case, dossier = _case_and_dossier()
    workspace = build_workspace_projection_v2(
        StoredCase(case=case, aggregate_version=9),
        at_step=9,
        content=_fixtures().load_workspace_ux(case.case_id),
        dossier=dossier,
        dossier_run_status=AgentRunStatus.COMPLETED,
    )

    assert workspace.deliberation.alignment_available is False
    assert workspace.deliberation.role_reviews == []
    assert all(
        item.epistemic_status in {"fact", "inference"}
        for item in workspace.deliberation.epistemic_items
    )
    assert workspace.details.role_originals_available is False


def test_run_repository_finds_latest_case_scoped_dossier() -> None:
    fixtures = _fixtures()
    cases = InMemoryCaseRepository()
    case = fixtures.load_observable("CASE-VR-001")
    cases.save(case, event_type="fixture_imported", expected_aggregate_version=None)
    runs = InMemoryReviewRunRepository()
    dossier = enqueue_dossier_review(
        cases,
        runs,
        case_id=case.case_id,
        provider="replay",
        model="replay-v1",
        idempotency_key="dossier-latest",
    )
    role = enqueue_role_review(
        cases,
        runs,
        case_id=case.case_id,
        role_id=case.required_role_ids[0],
        provider="replay",
        model="replay-v1",
        idempotency_key="role-latest",
    )

    assert runs.latest_for_case(case.case_id) == role
    assert runs.latest_for_case(case.case_id, run_kind="dossier") == dossier


def test_workspace_api_joins_latest_completed_dossier_projection() -> None:
    fixtures = _fixtures()
    cases = InMemoryCaseRepository()
    case = fixtures.load_observable("CASE-VR-001")
    cases.save(case, event_type="fixture_imported", expected_aggregate_version=None)
    runs = InMemoryReviewRunRepository()
    run = enqueue_dossier_review(
        cases,
        runs,
        case_id=case.case_id,
        provider="replay",
        model="replay-v1",
        idempotency_key="dossier-api",
        topology="B2",
    )
    claimed = runs.claim("worker-ux-d", lease_seconds=30)
    assert claimed is not None and claimed.run_id == run.run_id
    execution = run_dossier_round(
        build_observable_case_packet(case),
        ReplayProvider(),
        "B2",
        allowed_decision_types=case.allowed_decision_types,
    )
    runs.complete(run.run_id, "worker-ux-d", execution)

    response = TestClient(create_app(cases, run_repository=runs)).get(
        "/api/v1/decision-cases/CASE-VR-001/workspace"
    )

    assert response.status_code == 200
    assert response.json()["deliberation"]["alignment_available"] is True
    assert response.json()["details"]["role_originals_available"] is True
