from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from soc_ot.agents.chair import (
    deterministic_core_decision,
    simulated_chair_decision,
    validate_decision_policy,
)
from soc_ot.agents.contracts import ProviderReviewResult, RoleReview
from soc_ot.agents.multi_role import (
    AblationResult,
    AgreementGroup,
    ChairProviderResult,
    ChallengerProviderResult,
    ChallengerReview,
    DecisionDossier,
    DissentItem,
    DossierExecution,
    RoleFailure,
)
from soc_ot.agents.providers import ReviewProvider
from soc_ot.agents.runtime import (
    AttemptSink,
    ReviewExecutionError,
    execute_chair_review,
    execute_challenger_review,
    execute_grounded_review,
)
from soc_ot.application.packets import ObservableCasePacket
from soc_ot.domain.models import DecisionType

__all__ = ["simulated_chair_decision", "validate_decision_policy"]

Topology = Literal["B0", "B1", "B2", "B3"]
ReviewCheckpointSink = Callable[[ProviderReviewResult, int], None]
ChallengerCheckpointSink = Callable[[ChallengerProviderResult], None]
ChairCheckpointSink = Callable[[ChairProviderResult], None]
MAX_REVISION_ROUNDS = 1
MAX_REVISED_ROLES = 2


@dataclass(frozen=True)
class AgentRuntimeBudget:
    max_role_agents: int = 5
    max_provider_attempts: int = 12
    max_output_tokens: int = 20_000
    max_case_cost_usd: float = 2.0


def run_ablation(
    packet: ObservableCasePacket,
    provider: ReviewProvider,
    topology: Topology,
    *,
    allowed_decision_types: list[DecisionType],
    budget: AgentRuntimeBudget | None = None,
) -> AblationResult:
    budget = budget or AgentRuntimeBudget()
    if topology == "B0":
        reviews = [_baseline_review(packet)]
        input_tokens = 0
        output_tokens = 0
        estimated_cost = 0.0
        provider_attempts = 0
        challenger = None
        dossier = build_dossier(packet, reviews)
    else:
        execution = run_dossier_round(
            packet,
            provider,
            topology,
            budget=budget,
            allowed_decision_types=allowed_decision_types,
        )
        reviews = execution.dossier.original_reviews
        challenger = execution.dossier.challenger
        dossier = execution.dossier
        input_tokens = execution.input_tokens
        output_tokens = execution.output_tokens
        estimated_cost = execution.estimated_cost_usd
        provider_attempts = execution.provider_attempts
    if topology == "B3":
        if execution.chair_provider_result is None:
            raise RuntimeError("CHAIR_RESULT_MISSING")
        decision = execution.chair_provider_result.decision
    else:
        decision = deterministic_core_decision(packet, dossier, allowed_decision_types)
    return AblationResult(
        topology=topology,
        role_count=0 if topology == "B0" else len(reviews),
        challenger_used=challenger is not None,
        chair_used=topology == "B3",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimated_cost,
        provider_attempts=provider_attempts,
        dossier=dossier,
        decision=decision,
    )


