from pydantic import BaseModel, ConfigDict

from soc_ot.application.repositories import StoredCase
from soc_ot.domain.models import Claim, Evidence


class TrackSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    track_id: str
    name: str
    status: str
    blocker_count: int


class AlternativeSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    option_id: str
    title: str
    description: str
    reversible: bool


class BlockerSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    work_item_title: str
    track_id: str
    blocker: str
    dependency_ids: list[str]


class EvidenceSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    evidence_id: str
    title: str
    evidence_type: str
    source_ref: str
    available_at_step: int
    eligible_now: bool
    limitations: list[str]


class ClaimSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    claim_id: str
    statement: str
    epistemic_status: str
    confidence_level: str
    source_refs: list[str]


class DecisionWorkspaceProjection(BaseModel):
    model_config = ConfigDict(frozen=True)
    projection_schema_version: str = "decision-workspace.v1"
    case_id: str
    fixture_version: int
    aggregate_version: int
    title_ko: str
    case_status: str
    current_step: int
    decision_question: str
    deadline_milestone_id: str
    deadline_title: str
    deadline_step: int
    tracks: list[TrackSummary]
    alternative_count: int
    evidence_count: int
    uncertainty_count: int
    alternatives: list[AlternativeSummary]
    blockers: list[BlockerSummary]
    eligible_evidence_titles: list[str]
    evidence: list[EvidenceSummary]
    claims: list[ClaimSummary]
    uncertainties: list[str]


def build_workspace_projection(stored: StoredCase) -> DecisionWorkspaceProjection:
    case = stored.case
    deadline = next(
        item for item in case.milestones if item.milestone_id == case.decision_deadline_milestone_id
    )
    blockers_by_track: dict[str, int] = {track.track_id: 0 for track in case.tracks}
    for item in case.work_items:
        if item.blocker:
            blockers_by_track[item.track_id] += 1
    return DecisionWorkspaceProjection(
        case_id=case.case_id,
        fixture_version=case.fixture_version,
        aggregate_version=stored.aggregate_version,
        title_ko=case.title_ko,
        case_status=case.status,
        current_step=case.current_step,
        decision_question=case.decision_question,
        deadline_milestone_id=case.decision_deadline_milestone_id,
        deadline_title=deadline.title,
        deadline_step=deadline.planned_at_step,
        tracks=[
            TrackSummary(
                track_id=track.track_id,
                name=track.name,
                status=track.status,
                blocker_count=blockers_by_track[track.track_id],
            )
            for track in case.tracks
        ],
        alternative_count=len(case.alternatives),
        evidence_count=len(case.evidence),
        uncertainty_count=len(case.uncertainties),
        alternatives=[
            AlternativeSummary(
                option_id=item.option_id,
                title=item.title,
                description=item.description,
                reversible=item.reversible,
            )
            for item in case.alternatives
        ],
        blockers=[
            BlockerSummary(
                work_item_title=item.title,
                track_id=item.track_id,
                blocker=item.blocker,
                dependency_ids=item.dependency_ids,
            )
            for item in case.work_items
            if item.blocker is not None
        ],
        eligible_evidence_titles=[
            item.title for item in case.evidence if item.available_at_step <= case.current_step
        ],
        evidence=[_evidence_summary(item, case.current_step) for item in case.evidence],
        claims=[_claim_summary(item) for item in case.claims],
        uncertainties=case.uncertainties,
    )


def _evidence_summary(item: Evidence, current_step: int) -> EvidenceSummary:
    return EvidenceSummary(
        evidence_id=item.evidence_id,
        title=item.title,
        evidence_type=item.evidence_type,
        source_ref=item.source_ref,
        available_at_step=item.available_at_step,
        eligible_now=item.available_at_step <= current_step,
        limitations=item.limitations,
    )


def _claim_summary(item: Claim) -> ClaimSummary:
    return ClaimSummary(
        claim_id=item.claim_id,
        statement=item.statement,
        epistemic_status=item.epistemic_status,
        confidence_level=item.confidence_level,
        source_refs=item.source_refs,
    )
