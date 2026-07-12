import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict

from soc_ot.domain.models import (
    Alternative,
    Claim,
    DecisionType,
    EpistemicStatus,
    Evidence,
    Milestone,
    ObservableCase,
    WorkItem,
)

HIDDEN_FIELD_DENYLIST = frozenset(
    {"hidden_root_causes", "outcome_paths", "expected_result", "acceptable_decision_types"}
)


class EvidenceAvailability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str
    title: str
    available_at_step: int
    eligible_now: bool


class WorkImpact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_work_item_id: str
    downstream_work_item_ids: list[str]
    impacted_track_ids: list[str]
    reaches_decision_deadline: bool


class OptionOperability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    option_id: str
    reversible: bool
    detectability: Literal["observable_now", "observable_later", "unknown"]
    recoverability: Literal["high", "medium", "low"]
    constraint_claim_ids: list[str]


class ObservableCasePacket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "observable-case-packet.v1"
    case_id: str
    fixture_version: int
    current_step: int
    decision_question: str
    deadline_milestone_id: str
    deadline_milestone: Milestone
    allowed_decision_types: list[DecisionType]
    work_items: list[WorkItem]
    blocker_work_item_ids: list[str]
    dependency_edges: list[tuple[str, str]]
    eligible_evidence: list[Evidence]
    evidence_availability: list[EvidenceAvailability]
    claims: list[Claim]
    assumptions: list[Claim]
    unknowns: list[Claim]
    uncertainties: list[str]
    alternatives: list[Alternative]
    option_operability: list[OptionOperability]
    work_impacts: list[WorkImpact]
    selected_role_ids: list[str]
    allowed_source_ids: list[str]
    contract_version: str = "observable-case-packet.v1"
    policy_version: str = "decision-policy.v1"
    hidden_denylist_checked: bool = True
    packet_hash: str


def build_observable_case_packet(case: ObservableCase) -> ObservableCasePacket:
    eligible_evidence = [
        evidence for evidence in case.evidence if evidence.available_at_step <= case.current_step
    ]
    eligible_ids = {evidence.evidence_id for evidence in eligible_evidence}
    claims = [claim for claim in case.claims if set(claim.source_refs) <= eligible_ids]
    deadline = next(
        item
        for item in case.milestones
        if item.milestone_id == case.decision_deadline_milestone_id
    )
    impacts = _build_work_impacts(case, deadline)
    evidence_availability = [
        EvidenceAvailability(
            evidence_id=item.evidence_id,
            title=item.title,
            available_at_step=item.available_at_step,
            eligible_now=item.available_at_step <= case.current_step,
        )
        for item in sorted(
            case.evidence,
            key=lambda item: (item.available_at_step, item.evidence_id),
        )
    ]
    detectability = (
        "observable_now"
        if eligible_evidence
        else "observable_later"
        if case.evidence
        else "unknown"
    )
    payload = {
        "schema_version": "observable-case-packet.v1",
        "case_id": case.case_id,
        "fixture_version": case.fixture_version,
        "current_step": case.current_step,
        "decision_question": case.decision_question,
        "deadline_milestone_id": case.decision_deadline_milestone_id,
        "deadline_milestone": deadline.model_dump(mode="json"),
        "allowed_decision_types": case.allowed_decision_types,
        "work_items": [item.model_dump(mode="json") for item in case.work_items],
        "blocker_work_item_ids": [
            item.work_item_id for item in case.work_items if item.blocker
        ],
        "dependency_edges": [
            (item.work_item_id, dependency_id)
            for item in case.work_items
            for dependency_id in item.dependency_ids
        ],
        "eligible_evidence": [item.model_dump(mode="json") for item in eligible_evidence],
        "evidence_availability": [item.model_dump(mode="json") for item in evidence_availability],
        "claims": [item.model_dump(mode="json") for item in claims],
        "assumptions": [
            item.model_dump(mode="json")
            for item in claims
            if item.epistemic_status is EpistemicStatus.ASSUMPTION
        ],
        "unknowns": [
            item.model_dump(mode="json")
            for item in claims
            if item.epistemic_status is EpistemicStatus.UNKNOWN
        ],
        "uncertainties": case.uncertainties,
        "alternatives": [item.model_dump(mode="json") for item in case.alternatives],
        "option_operability": [
            OptionOperability(
                option_id=item.option_id,
                reversible=item.reversible,
                detectability=detectability,
                recoverability=_recoverability(item),
                constraint_claim_ids=item.claim_ids,
            ).model_dump(mode="json")
            for item in case.alternatives
        ],
        "work_impacts": [item.model_dump(mode="json") for item in impacts],
        "selected_role_ids": case.required_role_ids[:5],
        "allowed_source_ids": sorted(eligible_ids),
        "contract_version": "observable-case-packet.v1",
        "policy_version": "decision-policy.v1",
        "hidden_denylist_checked": True,
    }
    _assert_hidden_free(payload)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return ObservableCasePacket.model_validate(
        {**payload, "packet_hash": hashlib.sha256(canonical.encode()).hexdigest()}
    )


def _build_work_impacts(case: ObservableCase, deadline: Milestone) -> list[WorkImpact]:
    downstream: dict[str, set[str]] = {item.work_item_id: set() for item in case.work_items}
    by_id = {item.work_item_id: item for item in case.work_items}
    for item in case.work_items:
        for dependency_id in item.dependency_ids:
            downstream[dependency_id].add(item.work_item_id)

    def descendants(item_id: str) -> set[str]:
        result: set[str] = set()
        pending = list(downstream[item_id])
        while pending:
            current = pending.pop()
            if current in result:
                continue
            result.add(current)
            pending.extend(downstream[current])
        return result

    impacts = []
    for item in sorted(case.work_items, key=lambda value: value.work_item_id):
        affected = descendants(item.work_item_id)
        impacts.append(
            WorkImpact(
                source_work_item_id=item.work_item_id,
                downstream_work_item_ids=sorted(affected),
                impacted_track_ids=sorted({by_id[item_id].track_id for item_id in affected}),
                reaches_decision_deadline=(
                    item.planned_at_step <= deadline.planned_at_step
                    or any(
                        by_id[item_id].planned_at_step <= deadline.planned_at_step
                        for item_id in affected
                    )
                ),
            )
        )
    return impacts


def _recoverability(alternative: Alternative) -> Literal["high", "medium", "low"]:
    if not alternative.reversible:
        return "low"
    quantity = alternative.switching_cost
    if quantity.value is not None and quantity.value <= 3:
        return "high"
    return "medium"


def _assert_hidden_free(value: object) -> None:
    if isinstance(value, dict):
        forbidden = HIDDEN_FIELD_DENYLIST & value.keys()
        if forbidden:
            raise ValueError(f"HIDDEN_FIELD_IN_PACKET:{sorted(forbidden)}")
        for nested in value.values():
            _assert_hidden_free(nested)
    elif isinstance(value, list | tuple):
        for nested in value:
            _assert_hidden_free(nested)