def run_dossier_round(
    packet: ObservableCasePacket,
    provider: ReviewProvider,
    topology: Literal["B1", "B2", "B3"] = "B3",
    *,
    budget: AgentRuntimeBudget | None = None,
    attempt_sink: AttemptSink | None = None,
    initial_role_results: dict[str, ProviderReviewResult] | None = None,
    initial_revision_results: dict[str, ProviderReviewResult] | None = None,
    initial_challenger_result: ChallengerProviderResult | None = None,
    initial_chair_result: ChairProviderResult | None = None,
    review_checkpoint_sink: ReviewCheckpointSink | None = None,
    challenger_checkpoint_sink: ChallengerCheckpointSink | None = None,
    chair_checkpoint_sink: ChairCheckpointSink | None = None,
    prior_provider_attempts: int = 0,
    allowed_decision_types: list[DecisionType] | None = None,
) -> DossierExecution:
    budget = budget or AgentRuntimeBudget()
    role_ids = packet.selected_role_ids[:1] if topology == "B1" else packet.selected_role_ids
    if len(role_ids) > budget.max_role_agents:
        raise ValueError("AGENT_BUDGET_EXCEEDED:ROLE_COUNT")
    provider_results = []
    failures: list[RoleFailure] = []
    input_tokens = 0
    output_tokens = 0
    estimated_cost = 0.0
    provider_attempts = prior_provider_attempts
    initial_role_results = initial_role_results or {}
    initial_revision_results = initial_revision_results or {}
    for role_id in role_ids:
        checkpoint = initial_role_results.get(role_id)
        if checkpoint is not None:
            provider_results.append(checkpoint)
            input_tokens += checkpoint.usage.input_tokens
            output_tokens += checkpoint.usage.output_tokens
            estimated_cost += checkpoint.usage.estimated_cost_usd
            continue
        remaining_attempts = budget.max_provider_attempts - provider_attempts
        if remaining_attempts < 1:
            raise ValueError("AGENT_BUDGET_EXCEEDED:PROVIDER_ATTEMPTS")
        try:
            result = execute_grounded_review(
                packet,
                role_id,
                provider,
                validator=lambda candidate: _validate_review_grounding(
                    packet, [candidate.review]
                ),
                max_provider_attempts=min(3, remaining_attempts),
                attempt_sink=attempt_sink,
            )
            attempts_used = result.usage.provider_attempts
        except ReviewExecutionError as error:
            provider_attempts += error.provider_attempts
            if error.code == "PROVIDER_USAGE_LIMIT":
                raise RuntimeError("PROVIDER_USAGE_LIMIT") from error
            if error.code.startswith("AGENT_BUDGET_EXCEEDED"):
                raise ValueError(error.code) from error
            failures.append(
                RoleFailure(
                    role_id=role_id,
                    error_code=error.code,
                    provider_attempts=error.provider_attempts,
                )
            )
            continue
        except Exception as error:
            provider_attempts += 1
            failures.append(
                RoleFailure(role_id=role_id, error_code=type(error).__name__)
            )
            continue
        provider_attempts += attempts_used
        provider_results.append(result)
        if review_checkpoint_sink is not None:
            review_checkpoint_sink(result, 0)
        input_tokens += result.usage.input_tokens
        output_tokens += result.usage.output_tokens
        estimated_cost += result.usage.estimated_cost_usd
        _enforce_runtime_budget(
            provider_attempts=provider_attempts,
            output_tokens=output_tokens,
            estimated_cost=estimated_cost,
            budget=budget,
        )
    if not provider_results:
        details = ",".join(
            f"{failure.role_id}={failure.error_code}" for failure in failures
        )
        raise RuntimeError(f"ALL_MANDATORY_ROLES_FAILED:{details}")
    reviews = [result.review for result in provider_results]
    challenger_result = initial_challenger_result
    if topology == "B3" and challenger_result is None:
        remaining_attempts = budget.max_provider_attempts - provider_attempts
        if remaining_attempts < 1:
            raise ValueError("AGENT_BUDGET_EXCEEDED:PROVIDER_ATTEMPTS")
        challenger_result = execute_challenger_review(
            packet,
            reviews,
            provider,
            max_provider_attempts=min(3, remaining_attempts),
            attempt_sink=attempt_sink,
        )
        provider_attempts += challenger_result.usage.provider_attempts
        input_tokens += challenger_result.usage.input_tokens
        output_tokens += challenger_result.usage.output_tokens
        estimated_cost += challenger_result.usage.estimated_cost_usd
        _enforce_runtime_budget(
            provider_attempts=provider_attempts,
            output_tokens=output_tokens,
            estimated_cost=estimated_cost,
            budget=budget,
        )
        if challenger_checkpoint_sink is not None:
            challenger_checkpoint_sink(challenger_result)
    elif challenger_result is not None:
        input_tokens += challenger_result.usage.input_tokens
        output_tokens += challenger_result.usage.output_tokens
        estimated_cost += challenger_result.usage.estimated_cost_usd
    challenger = challenger_result.challenger if challenger_result else None
    revision_results: list[ProviderReviewResult] = []
    revision_failures: list[RoleFailure] = []
    if challenger:
        targets = {
            item.target_role_id: item
            for item in challenger.objections[:MAX_REVISED_ROLES]
        }
        for role_id, objection in targets.items():
            checkpoint = initial_revision_results.get(role_id)
            if checkpoint is not None:
                revision_results.append(checkpoint)
                input_tokens += checkpoint.usage.input_tokens
                output_tokens += checkpoint.usage.output_tokens
                estimated_cost += checkpoint.usage.estimated_cost_usd
                continue
            remaining_attempts = budget.max_provider_attempts - provider_attempts
            if remaining_attempts < 1:
                raise ValueError("AGENT_BUDGET_EXCEEDED:PROVIDER_ATTEMPTS")
            try:
                result = execute_grounded_review(
                    packet,
                    role_id,
                    provider,
                    validator=lambda candidate: _validate_review_grounding(
                        packet, [candidate.review]
                    ),
                    max_provider_attempts=min(3, remaining_attempts),
                    attempt_sink=attempt_sink,
                    review_round=MAX_REVISION_ROUNDS,
                    initial_feedback=objection.requested_revision,
                )
            except ReviewExecutionError as error:
                provider_attempts += error.provider_attempts
                if error.code == "PROVIDER_USAGE_LIMIT":
                    raise RuntimeError("PROVIDER_USAGE_LIMIT") from error
                if error.code.startswith("AGENT_BUDGET_EXCEEDED"):
                    raise ValueError(error.code) from error
                revision_failures.append(
                    RoleFailure(
                        role_id=role_id,
                        error_code=error.code,
                        provider_attempts=error.provider_attempts,
                    )
                )
                continue
            provider_attempts += result.usage.provider_attempts
            revision_results.append(result)
            if review_checkpoint_sink is not None:
                review_checkpoint_sink(result, MAX_REVISION_ROUNDS)
            input_tokens += result.usage.input_tokens
            output_tokens += result.usage.output_tokens
            estimated_cost += result.usage.estimated_cost_usd
            _enforce_runtime_budget(
                provider_attempts=provider_attempts,
                output_tokens=output_tokens,
                estimated_cost=estimated_cost,
                budget=budget,
            )
    revised = [result.review for result in revision_results]
    dossier = build_dossier(packet, reviews, challenger, revised)
    chair_result = initial_chair_result
    if topology == "B3" and chair_result is None:
        if allowed_decision_types is None:
            raise ValueError("ALLOWED_DECISION_TYPES_REQUIRED")
        remaining_attempts = budget.max_provider_attempts - provider_attempts
        if remaining_attempts < 1:
            raise ValueError("AGENT_BUDGET_EXCEEDED:PROVIDER_ATTEMPTS")
        chair_result = execute_chair_review(
            packet,
            dossier,
            allowed_decision_types,
            provider,
            max_provider_attempts=min(3, remaining_attempts),
            attempt_sink=attempt_sink,
        )
        provider_attempts += chair_result.usage.provider_attempts
        input_tokens += chair_result.usage.input_tokens
        output_tokens += chair_result.usage.output_tokens
        estimated_cost += chair_result.usage.estimated_cost_usd
        _enforce_runtime_budget(
            provider_attempts=provider_attempts,
            output_tokens=output_tokens,
            estimated_cost=estimated_cost,
            budget=budget,
        )
        if chair_checkpoint_sink is not None:
            chair_checkpoint_sink(chair_result)
    elif chair_result is not None:
        input_tokens += chair_result.usage.input_tokens
        output_tokens += chair_result.usage.output_tokens
        estimated_cost += chair_result.usage.estimated_cost_usd
    return DossierExecution(
        topology=topology,
        role_count=len(reviews),
        challenger_used=challenger is not None,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimated_cost,
        provider_attempts=provider_attempts,
        returned_models=sorted(
            {
                result.returned_model
                for result in provider_results + revision_results
                if result.returned_model
            }
            | (
                {challenger_result.returned_model}
                if challenger_result and challenger_result.returned_model
                else set()
            )
            | (
                {chair_result.returned_model}
                if chair_result and chair_result.returned_model
                else set()
            )
        ),
        accepted_role_results=provider_results,
        accepted_revision_results=revision_results,
        failed_roles=failures,
        failed_revisions=revision_failures,
        challenger_provider_result=challenger_result,
        chair_provider_result=chair_result,
        dossier=dossier,
    )


