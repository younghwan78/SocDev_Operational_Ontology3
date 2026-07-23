from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from soc_ot.application.contracts import CONTRACT_MODELS
from soc_ot.application.project_fixture_contracts import DevelopmentProject
from soc_ot.application.usability_study import (
    BoundaryClassification,
    ParticipantKind,
    ProjectUsabilityBaselinePack,
    ProjectUsabilityStudyProtocol,
    SessionStatus,
    StudyCondition,
    TaskScore,
    UsabilityEvent,
    UsabilityEventType,
    UsabilityReviewerRubric,
    UsabilitySession,
    UsabilityStudyProtocol,
    UsabilityStudyRelease,
    UsabilityTaskResult,
    create_session_template,
    project_sha256,
    render_baseline_markdown,
    render_session_guide,
    render_study_report,
    summarize_sessions,
    validate_project_study_bundle,
    validate_session,
    validate_study_materials,
)
from soc_ot.cli.main import main
from soc_ot.domain.models import ObservableCase

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_V2 = ROOT / "fixtures/usability/OPS-F-20260722.protocol.v2.yaml"
BASELINE_V2 = ROOT / "fixtures/usability/PROJECT-OPERATIONS.baseline-pack.v2.yaml"
RELEASE_V2 = ROOT / "fixtures/usability/UX-I-20260724.release.v1.yaml"
RUBRIC_V2 = ROOT / "fixtures/usability/OPS-F-20260722.reviewer-rubric.v1.yaml"
PROTOCOL_V1 = ROOT / "fixtures/usability/UX-H-20260719.protocol.yaml"
BASELINE_V1 = ROOT / "fixtures/usability/CASE-VR-001.baseline-pack.v1.yaml"


def _v2_materials() -> tuple[
    ProjectUsabilityStudyProtocol,
    ProjectUsabilityBaselinePack,
    dict[str, DevelopmentProject],
]:
    protocol, pack, projects = validate_study_materials(
        ROOT / "fixtures", PROTOCOL_V2, BASELINE_V2
    )
    assert isinstance(protocol, ProjectUsabilityStudyProtocol)
    assert isinstance(pack, ProjectUsabilityBaselinePack)
    assert isinstance(projects, dict)
    return protocol, pack, projects


def _completed_session(
    protocol: ProjectUsabilityStudyProtocol,
    *,
    condition: StudyCondition,
    participant_code: str,
) -> UsabilitySession:
    draft = create_session_template(
        protocol,
        session_id=f"SESSION-{condition}-{participant_code}",
        condition=condition,
        participant_code=participant_code,
        participant_kind=ParticipantKind.PROXY,
    )
    base = datetime(2026, 7, 22, 6, 0, tzinfo=UTC)
    events: list[UsabilityEvent] = []
    results: list[UsabilityTaskResult] = []
    for index, task in enumerate(protocol.tasks):
        started = base + timedelta(minutes=index)
        event_types = (
            UsabilityEventType.TASK_STARTED,
            UsabilityEventType.ANSWER_SUBMITTED,
            UsabilityEventType.REVIEWER_RESPONSE_RECORDED,
            UsabilityEventType.TASK_ENDED,
        )
        events.extend(
            UsabilityEvent(
                event_id=f"{participant_code}-{task.task_id}-{event_type}",
                event_type=event_type,
                task_id=task.task_id,
                occurred_at=started + timedelta(seconds=offset * 10),
                detail_ko="OPS-F test observation",
            )
            for offset, event_type in enumerate(event_types)
        )
        results.append(
            UsabilityTaskResult(
                task_id=task.task_id,
                answer_ko="실제 session에서 participant가 기록할 답변",
                score=TaskScore.PASS,
                boundary_classification=(
                    task.expected_boundary_classification
                    or BoundaryClassification.NOT_APPLICABLE
                ),
                safeguard_completeness=(
                    1.0 if task.task_id == "P07_TREATMENT_AND_ROLLBACK" else None
                ),
                reviewer_note_ko="독립 reviewer가 source와 대조할 판정",
            )
        )
    return draft.model_copy(
        update={
            "status": SessionStatus.COMPLETED,
            "events": events,
            "task_results": results,
        }
    )


