from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from soc_ot.application.contracts import CONTRACT_MODELS
from soc_ot.application.usability_study import (
    BoundaryClassification,
    ParticipantKind,
    SessionStatus,
    StudyCondition,
    TaskScore,
    UsabilityBaselinePack,
    UsabilityEvent,
    UsabilityEventType,
    UsabilitySession,
    UsabilityStudyProtocol,
    UsabilityStudySummary,
    UsabilityTaskResult,
    create_session_template,
    observable_sha256,
    render_baseline_markdown,
    render_study_report,
    summarize_sessions,
    validate_session,
    validate_study_materials,
)
from soc_ot.cli.main import main

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "fixtures/usability/UX-H-20260719.protocol.yaml"
BASELINE = ROOT / "fixtures/usability/CASE-VR-001.baseline-pack.v1.yaml"


def _materials() -> tuple[UsabilityStudyProtocol, UsabilityBaselinePack]:
    protocol, pack, _ = validate_study_materials(ROOT / "fixtures", PROTOCOL, BASELINE)
    return protocol, pack


def _completed_session(
    protocol: UsabilityStudyProtocol,
    *,
    condition: StudyCondition,
    participant_kind: ParticipantKind,
    participant_code: str,
) -> UsabilitySession:
    draft = create_session_template(
        protocol,
        session_id=f"SESSION-{condition}-{participant_code}",
        condition=condition,
        participant_code=participant_code,
        participant_kind=participant_kind,
    )
    base = datetime(2026, 7, 19, 3, 0, tzinfo=UTC)
    events: list[UsabilityEvent] = []
    results: list[UsabilityTaskResult] = []
    for index, task in enumerate(protocol.tasks):
        started = base + timedelta(minutes=index)
        for offset, event_type in enumerate(
            (
                UsabilityEventType.TASK_STARTED,
                UsabilityEventType.ANSWER_SUBMITTED,
                UsabilityEventType.REVIEWER_RESPONSE_RECORDED,
                UsabilityEventType.TASK_ENDED,
            )
        ):
            events.append(
                UsabilityEvent(
                    event_id=f"{participant_code}-{task.task_id}-{event_type}",
                    event_type=event_type,
                    task_id=task.task_id,
                    occurred_at=started + timedelta(seconds=offset * 10),
                    detail_ko="fixture human-study event",
                )
            )
        classification = BoundaryClassification.NOT_APPLICABLE
        if task.expected_boundary_classification is not None:
            classification = task.expected_boundary_classification
        results.append(
            UsabilityTaskResult(
                task_id=task.task_id,
                answer_ko="사람이 실제 session에서 작성한 답변",
                score=TaskScore.PASS,
                boundary_classification=classification,
                safeguard_completeness=(
                    1.0 if task.task_id == "Q06_GUARDRAIL" else None
                ),
                reviewer_note_ko="독립 reviewer가 rubric으로 확인",
            )
        )
    return draft.model_copy(
        update={
            "status": SessionStatus.COMPLETED,
            "events": events,
            "task_results": results,
        }
    )


def test_baseline_pack_is_hash_pinned_to_the_observable_fixture() -> None:
    protocol, pack, case = validate_study_materials(
        ROOT / "fixtures", PROTOCOL, BASELINE
    )

    assert protocol.case_id == case.case_id == pack.case_id == "CASE-VR-001"
    assert pack.observable_sha256 == observable_sha256(case)
    assert len(pack.surfaces) == 3
    assert {item.surface_kind for item in pack.surfaces} == {
        "wiki_review_note",
        "issue_tracker_export",
        "evidence_note",
    }


def test_baseline_pack_rejects_a_stale_observable_hash(tmp_path: Path) -> None:
    payload = yaml.safe_load(BASELINE.read_text(encoding="utf-8"))
    payload["observable_sha256"] = "0" * 64
    stale = tmp_path / "stale.yaml"
    stale.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="baseline observable hash is stale"):
        validate_study_materials(ROOT / "fixtures", PROTOCOL, stale)


def test_protocol_freezes_tasks_targets_and_builder_exclusion() -> None:
    protocol, _ = _materials()

    assert len(protocol.tasks) == 13
    assert sum(task.category == "canonical" for task in protocol.tasks) == 8
    assert sum(task.category == "development_twin" for task in protocol.tasks) == 5
    assert protocol.targets.minimum_independent_observations_per_condition == 5
    assert protocol.targets.product_median_time_ratio_to_baseline_maximum == 0.8
    assert ParticipantKind.BUILDER not in protocol.independent_participant_kinds
    assert protocol.targets.interpretation == "directional_only"


def test_rendered_baseline_contains_only_selected_observable_sections() -> None:
    protocol, pack, case = validate_study_materials(
        ROOT / "fixtures", PROTOCOL, BASELINE
    )
    rendered = render_baseline_markdown(protocol, pack, case)

    assert "업무 도구형 baseline" in rendered
    assert "Jira형 fixture" in rendered
    assert "측정이 완성되기 전에" in rendered
    assert "hidden outcome을 포함하지 않습니다" in rendered
    assert "selected_option_id" not in rendered
    assert "expected_result" not in rendered