def _enforce_runtime_budget(
    *,
    provider_attempts: int,
    output_tokens: int,
    estimated_cost: float,
    budget: AgentRuntimeBudget,
) -> None:
    if provider_attempts > budget.max_provider_attempts:
        raise ValueError("AGENT_BUDGET_EXCEEDED:PROVIDER_ATTEMPTS")
    if output_tokens > budget.max_output_tokens:
        raise ValueError("AGENT_BUDGET_EXCEEDED:OUTPUT_TOKENS")
    if estimated_cost > budget.max_case_cost_usd:
        raise ValueError("AGENT_BUDGET_EXCEEDED:COST")


def build_dossier(
    packet: ObservableCasePacket,
    reviews: list[RoleReview],
    challenger: ChallengerReview | None = None,
    revised_reviews: list[RoleReview] | None = None,
) -> DecisionDossier:
    groups: dict[DecisionType, list[str]] = {}
    for review in reviews:
        groups.setdefault(review.recommendation, []).append(review.role_id)
    majority = Counter(review.recommendation for review in reviews).most_common(1)[0][0]
    dissent = [
        DissentItem(
            role_id=review.role_id,
            recommendation=review.recommendation,
            rationale=review.rationale,
        )
        for review in reviews
        if review.recommendation != majority
    ]
    return DecisionDossier(
        case_id=packet.case_id,
        packet_hash=packet.packet_hash,
        original_reviews=reviews,
        challenger=challenger,
        revised_reviews=revised_reviews or [],
        agreement_groups=[
            AgreementGroup(recommendation=recommendation, role_ids=role_ids)
            for recommendation, role_ids in groups.items()
        ],
        dissent=dissent,
        unresolved_uncertainties=packet.uncertainties,
    )


