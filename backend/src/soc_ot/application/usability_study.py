import hashlib
import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal

import yaml
from pydantic import Field, field_validator, model_validator

from soc_ot.application.project_fixture_contracts import DevelopmentProject
from soc_ot.domain.models import ObservableCase, StrictModel


class StudyCondition(StrEnum):
    BASELINE = "baseline"
    PRODUCT = "product"


class ParticipantKind(StrEnum):
    BUILDER = "builder"
    PROXY = "proxy"
    DOMAIN = "domain"


class SessionStatus(StrEnum):
    DRAFT = "draft"
    COMPLETED = "completed"
    EXCLUDED = "excluded"


class TaskScore(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_REVIEWED = "not_reviewed"


class BoundaryClassification(StrEnum):
    OBSERVED = "observed"
    EXPECTED = "expected"
    UNCONFIRMED = "unconfirmed"
    NOT_APPLICABLE = "not_applicable"


class UsabilityEventType(StrEnum):
    TASK_STARTED = "task_started"
    TASK_ENDED = "task_ended"
    ANSWER_SUBMITTED = "answer_submitted"
    WRONG_PRIMARY_ACTION = "wrong_primary_action"
    DETAIL_OPENED = "detail_opened"
    RECOVERY_USED = "recovery_used"
    REVIEWER_RESPONSE_RECORDED = "reviewer_response_recorded"


class BaselineSurface(StrictModel):
    surface_id: str
    surface_kind: Literal["wiki_review_note", "issue_tracker_export", "evidence_note"]
    title_ko: str = Field(min_length=1)
    source_paths: list[str] = Field(min_length=1)

    @field_validator("source_paths")
    @classmethod
    def validate_source_paths(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("baseline surface has duplicate source paths")
        for value in values:
            parts = PurePosixPath(value).parts
            if not value.startswith("/") or ".." in parts or "\\" in value:
                raise ValueError("baseline source path must be an absolute JSON pointer")
        return values


class UsabilityBaselinePack(StrictModel):
    schema_version: Literal["usability-baseline-pack.v1"] = (
        "usability-baseline-pack.v1"
    )
    study_id: str
    case_id: str
    source_observable_path: str
    observable_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    surfaces: list[BaselineSurface] = Field(min_length=1)
    prohibited_content: list[str] = Field(min_length=1)

    @field_validator("source_observable_path")
    @classmethod
    def require_safe_source_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value:
            raise ValueError("observable source path must be a safe POSIX relative path")
        return value

    @model_validator(mode="after")
    def validate_surfaces(self) -> "UsabilityBaselinePack":
        surface_ids = [item.surface_id for item in self.surfaces]
        if len(surface_ids) != len(set(surface_ids)):
            raise ValueError("baseline pack has duplicate surface ids")
        source_paths = [path for item in self.surfaces for path in item.source_paths]
        if len(source_paths) != len(set(source_paths)):
            raise ValueError("baseline pack exposes a source path more than once")
        return self


class UsabilityTask(StrictModel):
    task_id: str
    category: Literal["canonical", "development_twin"]
    prompt_ko: str = Field(min_length=1)
    answer_source_paths: list[str] = Field(default_factory=list)
    boundary_classification_required: bool = False
    expected_boundary_classification: BoundaryClassification | None = None

    @model_validator(mode="after")
    def validate_boundary_rubric(self) -> "UsabilityTask":
        has_expected = self.expected_boundary_classification is not None
        if self.boundary_classification_required != has_expected:
            raise ValueError("boundary task requires an expected classification")
        if self.expected_boundary_classification is BoundaryClassification.NOT_APPLICABLE:
            raise ValueError("boundary task expected classification cannot be not_applicable")
        return self


class ProjectBaselineSource(StrictModel):
    project_id: str
    source_project_path: str
    project_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("source_project_path")
    @classmethod
    def require_safe_source_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value:
            raise ValueError("project source path must be a safe POSIX relative path")
        return value


class ProjectSourceSelection(StrictModel):
    project_id: str
    source_paths: list[str] = Field(min_length=1)

    @field_validator("source_paths")
    @classmethod
    def validate_source_paths(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("project source selection has duplicate paths")
        for value in values:
            parts = PurePosixPath(value).parts
            if not value.startswith("/") or ".." in parts or "\\" in value:
                raise ValueError("project source path must be an absolute JSON pointer")
        return values


class ProjectBaselineSurface(StrictModel):
    surface_id: str
    surface_kind: Literal[
        "portfolio_review_note",
        "issue_tracker_export",
        "risk_register",
        "evidence_note",
    ]
    title_ko: str = Field(min_length=1)
    source_selections: list[ProjectSourceSelection] = Field(min_length=1)


class ProjectUsabilityBaselinePack(StrictModel):
    schema_version: Literal["usability-project-baseline-pack.v2"] = (
        "usability-project-baseline-pack.v2"
    )
    study_id: str
    project_sources: list[ProjectBaselineSource] = Field(min_length=1)
    surfaces: list[ProjectBaselineSurface] = Field(min_length=1)
    prohibited_content: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_sources_and_surfaces(self) -> "ProjectUsabilityBaselinePack":
        project_ids = [item.project_id for item in self.project_sources]
        if len(project_ids) != len(set(project_ids)):
            raise ValueError("project baseline pack has duplicate project ids")
        source_paths = [item.source_project_path for item in self.project_sources]
        if len(source_paths) != len(set(source_paths)):
            raise ValueError("project baseline pack has duplicate source paths")
        surface_ids = [item.surface_id for item in self.surfaces]
        if len(surface_ids) != len(set(surface_ids)):
            raise ValueError("project baseline pack has duplicate surface ids")
        selections = [
            (selection.project_id, path)
            for surface in self.surfaces
            for selection in surface.source_selections
            for path in selection.source_paths
        ]
        if len(selections) != len(set(selections)):
            raise ValueError("project baseline pack exposes a source path more than once")
        unknown = {
            selection.project_id
            for surface in self.surfaces
            for selection in surface.source_selections
            if selection.project_id not in project_ids
        }
        if unknown:
            raise ValueError("project baseline surface references an unknown project")
        return self


class ProjectUsabilityTask(StrictModel):
    task_id: str
    category: Literal[
        "portfolio",
        "project_situation",
        "risk_trace",
        "decision_linkage",
        "historical_boundary",
    ]
    prompt_ko: str = Field(min_length=1)
    answer_sources: list[ProjectSourceSelection] = Field(default_factory=list)
    boundary_classification_required: bool = False
    expected_boundary_classification: BoundaryClassification | None = None

    @model_validator(mode="after")
    def validate_boundary_rubric(self) -> "ProjectUsabilityTask":
        has_expected = self.expected_boundary_classification is not None
        if self.boundary_classification_required != has_expected:
            raise ValueError("boundary task requires an expected classification")
        if self.expected_boundary_classification is BoundaryClassification.NOT_APPLICABLE:
            raise ValueError("boundary task expected classification cannot be not_applicable")
        return self


class UsabilityTargets(StrictModel):
    minimum_independent_observations_per_condition: int = Field(ge=5)
    question_accuracy_minimum: float = Field(ge=0, le=1)
    boundary_accuracy_minimum: float = Field(ge=0, le=1)
    safeguard_completeness_minimum: float = Field(ge=0, le=1)
    product_median_time_ratio_to_baseline_maximum: float = Field(gt=0, le=1)
    interpretation: Literal["directional_only"] = "directional_only"


class UsabilityStudyProtocol(StrictModel):
    schema_version: Literal["usability-study-protocol.v1"] = (
        "usability-study-protocol.v1"
    )
    study_id: str
    frozen_at: datetime
    case_id: str
    conditions: list[StudyCondition]
    tasks: list[UsabilityTask] = Field(min_length=1)
    targets: UsabilityTargets
    independent_participant_kinds: list[ParticipantKind]
    exclusion_reasons: list[str] = Field(min_length=1)
    result_policy: list[str] = Field(min_length=1)

    @field_validator("frozen_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("protocol frozen_at must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_protocol(self) -> "UsabilityStudyProtocol":
        if set(self.conditions) != {StudyCondition.BASELINE, StudyCondition.PRODUCT}:
            raise ValueError("protocol requires baseline and product conditions")
        if set(self.independent_participant_kinds) != {
            ParticipantKind.PROXY,
            ParticipantKind.DOMAIN,
        }:
            raise ValueError("independent participants must be proxy and domain reviewers")
        task_ids = [item.task_id for item in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("protocol has duplicate task ids")
        return self


class ProjectUsabilityStudyProtocol(StrictModel):
    schema_version: Literal["usability-study-protocol.v2"] = (
        "usability-study-protocol.v2"
    )
    study_id: str
    frozen_at: datetime
    project_ids: list[str] = Field(min_length=1)
    product_entry_path: Literal["/projects"] = "/projects"
    conditions: list[StudyCondition]
    tasks: list[ProjectUsabilityTask] = Field(min_length=1)
    targets: UsabilityTargets
    independent_participant_kinds: list[ParticipantKind]
    exclusion_reasons: list[str] = Field(min_length=1)
    result_policy: list[str] = Field(min_length=1)

    @field_validator("frozen_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("protocol frozen_at must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_protocol(self) -> "ProjectUsabilityStudyProtocol":
        if set(self.conditions) != {StudyCondition.BASELINE, StudyCondition.PRODUCT}:
            raise ValueError("protocol requires baseline and product conditions")
        if set(self.independent_participant_kinds) != {
            ParticipantKind.PROXY,
            ParticipantKind.DOMAIN,
        }:
            raise ValueError("independent participants must be proxy and domain reviewers")
        if len(self.project_ids) != len(set(self.project_ids)):
            raise ValueError("project protocol has duplicate project ids")
        task_ids = [item.task_id for item in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("protocol has duplicate task ids")
        unknown = {
            selection.project_id
            for task in self.tasks
            for selection in task.answer_sources
            if selection.project_id not in self.project_ids
        }
        if unknown:
            raise ValueError("project task references an unknown project")
        return self


class UsabilityEvent(StrictModel):
    event_id: str
    event_type: UsabilityEventType
    task_id: str
    occurred_at: datetime
    detail_ko: str | None = None

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("usability event timestamp must include a timezone")
        return value


class UsabilityTaskResult(StrictModel):
    task_id: str
    answer_ko: str = ""
    score: TaskScore = TaskScore.NOT_REVIEWED
    boundary_classification: BoundaryClassification = (
        BoundaryClassification.NOT_APPLICABLE
    )
    safeguard_completeness: float | None = Field(default=None, ge=0, le=1)
    reviewer_note_ko: str = ""


class UsabilitySession(StrictModel):
    schema_version: Literal["usability-session.v1"] = "usability-session.v1"
    study_id: str
    session_id: str
    condition: StudyCondition
    participant_code: str
    participant_kind: ParticipantKind
    status: SessionStatus = SessionStatus.DRAFT
    exclusion_reason: str | None = None
    events: list[UsabilityEvent] = Field(default_factory=list)
    task_results: list[UsabilityTaskResult]

    @model_validator(mode="after")
    def validate_status(self) -> "UsabilitySession":
        event_ids = [event.event_id for event in self.events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("session has duplicate event ids")
        if self.status is SessionStatus.EXCLUDED and not self.exclusion_reason:
            raise ValueError("excluded session requires exclusion_reason")
        if self.status is not SessionStatus.EXCLUDED and self.exclusion_reason:
            raise ValueError("only excluded sessions may have exclusion_reason")
        return self


class ConditionSummary(StrictModel):
    condition: StudyCondition
    completed_sessions: int
    independent_sessions: int
    builder_sessions: int
    median_elapsed_seconds: float | None
    question_accuracy: float | None
    boundary_accuracy: float | None
    safeguard_completeness: float | None
    wrong_primary_action_count: int
    detail_open_count: int
    recovery_used_count: int


class TargetAssessment(StrictModel):
    question_accuracy_met: bool | None
    boundary_accuracy_met: bool | None
    safeguard_completeness_met: bool | None
    time_ratio_met: bool | None
    product_to_baseline_time_ratio: float | None
    all_targets_met: bool | None


class UsabilityStudySummary(StrictModel):
    schema_version: Literal["usability-study-summary.v1"] = (
        "usability-study-summary.v1"
    )
    study_id: str
    generated_at: datetime
    condition_summaries: list[ConditionSummary]
    independent_requirement_met: bool
    human_gate_status: Literal["not_ready", "ready_for_directional_review"]
    directional_target_status: Literal["not_evaluable", "met", "not_met"]
    target_assessment: TargetAssessment
    interpretation: Literal["no_business_claim", "directional_only"]
    reasons: list[str]


StudyProtocol = UsabilityStudyProtocol | ProjectUsabilityStudyProtocol
StudyBaselinePack = UsabilityBaselinePack | ProjectUsabilityBaselinePack
StudySource = ObservableCase | dict[str, DevelopmentProject]
StudyTask = UsabilityTask | ProjectUsabilityTask


def _study_tasks(protocol: StudyProtocol) -> list[StudyTask]:
    if isinstance(protocol, ProjectUsabilityStudyProtocol):
        return list(protocol.tasks)
    return list(protocol.tasks)


def load_protocol(path: Path) -> StudyProtocol:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") == "usability-study-protocol.v2":
        return ProjectUsabilityStudyProtocol.model_validate(payload)
    return UsabilityStudyProtocol.model_validate(payload)


def load_baseline_pack(path: Path) -> StudyBaselinePack:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") == "usability-project-baseline-pack.v2":
        return ProjectUsabilityBaselinePack.model_validate(payload)
    return UsabilityBaselinePack.model_validate(payload)


def load_session(path: Path) -> UsabilitySession:
    return UsabilitySession.model_validate(
        yaml.safe_load(path.read_text(encoding="utf-8"))
    )


def observable_sha256(case: ObservableCase) -> str:
    return _model_sha256(case)


def project_sha256(project: DevelopmentProject) -> str:
    return _model_sha256(project)


def _model_sha256(model: StrictModel) -> str:
    encoded = json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_study_materials(
    fixtures_root: Path,
    protocol_path: Path,
    baseline_pack_path: Path,
) -> tuple[StudyProtocol, StudyBaselinePack, StudySource]:
    protocol = load_protocol(protocol_path)
    pack = load_baseline_pack(baseline_pack_path)
    if isinstance(protocol, ProjectUsabilityStudyProtocol):
        if not isinstance(pack, ProjectUsabilityBaselinePack):
            raise ValueError("v2 protocol requires a project baseline pack")
        return _validate_project_study_materials(fixtures_root, protocol, pack)
    if not isinstance(pack, UsabilityBaselinePack):
        raise ValueError("v1 protocol requires an observable-case baseline pack")
    return _validate_case_study_materials(fixtures_root, protocol, pack)


def _validate_case_study_materials(
    fixtures_root: Path,
    protocol: UsabilityStudyProtocol,
    pack: UsabilityBaselinePack,
) -> tuple[UsabilityStudyProtocol, UsabilityBaselinePack, ObservableCase]:
    if protocol.study_id != pack.study_id or protocol.case_id != pack.case_id:
        raise ValueError("protocol and baseline pack identity mismatch")

    source_path = (fixtures_root / PurePosixPath(pack.source_observable_path)).resolve()
    root = fixtures_root.resolve()
    if root not in source_path.parents:
        raise ValueError("baseline observable source escapes fixtures root")
    case = ObservableCase.model_validate(
        yaml.safe_load(source_path.read_text(encoding="utf-8"))
    )
    if case.case_id != pack.case_id:
        raise ValueError("baseline pack case id does not match observable source")
    if observable_sha256(case) != pack.observable_sha256:
        raise ValueError("baseline observable hash is stale")

    payload = case.model_dump(mode="json")
    for surface in pack.surfaces:
        for source_pointer in surface.source_paths:
            _resolve_pointer(payload, source_pointer)
    for task in protocol.tasks:
        for source_pointer in task.answer_source_paths:
            _resolve_pointer(payload, source_pointer)

    visible_text = json.dumps(
        [surface.model_dump(mode="json") for surface in pack.surfaces],
        ensure_ascii=False,
    ).lower()
    leaked = [term for term in pack.prohibited_content if term.lower() in visible_text]
    if leaked:
        raise ValueError("baseline pack contains prohibited content: " + ", ".join(leaked))
    return protocol, pack, case


def _validate_project_study_materials(
    fixtures_root: Path,
    protocol: ProjectUsabilityStudyProtocol,
    pack: ProjectUsabilityBaselinePack,
) -> tuple[
    ProjectUsabilityStudyProtocol,
    ProjectUsabilityBaselinePack,
    dict[str, DevelopmentProject],
]:
    if protocol.study_id != pack.study_id:
        raise ValueError("protocol and baseline pack identity mismatch")
    if set(protocol.project_ids) != {item.project_id for item in pack.project_sources}:
        raise ValueError("protocol and baseline pack project ids differ")
    root = fixtures_root.resolve()
    projects: dict[str, DevelopmentProject] = {}
    for source in pack.project_sources:
        source_path = (fixtures_root / PurePosixPath(source.source_project_path)).resolve()
        if root not in source_path.parents:
            raise ValueError("project baseline source escapes fixtures root")
        project = DevelopmentProject.model_validate(
            yaml.safe_load(source_path.read_text(encoding="utf-8"))
        )
        if project.project_id != source.project_id:
            raise ValueError("project baseline id does not match source")
        if project_sha256(project) != source.project_sha256:
            raise ValueError("project baseline source hash is stale")
        projects[project.project_id] = project

    selected_values: list[object] = []
    exposed_sources: set[tuple[str, str]] = set()
    for surface in pack.surfaces:
        for selection in surface.source_selections:
            payload = projects[selection.project_id].model_dump(mode="json")
            for source_pointer in selection.source_paths:
                exposed_sources.add((selection.project_id, source_pointer))
                selected_values.append(_resolve_pointer(payload, source_pointer))
    for task in protocol.tasks:
        for selection in task.answer_sources:
            payload = projects[selection.project_id].model_dump(mode="json")
            for source_pointer in selection.source_paths:
                if (selection.project_id, source_pointer) not in exposed_sources:
                    raise ValueError("project task source is not exposed in baseline")
                _resolve_pointer(payload, source_pointer)

    visible_text = json.dumps(selected_values, ensure_ascii=False).lower()
    leaked = [term for term in pack.prohibited_content if term.lower() in visible_text]
    if leaked:
        raise ValueError("project baseline contains prohibited content: " + ", ".join(leaked))
    return protocol, pack, projects


def render_baseline_markdown(
    protocol: StudyProtocol,
    pack: StudyBaselinePack,
    source: StudySource,
) -> str:
    if isinstance(protocol, ProjectUsabilityStudyProtocol):
        if not isinstance(pack, ProjectUsabilityBaselinePack) or not isinstance(source, dict):
            raise ValueError("v2 baseline rendering requires validated project sources")
        return _render_project_baseline_markdown(protocol, pack, source)
    if not isinstance(pack, UsabilityBaselinePack) or not isinstance(source, ObservableCase):
        raise ValueError("v1 baseline rendering requires a validated observable case")
    return _render_case_baseline_markdown(protocol, pack, source)


def _render_case_baseline_markdown(
    protocol: UsabilityStudyProtocol,
    pack: UsabilityBaselinePack,
    case: ObservableCase,
) -> str:
    payload = case.model_dump(mode="json")
    lines = [
        f"# {case.title_ko} — 업무 도구형 baseline",
        "",
        f"> Study: `{protocol.study_id}` / Case: `{case.case_id}`",
        "> 이 문서는 공개 observable fixture만으로 생성되며 Agent 조언과 "
        "hidden outcome을 포함하지 않습니다.",
    ]
    for surface in pack.surfaces:
        lines.extend(["", f"## {surface.title_ko}", ""])
        for pointer in surface.source_paths:
            value = _resolve_pointer(payload, pointer)
            lines.extend([f"### `{pointer}`", "", "```yaml"])
            lines.append(
                yaml.safe_dump(value, allow_unicode=True, sort_keys=False).rstrip()
            )
            lines.append("```")
    lines.extend(
        [
            "",
            "---",
            "",
            "이 baseline은 독립 시스템이 아니라 human study용 fixture 문서입니다.",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_project_baseline_markdown(
    protocol: ProjectUsabilityStudyProtocol,
    pack: ProjectUsabilityBaselinePack,
    projects: dict[str, DevelopmentProject],
) -> str:
    lines = [
        "# SoC 개발 과제 운영 검토 — 업무 도구형 baseline",
        "",
        f"> Study: `{protocol.study_id}` / Projects: `{' · '.join(protocol.project_ids)}`",
        "> 이 문서는 합성 Project fixture의 선택된 source만 보여주며 Agent 조언, "
        "제품 projection과 hidden outcome을 포함하지 않습니다.",
    ]
    for surface in pack.surfaces:
        lines.extend(["", f"## {surface.title_ko}", ""])
        for selection in surface.source_selections:
            payload = projects[selection.project_id].model_dump(mode="json")
            lines.extend([f"### `{selection.project_id}`", ""])
            for pointer in selection.source_paths:
                value = _resolve_pointer(payload, pointer)
                lines.extend([f"#### `{pointer}`", "", "```yaml"])
                lines.append(
                    yaml.safe_dump(value, allow_unicode=True, sort_keys=False).rstrip()
                )
                lines.append("```")
    lines.extend(
        [
            "",
            "---",
            "",
            "이 baseline은 Jira·Confluence를 모사한 human-study fixture이며 "
            "실제 회사 data가 아닙니다.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_session_guide(protocol: StudyProtocol, condition: StudyCondition) -> str:
    if isinstance(protocol, ProjectUsabilityStudyProtocol):
        start = (
            "`baseline-pack.md`"
            if condition is StudyCondition.BASELINE
            else f"제품 `{protocol.product_entry_path}`"
        )
    else:
        start = (
            "`baseline-pack.md`"
            if condition is StudyCondition.BASELINE
            else f"제품 `/decisions/{protocol.case_id}`"
        )
    lines = [
        f"# 사용성 관측 안내 — {protocol.study_id}",
        "",
        f"> Condition: `{condition}` / 시작 위치: {start}",
        "> 답변, 시간과 reviewer 판정은 session.yaml에 실제 관측한 내용만 기록합니다.",
        "",
        "## 고정 Task",
        "",
    ]
    lines.extend(
        f"{index}. **{task.task_id}** — {task.prompt_ko}"
        for index, task in enumerate(_study_tasks(protocol), start=1)
    )
    lines.extend(
        [
            "",
            "다른 condition의 결과나 reviewer rubric을 참가자에게 미리 보여주지 않습니다.",
        ]
    )
    return "\n".join(lines) + "\n"


def create_session_template(
    protocol: StudyProtocol,
    *,
    session_id: str,
    condition: StudyCondition,
    participant_code: str,
    participant_kind: ParticipantKind,
) -> UsabilitySession:
    return UsabilitySession(
        study_id=protocol.study_id,
        session_id=session_id,
        condition=condition,
        participant_code=participant_code,
        participant_kind=participant_kind,
        task_results=[
            UsabilityTaskResult(task_id=task.task_id)
            for task in _study_tasks(protocol)
        ],
    )


def validate_session(
    protocol: StudyProtocol,
    session: UsabilitySession,
    *,
    require_complete: bool = False,
) -> UsabilitySession:
    if session.study_id != protocol.study_id:
        raise ValueError("session study id does not match protocol")
    if session.condition not in protocol.conditions:
        raise ValueError("session condition is not in protocol")
    task_ids = [task.task_id for task in _study_tasks(protocol)]
    result_ids = [result.task_id for result in session.task_results]
    if result_ids != task_ids:
        raise ValueError("session task order does not match frozen protocol")
    if any(event.task_id not in task_ids for event in session.events):
        raise ValueError("session event references an unknown task")

    complete = session.status is SessionStatus.COMPLETED
    if require_complete and not complete:
        raise ValueError("completed session required")
    if complete:
        _validate_completed_session(protocol, session)
    return session


def write_session_template(session: UsabilitySession, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(session.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def summarize_sessions(
    protocol: StudyProtocol,
    sessions: list[UsabilitySession],
    *,
    generated_at: datetime,
) -> UsabilityStudySummary:
    completed = [
        validate_session(protocol, session, require_complete=True)
        for session in sessions
        if session.status is SessionStatus.COMPLETED
    ]
    identities = [
        (session.condition, session.participant_code) for session in completed
    ]
    if len(identities) != len(set(identities)):
        raise ValueError("participant has duplicate completed sessions in one condition")
    if isinstance(protocol, ProjectUsabilityStudyProtocol):
        participant_codes = [session.participant_code for session in completed]
        if len(participant_codes) != len(set(participant_codes)):
            raise ValueError("v2 participant may complete only one study condition")
    condition_summaries = [
        _condition_summary(protocol, completed, condition)
        for condition in (StudyCondition.BASELINE, StudyCondition.PRODUCT)
    ]
    requirement = all(
        item.independent_sessions
        >= protocol.targets.minimum_independent_observations_per_condition
        for item in condition_summaries
    )
    target_assessment = _assess_targets(
        protocol, condition_summaries, requirement_met=requirement
    )
    reasons: list[str] = []
    if not requirement:
        reasons.append("각 condition의 독립 관측 수가 고정된 최소 표본에 미달한다.")
    if not completed:
        reasons.append("실제 완료된 human session이 없다.")
    return UsabilityStudySummary(
        study_id=protocol.study_id,
        generated_at=generated_at,
        condition_summaries=condition_summaries,
        independent_requirement_met=requirement,
        human_gate_status=(
            "ready_for_directional_review" if requirement else "not_ready"
        ),
        directional_target_status=(
            "not_evaluable"
            if target_assessment.all_targets_met is None
            else "met"
            if target_assessment.all_targets_met
            else "not_met"
        ),
        target_assessment=target_assessment,
        interpretation="directional_only" if requirement else "no_business_claim",
        reasons=reasons,
    )


def render_study_report(summary: UsabilityStudySummary) -> str:
    lines = [
        f"# SoC Operational Twin 사용성 관측 요약 — {summary.study_id}",
        "",
        f"> Human gate: `{summary.human_gate_status}`",
        f"> Directional targets: `{summary.directional_target_status}`",
        f"> Interpretation: `{summary.interpretation}`",
        "",
        "이 보고서는 측정 산출물 요약이며 사람의 최종 승인이나 business value 증명이 아닙니다.",
        "",
        "|Condition|Completed|Independent|Builder|Median seconds|Accuracy|Boundary|"
        "Safeguard|Wrong action|Detail open|Recovery|",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in summary.condition_summaries:
        lines.append(
            "|"
            + "|".join(
                [
                    item.condition,
                    str(item.completed_sessions),
                    str(item.independent_sessions),
                    str(item.builder_sessions),
                    _display_metric(item.median_elapsed_seconds),
                    _display_metric(item.question_accuracy),
                    _display_metric(item.boundary_accuracy),
                    _display_metric(item.safeguard_completeness),
                    str(item.wrong_primary_action_count),
                    str(item.detail_open_count),
                    str(item.recovery_used_count),
                ]
            )
            + "|"
        )
    lines.extend(["", "## 판정 이유", ""])
    if summary.reasons:
        lines.extend(f"- {reason}" for reason in summary.reasons)
    else:
        lines.append("- 고정된 독립 표본 요건을 충족해 directional review가 가능하다.")
    lines.extend(
        [
            "",
            "## 목표 확인",
            "",
            f"- 질문 정확도: `{summary.target_assessment.question_accuracy_met}`",
            f"- 경계 분류 정확도: `{summary.target_assessment.boundary_accuracy_met}`",
            f"- safeguard completeness: `{summary.target_assessment.safeguard_completeness_met}`",
            f"- 시간 비율: `{summary.target_assessment.time_ratio_met}`",
            "- Product/Baseline median time ratio: "
            f"`{_display_metric(summary.target_assessment.product_to_baseline_time_ratio)}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _resolve_pointer(payload: object, pointer: str) -> object:
    current = payload
    for raw_part in pointer.lstrip("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise ValueError(f"baseline source pointer does not exist: {pointer}")
    return current


def _validate_completed_session(
    protocol: StudyProtocol, session: UsabilitySession
) -> None:
    if any(result.score is TaskScore.NOT_REVIEWED for result in session.task_results):
        raise ValueError("completed session has an unreviewed task")
    events_by_task = {
        task.task_id: [event for event in session.events if event.task_id == task.task_id]
        for task in _study_tasks(protocol)
    }
    required = {
        UsabilityEventType.TASK_STARTED,
        UsabilityEventType.TASK_ENDED,
        UsabilityEventType.ANSWER_SUBMITTED,
        UsabilityEventType.REVIEWER_RESPONSE_RECORDED,
    }
    for task, result in zip(_study_tasks(protocol), session.task_results, strict=True):
        events = events_by_task[task.task_id]
        event_types = {event.event_type for event in events}
        missing = required - event_types
        if missing:
            raise ValueError(
                f"completed task {task.task_id} is missing events: "
                + ", ".join(sorted(missing))
            )
        starts = [e.occurred_at for e in events if e.event_type is UsabilityEventType.TASK_STARTED]
        ends = [e.occurred_at for e in events if e.event_type is UsabilityEventType.TASK_ENDED]
        if len(starts) != 1 or len(ends) != 1 or ends[0] < starts[0]:
            raise ValueError(f"completed task {task.task_id} has invalid timing events")
        for event_type in required:
            if sum(event.event_type is event_type for event in events) != 1:
                raise ValueError(
                    f"completed task {task.task_id} requires exactly one {event_type}"
                )
        if any(not starts[0] <= event.occurred_at <= ends[0] for event in events):
            raise ValueError(f"task {task.task_id} has an event outside its timing window")
        if not result.answer_ko.strip() or not result.reviewer_note_ko.strip():
            raise ValueError(f"completed task {task.task_id} requires answer and reviewer note")
        if task.boundary_classification_required and (
            result.boundary_classification is BoundaryClassification.NOT_APPLICABLE
        ):
            raise ValueError(f"task {task.task_id} requires a boundary classification")


def _condition_summary(
    protocol: StudyProtocol,
    sessions: list[UsabilitySession],
    condition: StudyCondition,
) -> ConditionSummary:
    selected = [session for session in sessions if session.condition is condition]
    independent = [
        session
        for session in selected
        if session.participant_kind in protocol.independent_participant_kinds
    ]
    elapsed = [_session_elapsed_seconds(session) for session in independent]
    results = [result for session in independent for result in session.task_results]
    task_by_id = {task.task_id: task for task in _study_tasks(protocol)}
    boundary_results = [
        result
        for result in results
        if task_by_id[result.task_id].expected_boundary_classification is not None
    ]
    safeguard_results = [
        result.safeguard_completeness
        for result in results
        if result.safeguard_completeness is not None
    ]
    return ConditionSummary(
        condition=condition,
        completed_sessions=len(selected),
        independent_sessions=len(independent),
        builder_sessions=sum(
            session.participant_kind is ParticipantKind.BUILDER for session in selected
        ),
        median_elapsed_seconds=_median(elapsed),
        question_accuracy=(
            sum(result.score is TaskScore.PASS for result in results) / len(results)
            if results
            else None
        ),
        boundary_accuracy=(
            sum(
                result.boundary_classification
                is task_by_id[result.task_id].expected_boundary_classification
                for result in boundary_results
            )
            / len(boundary_results)
            if boundary_results
            else None
        ),
        safeguard_completeness=(
            sum(safeguard_results) / len(safeguard_results)
            if safeguard_results
            else None
        ),
        wrong_primary_action_count=_event_count(
            independent, UsabilityEventType.WRONG_PRIMARY_ACTION
        ),
        detail_open_count=_event_count(independent, UsabilityEventType.DETAIL_OPENED),
        recovery_used_count=_event_count(
            independent, UsabilityEventType.RECOVERY_USED
        ),
    )


def _assess_targets(
    protocol: StudyProtocol,
    summaries: list[ConditionSummary],
    *,
    requirement_met: bool,
) -> TargetAssessment:
    baseline, product = summaries
    ratio = (
        product.median_elapsed_seconds / baseline.median_elapsed_seconds
        if baseline.median_elapsed_seconds
        and product.median_elapsed_seconds is not None
        else None
    )
    if not requirement_met:
        return TargetAssessment(
            question_accuracy_met=None,
            boundary_accuracy_met=None,
            safeguard_completeness_met=None,
            time_ratio_met=None,
            product_to_baseline_time_ratio=ratio,
            all_targets_met=None,
        )
    checks = [
        _both_at_least(
            baseline.question_accuracy,
            product.question_accuracy,
            protocol.targets.question_accuracy_minimum,
        ),
        _both_at_least(
            baseline.boundary_accuracy,
            product.boundary_accuracy,
            protocol.targets.boundary_accuracy_minimum,
        ),
        _both_at_least(
            baseline.safeguard_completeness,
            product.safeguard_completeness,
            protocol.targets.safeguard_completeness_minimum,
        ),
        ratio is not None
        and ratio <= protocol.targets.product_median_time_ratio_to_baseline_maximum,
    ]
    return TargetAssessment(
        question_accuracy_met=checks[0],
        boundary_accuracy_met=checks[1],
        safeguard_completeness_met=checks[2],
        time_ratio_met=checks[3],
        product_to_baseline_time_ratio=ratio,
        all_targets_met=all(checks),
    )


def _both_at_least(
    first: float | None, second: float | None, minimum: float
) -> bool:
    return first is not None and second is not None and first >= minimum and second >= minimum


def _event_count(
    sessions: list[UsabilitySession], event_type: UsabilityEventType
) -> int:
    return sum(
        event.event_type is event_type
        for session in sessions
        for event in session.events
    )


def _session_elapsed_seconds(session: UsabilitySession) -> float:
    starts = [
        event.occurred_at
        for event in session.events
        if event.event_type is UsabilityEventType.TASK_STARTED
    ]
    ends = [
        event.occurred_at
        for event in session.events
        if event.event_type is UsabilityEventType.TASK_ENDED
    ]
    return (max(ends) - min(starts)).total_seconds()


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def _display_metric(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.3f}"