def test_v2_protocol_is_hash_pinned_to_three_project_sources() -> None:
    protocol, pack, projects = _v2_materials()

    assert protocol.project_ids == ["PROJECT-U", "PROJECT-V", "PROJECT-W"]
    assert protocol.product_entry_path == "/projects"
    assert len(protocol.tasks) == 11
    assert {task.category for task in protocol.tasks} == {
        "portfolio",
        "project_situation",
        "risk_trace",
        "decision_linkage",
        "historical_boundary",
    }
    assert set(projects) == set(protocol.project_ids)
    for source in pack.project_sources:
        assert project_sha256(projects[source.project_id]) == source.project_sha256


def test_v2_release_pins_product_and_reviewer_material() -> None:
    protocol, _, _, release, rubric = validate_project_study_bundle(
        ROOT,
        ROOT / "fixtures",
        PROTOCOL_V2,
        BASELINE_V2,
        RELEASE_V2,
        RUBRIC_V2,
    )

    assert release.release_id == "UX-I-PRODUCT-87D49D7"
    assert release.product_revision == "87d49d76290324ea71b44dfccd4bdbd4ff766e4c"
    assert release.environment.browser_family == "chromium"
    assert {item.purpose for item in release.artifact_pins} == {
        "product_ui",
        "product_api",
        "study_material",
    }
    assert [item.task_id for item in rubric.tasks] == [
        item.task_id for item in protocol.tasks
    ]


def test_v2_release_rejects_a_stale_product_surface(tmp_path: Path) -> None:
    payload = yaml.safe_load(RELEASE_V2.read_text(encoding="utf-8"))
    payload["artifact_pins"][0]["sha256"] = "0" * 64
    stale = tmp_path / "stale-release.yaml"
    stale.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="artifact hash is stale"):
        validate_project_study_bundle(
            ROOT,
            ROOT / "fixtures",
            PROTOCOL_V2,
            BASELINE_V2,
            stale,
            RUBRIC_V2,
        )


def test_v2_baseline_rejects_a_stale_project_hash(tmp_path: Path) -> None:
    payload = yaml.safe_load(BASELINE_V2.read_text(encoding="utf-8"))
    payload["project_sources"][1]["project_sha256"] = "0" * 64
    stale = tmp_path / "stale-project-pack.yaml"
    stale.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="project baseline source hash is stale"):
        validate_study_materials(ROOT / "fixtures", PROTOCOL_V2, stale)


def test_v2_rejects_a_task_source_hidden_from_the_baseline(tmp_path: Path) -> None:
    payload = yaml.safe_load(BASELINE_V2.read_text(encoding="utf-8"))
    risk_surface = next(
        item for item in payload["surfaces"] if item["surface_id"] == "BASE-PROJECT-V-RISK"
    )
    risk_surface["source_selections"][0]["source_paths"].remove(
        "/cross_project_sources"
    )
    unfair = tmp_path / "unfair-project-pack.yaml"
    unfair.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="task source is not exposed"):
        validate_study_materials(ROOT / "fixtures", PROTOCOL_V2, unfair)


def test_v2_baseline_and_guides_separate_conditions_without_answers() -> None:
    protocol, pack, projects = _v2_materials()
    rendered = render_baseline_markdown(protocol, pack, projects)
    baseline_guide = render_session_guide(protocol, StudyCondition.BASELINE)
    product_guide = render_session_guide(protocol, StudyCondition.PRODUCT)

    assert "업무 도구형 baseline" in rendered
    assert "PROJECT-V 개발 진행 현황" in rendered
    assert "RISK-V-WRONG-COMMIT" in rendered
    assert "hidden outcome을 포함하지 않습니다" in rendered
    assert "expected_result" not in rendered
    assert "baseline-pack.md" in baseline_guide
    assert "제품 `/projects`" in product_guide
    assert "P09_NO_FUTURE_LEAKAGE" in product_guide
    assert "정답" not in product_guide


def test_v1_case_protocol_remains_valid_after_v2_becomes_default() -> None:
    protocol, _, source = validate_study_materials(
        ROOT / "fixtures", PROTOCOL_V1, BASELINE_V1
    )

    assert isinstance(protocol, UsabilityStudyProtocol)
    assert isinstance(source, ObservableCase)
    assert protocol.study_id == "UX-H-20260719-CASE-VR-001"
    assert source.case_id == "CASE-VR-001"