def _baseline_review(packet: ObservableCasePacket) -> RoleReview:
    claim_ids = [packet.claims[0].claim_id] if packet.claims else []
    return RoleReview(
        role_id="non_agent_baseline",
        recommendation=DecisionType.COLLECT_MINIMUM_EVIDENCE,
        rationale="Blocker와 불확실성이 남아 있어 최소 근거 확보를 우선한다.",
        rationale_claim_ids=claim_ids,
        risks=[],
        information_gaps=packet.uncertainties,
        unique_concern="결정론적 baseline은 역할별 고유 concern을 생성하지 않는다.",
        confidence="low",
    )


def _validate_review_grounding(
    packet: ObservableCasePacket, reviews: list[RoleReview]
) -> None:
    valid_claim_ids = {claim.claim_id for claim in packet.claims}
    valid_option_ids = {option.option_id for option in packet.alternatives}
    for review in reviews:
        used_claim_ids = set(review.rationale_claim_ids)
        for risk in review.risks:
            used_claim_ids.update(risk.claim_ids)
        if not used_claim_ids <= valid_claim_ids:
            raise ValueError("UNSUPPORTED_AUTHORITATIVE_CLAIM")
        if review.recommended_option_id and review.recommended_option_id not in valid_option_ids:
            raise ValueError("UNKNOWN_RECOMMENDED_OPTION")