def test_draft_session_preserves_frozen_task_order_without_fake_results() -> None:
    protocol, _ = _materials()
    session = create_session_template(
        protocol,
        session_id="DRAFT-001",
        condition=StudyCondition.BASELINE,
        participant_code="P001",
        participant_kind=ParticipantKind.PROXY,
    )

    assert session.status is SessionStatus.DRAFT
    assert session.events == []
    assert [item.task_id for item in session.task_results] == [
        item.task_id for item in protocol.tasks
    ]
    assert all(item.score is TaskScore.NOT_REVIEWED for item in session.task_results)
    validate_session(protocol, session)
    with pytest.raises(ValueError, match="completed session required"):
        validate_session(protocol, session, require_complete=True)


def test_completed_session_requires_full_measurement_and_reviewer_events() -> None:
    protocol, _ = _materials()
    session = _completed_session(
        protocol,
        condition=StudyCondition.BASELINE,
        participant_kind=ParticipantKind.PROXY,
        participant_code="P001",
    )
    validate_session(protocol, session, require_complete=True)

    incomplete = session.model_copy(update={"events": session.events[:-2]})
    with pytest.raises(ValueError, match="missing events"):
        validate_session(protocol, incomplete, require_complete=True)


def test_builder_sessions_never_satisfy_the_independent_human_gate() -> None:
    protocol, _ = _materials()
    sessions = [
        _completed_session(
            protocol,
            condition=condition,
            participant_kind=ParticipantKind.BUILDER,
            participant_code=f"BUILDER-{index}",
        )
        for index, condition in enumerate(
            [StudyCondition.BASELINE, StudyCondition.PRODUCT], start=1
        )
    ]
    summary = summarize_sessions(
        protocol,
        sessions,
        generated_at=datetime(2026, 7, 19, 4, 0, tzinfo=UTC),
    )

    assert summary.human_gate_status == "not_ready"
    assert summary.directional_target_status == "not_evaluable"
    assert summary.target_assessment.all_targets_met is None
    assert summary.interpretation == "no_business_claim"
    assert all(item.independent_sessions == 0 for item in summary.condition_summaries)


def test_duplicate_participant_cannot_inflate_one_condition_sample() -> None:
    protocol, _ = _materials()
    session = _completed_session(
        protocol,
        condition=StudyCondition.BASELINE,
        participant_kind=ParticipantKind.PROXY,
        participant_code="P-DUPLICATE",
    )

    with pytest.raises(ValueError, match="duplicate completed sessions"):
        summarize_sessions(
            protocol,
            [session, session.model_copy(update={"session_id": "SECOND"})],
            generated_at=datetime(2026, 7, 19, 4, 0, tzinfo=UTC),
        )


def test_minimum_independent_sample_only_enables_directional_review() -> None:
    protocol, _ = _materials()
    sessions = [
        _completed_session(
            protocol,
            condition=condition,
            participant_kind=ParticipantKind.PROXY,
            participant_code=f"{condition}-{index}",
        )
        for condition in (StudyCondition.BASELINE, StudyCondition.PRODUCT)
        for index in range(5)
    ]
    summary = summarize_sessions(
        protocol,
        sessions,
        generated_at=datetime(2026, 7, 19, 4, 0, tzinfo=UTC),
    )

    assert summary.independent_requirement_met is True
    assert summary.human_gate_status == "ready_for_directional_review"
    assert summary.interpretation == "directional_only"
    assert summary.directional_target_status == "not_met"
    assert summary.target_assessment.question_accuracy_met is True
    assert summary.target_assessment.time_ratio_met is False
    assert all(item.question_accuracy == 1.0 for item in summary.condition_summaries)
    report = render_study_report(summary)
    assert "ready_for_directional_review" in report
    assert "business value 증명이 아닙니다" in report


def test_usability_contracts_are_generated_and_cli_prepares_draft(tmp_path: Path) -> None:
    assert CONTRACT_MODELS["usability-baseline-pack.v1"] is UsabilityBaselinePack
    assert CONTRACT_MODELS["usability-study-protocol.v1"] is UsabilityStudyProtocol
    assert CONTRACT_MODELS["usability-session.v1"] is UsabilitySession
    assert CONTRACT_MODELS["usability-study-summary.v1"] is UsabilityStudySummary

    assert (
        main(
            [
                "usability",
                "prepare-session",
                "--condition",
                "baseline",
                "--participant-kind",
                "proxy",
                "--participant-code",
                "P-CLI-001",
                "--session-id",
                "CLI-SESSION",
                "--output-root",
                str(tmp_path),
            ]
        )
        == 0
    )
    session_dir = tmp_path / "CLI-SESSION"
    session = UsabilitySession.model_validate(
        yaml.safe_load((session_dir / "session.yaml").read_text(encoding="utf-8"))
    )
    assert session.status is SessionStatus.DRAFT
    assert (session_dir / "baseline-pack.md").exists()