def test_cli_prepares_v2_baseline_and_product_session_materials(tmp_path: Path) -> None:
    for condition in ("baseline", "product"):
        session_id = f"OPS-F-{condition.upper()}"
        assert main(
            [
                "usability",
                "prepare-session",
                "--condition",
                condition,
                "--participant-kind",
                "proxy",
                "--participant-code",
                f"P-{condition}",
                "--session-id",
                session_id,
                "--output-root",
                str(tmp_path),
            ]
        ) == 0
        session_dir = tmp_path / session_id
        assert (session_dir / "study-guide.md").exists()
        assert (session_dir / "session.yaml").exists()
        assert (session_dir / "baseline-pack.md").exists() is (
            condition == "baseline"
        )

    reviewer_guide = tmp_path / "reviewer-only.md"
    assert main(
        [
            "usability",
            "reviewer-guide",
            "--output",
            str(reviewer_guide),
        ]
    ) == 0
    rendered = reviewer_guide.read_text(encoding="utf-8")
    assert "참가자에게 사전 공개하지 않습니다" in rendered
    assert "PROJECT-V를 먼저 확인할 과제로 선택" in rendered
    assert "Step 21 emulator 충돌" in rendered


def test_v2_dry_run_keeps_human_gate_closed_and_is_between_subjects() -> None:
    protocol, _, _ = _v2_materials()
    empty = summarize_sessions(
        protocol, [], generated_at=datetime(2026, 7, 22, 7, 0, tzinfo=UTC)
    )
    assert empty.human_gate_status == "not_ready"
    assert empty.directional_target_status == "not_evaluable"
    assert empty.interpretation == "no_business_claim"

    duplicate = [
        _completed_session(
            protocol,
            condition=condition,
            participant_code="SAME-PARTICIPANT",
        )
        for condition in (StudyCondition.BASELINE, StudyCondition.PRODUCT)
    ]
    with pytest.raises(ValueError, match="only one study condition"):
        summarize_sessions(
            protocol,
            duplicate,
            generated_at=datetime(2026, 7, 22, 7, 0, tzinfo=UTC),
        )


def test_v2_exclusions_are_frozen_and_visible_in_report() -> None:
    protocol, _, _ = _v2_materials()
    draft = create_session_template(
        protocol,
        session_id="DRAFT-BASELINE",
        condition=StudyCondition.BASELINE,
        participant_code="P-DRAFT",
        participant_kind=ParticipantKind.PROXY,
    )
    excluded = UsabilitySession.model_validate(
        {
            **draft.model_dump(mode="json"),
            "session_id": "EXCLUDED-BASELINE",
            "participant_code": "P-EXCLUDED",
            "status": "excluded",
            "exclusion_reason": "study_environment_failure",
        }
    )
    summary = summarize_sessions(
        protocol,
        [draft, excluded],
        generated_at=datetime(2026, 7, 22, 7, 0, tzinfo=UTC),
    )
    baseline = summary.condition_summaries[0]
    assert baseline.draft_sessions == 1
    assert baseline.excluded_sessions == 1
    assert baseline.exclusion_reasons == {"study_environment_failure": 1}
    report = render_study_report(summary)
    assert "study_environment_failure" in report
    assert "|baseline|study_environment_failure|1|" in report

    invalid = UsabilitySession.model_validate(
        {
            **excluded.model_dump(mode="json"),
            "exclusion_reason": "result_was_inconvenient",
        }
    )
    with pytest.raises(ValueError, match="not frozen in protocol"):
        validate_session(protocol, invalid)


def test_v2_contracts_are_registered_without_replacing_v1() -> None:
    assert (
        CONTRACT_MODELS["usability-project-baseline-pack.v2"]
        is ProjectUsabilityBaselinePack
    )
    assert (
        CONTRACT_MODELS["usability-study-protocol.v2"]
        is ProjectUsabilityStudyProtocol
    )
    assert CONTRACT_MODELS["usability-study-protocol.v1"] is UsabilityStudyProtocol
    assert CONTRACT_MODELS["usability-study-release.v1"] is UsabilityStudyRelease
    assert CONTRACT_MODELS["usability-reviewer-rubric.v1"] is UsabilityReviewerRubric
