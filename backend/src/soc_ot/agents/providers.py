import json
from typing import Protocol

from openai import OpenAI
from pydantic import ValidationError

from soc_ot.agents.contracts import ProviderReviewResult, ProviderUsage, RiskAssessment, RoleReview
from soc_ot.agents.multi_role import (
    ChairProviderResult,
    ChallengerObjection,
    ChallengerProviderResult,
    ChallengerReview,
    DecisionDossier,
    SimulatedDecision,
)
from soc_ot.agents.prompts import (
    CHAIR_INSTRUCTIONS,
    CHALLENGER_INSTRUCTIONS,
    ROLE_REVIEW_INSTRUCTIONS,
)
from soc_ot.application.packets import ObservableCasePacket
from soc_ot.domain.models import DecisionType


class ReviewProvider(Protocol):
    name: str

    def review(self, packet: ObservableCasePacket, role_id: str) -> ProviderReviewResult: ...


class StructuredReviewError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ReplayProvider:
    """Deterministic provider for CI, local development, and evaluation baselines."""

    name = "replay"
    model = "replay-v1"
    challenger_model = "replay-v1"
    chair_model = "replay-v1"

    def review(self, packet: ObservableCasePacket, role_id: str) -> ProviderReviewResult:
        option = packet.alternatives[0]
        claim_ids = [claim.claim_id for claim in packet.claims]
        risks = [
            RiskAssessment(
                risk_id=f"{role_id}:risk:1",
                statement=packet.uncertainties[0] if packet.uncertainties else "잔여 불확실성",
                severity="high" if packet.blocker_work_item_ids else "medium",
                claim_ids=claim_ids[:1],
                mitigation="작은 가역 실험과 명시적 중단 조건으로 노출을 제한한다.",
            )
        ]
        if not claim_ids or "verification" in role_id:
            decision = DecisionType.COLLECT_MINIMUM_EVIDENCE
        elif "program" in role_id:
            decision = DecisionType.DEFER_UNTIL_TRIGGER
        else:
            decision = (
                DecisionType.RUN_REVERSIBLE_TRIAL
                if option.reversible
                else DecisionType.COLLECT_MINIMUM_EVIDENCE
            )
        review = RoleReview(
            role_id=role_id,
            recommendation=decision,
            recommended_option_id=(
                option.option_id
                if decision
                in {DecisionType.RUN_REVERSIBLE_TRIAL, DecisionType.APPROVE_WITH_GUARDRAILS}
                else None
            ),
            rationale=(
                "현재 근거만으로 불확실성을 제거할 수 없으므로 "
                "가역성과 복구 가능성을 우선한다."
            ),
            rationale_claim_ids=claim_ids[:2],
            risks=risks,
            information_gaps=list(packet.uncertainties),
            unique_concern=_role_concern(role_id),
            confidence="medium",
        )
        return ProviderReviewResult(review=review, returned_model="replay-v1")

    def review_with_feedback(
        self, packet: ObservableCasePacket, role_id: str, feedback: str
    ) -> ProviderReviewResult:
        result = self.review(packet, role_id)
        return result.model_copy(
            update={
                "review": result.review.model_copy(
                    update={
                        "rationale": result.review.rationale
                        + " Challenger 요청에 따라 중단 조건과 재검토 시점을 명시한다."
                    }
                )
            }
        )

    def challenge(
        self, packet: ObservableCasePacket, reviews: list[RoleReview]
    ) -> ChallengerProviderResult:
        objections = [
            ChallengerObjection(
                objection_id=f"OBJ-{index + 1}",
                target_role_id=review.role_id,
                statement="이 권고가 실패할 때 조기 중단 조건이 충분히 구체적인가?",
                claim_ids=review.rationale_claim_ids[:1],
                requested_revision="중단 조건과 다음 검증 step을 명시한다.",
            )
            for index, review in enumerate(reviews)
        ]
        return ChallengerProviderResult(
            challenger=ChallengerReview(objections=objections),
            returned_model="replay-v1",
        )

    def challenge_with_feedback(
        self,
        packet: ObservableCasePacket,
        reviews: list[RoleReview],
        feedback: str,
    ) -> ChallengerProviderResult:
        return self.challenge(packet, reviews)

    def decide(
        self,
        packet: ObservableCasePacket,
        dossier: DecisionDossier,
        allowed_decision_types: list[DecisionType],
    ) -> ChairProviderResult:
        from soc_ot.agents.chair import simulated_chair_decision

        return ChairProviderResult(
            decision=simulated_chair_decision(
                packet, dossier, allowed_decision_types
            ),
            returned_model=self.chair_model,
        )

    def decide_with_feedback(
        self,
        packet: ObservableCasePacket,
        dossier: DecisionDossier,
        allowed_decision_types: list[DecisionType],
        feedback: str,
    ) -> ChairProviderResult:
        return self.decide(packet, dossier, allowed_decision_types)


class OpenAIResponsesProvider:
    """Live provider using Responses API native Pydantic Structured Outputs."""

    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        challenger_model: str | None = None,
        chair_model: str | None = None,
        timeout_seconds: float = 120.0,
        input_cost_per_million_usd: float = 0.0,
        output_cost_per_million_usd: float = 0.0,
    ) -> None:
        self.client = OpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)
        self.model = model
        self.challenger_model = challenger_model or model
        self.chair_model = chair_model or model
        self.input_cost_per_million_usd = input_cost_per_million_usd
        self.output_cost_per_million_usd = output_cost_per_million_usd

    def review(self, packet: ObservableCasePacket, role_id: str) -> ProviderReviewResult:
        return self._review(packet, role_id, None)

    def review_with_feedback(
        self, packet: ObservableCasePacket, role_id: str, feedback: str
    ) -> ProviderReviewResult:
        return self._review(packet, role_id, feedback)

    def _review(
        self, packet: ObservableCasePacket, role_id: str, feedback: str | None
    ) -> ProviderReviewResult:
        instructions = ROLE_REVIEW_INSTRUCTIONS
        if feedback:
            instructions += f"\nValidator feedback for this clean retry: {feedback}"
        try:
            response = self.client.responses.parse(
                model=self.model,
                instructions=instructions,
                input=json.dumps(packet.model_dump(mode="json"), ensure_ascii=False),
                text_format=RoleReview,
                max_output_tokens=1500,
                store=False,
            )
        except (ValidationError, ValueError) as error:
            raise StructuredReviewError("OPENAI_STRUCTURED_OUTPUT_INVALID") from error
        parsed = response.output_parsed
        if parsed is None:
            raise StructuredReviewError("OPENAI_STRUCTURED_OUTPUT_MISSING")
        usage = response.usage
        input_tokens = usage.input_tokens if usage else 0
        output_tokens = usage.output_tokens if usage else 0
        estimated_cost = (
            input_tokens * self.input_cost_per_million_usd
            + output_tokens * self.output_cost_per_million_usd
        ) / 1_000_000
        return ProviderReviewResult(
            review=parsed,
            provider_request_id=response.id,
            returned_model=response.model,
            usage=ProviderUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=estimated_cost,
            ),
        )

    def challenge(
        self, packet: ObservableCasePacket, reviews: list[RoleReview]
    ) -> ChallengerProviderResult:
        return self._challenge(packet, reviews, None)

    def challenge_with_feedback(
        self,
        packet: ObservableCasePacket,
        reviews: list[RoleReview],
        feedback: str,
    ) -> ChallengerProviderResult:
        return self._challenge(packet, reviews, feedback)

    def _challenge(
        self,
        packet: ObservableCasePacket,
        reviews: list[RoleReview],
        feedback: str | None,
    ) -> ChallengerProviderResult:
        instructions = CHALLENGER_INSTRUCTIONS
        if feedback:
            instructions += f"\nValidator feedback for this clean retry: {feedback}"
        input_payload = {
            "observable_case_packet": packet.model_dump(mode="json"),
            "independent_role_reviews": [item.model_dump(mode="json") for item in reviews],
        }
        try:
            response = self.client.responses.parse(
                model=self.challenger_model,
                instructions=instructions,
                input=json.dumps(input_payload, ensure_ascii=False),
                text_format=ChallengerReview,
                max_output_tokens=2000,
                store=False,
            )
        except (ValidationError, ValueError) as error:
            raise StructuredReviewError("OPENAI_CHALLENGER_OUTPUT_INVALID") from error
        parsed = response.output_parsed
        if parsed is None:
            raise StructuredReviewError("OPENAI_CHALLENGER_OUTPUT_MISSING")
        usage = response.usage
        input_tokens = usage.input_tokens if usage else 0
        output_tokens = usage.output_tokens if usage else 0
        estimated_cost = (
            input_tokens * self.input_cost_per_million_usd
            + output_tokens * self.output_cost_per_million_usd
        ) / 1_000_000
        return ChallengerProviderResult(
            challenger=parsed,
            provider_request_id=response.id,
            returned_model=response.model,
            usage=ProviderUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=estimated_cost,
            ),
        )

    def decide(
        self,
        packet: ObservableCasePacket,
        dossier: DecisionDossier,
        allowed_decision_types: list[DecisionType],
    ) -> ChairProviderResult:
        return self._decide(packet, dossier, allowed_decision_types, None)

    def decide_with_feedback(
        self,
        packet: ObservableCasePacket,
        dossier: DecisionDossier,
        allowed_decision_types: list[DecisionType],
        feedback: str,
    ) -> ChairProviderResult:
        return self._decide(packet, dossier, allowed_decision_types, feedback)

    def _decide(
        self,
        packet: ObservableCasePacket,
        dossier: DecisionDossier,
        allowed_decision_types: list[DecisionType],
        feedback: str | None,
    ) -> ChairProviderResult:
        instructions = CHAIR_INSTRUCTIONS
        if feedback:
            instructions += f"\nValidator feedback for this clean retry: {feedback}"
        input_payload = {
            "observable_case_packet": packet.model_dump(mode="json"),
            "decision_dossier": dossier.model_dump(mode="json"),
            "allowed_decision_types": [item.value for item in allowed_decision_types],
        }
        try:
            response = self.client.responses.parse(
                model=self.chair_model,
                instructions=instructions,
                input=json.dumps(input_payload, ensure_ascii=False),
                text_format=SimulatedDecision,
                max_output_tokens=3000,
                store=False,
            )
        except (ValidationError, ValueError) as error:
            raise StructuredReviewError("OPENAI_CHAIR_OUTPUT_INVALID") from error
        parsed = response.output_parsed
        if parsed is None:
            raise StructuredReviewError("OPENAI_CHAIR_OUTPUT_MISSING")
        usage = response.usage
        input_tokens = usage.input_tokens if usage else 0
        output_tokens = usage.output_tokens if usage else 0
        estimated_cost = (
            input_tokens * self.input_cost_per_million_usd
            + output_tokens * self.output_cost_per_million_usd
        ) / 1_000_000
        return ChairProviderResult(
            decision=parsed,
            provider_request_id=response.id,
            returned_model=response.model,
            usage=ProviderUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=estimated_cost,
            ),
        )


def _role_concern(role_id: str) -> str:
    if "architecture" in role_id:
        return "option이 downstream HW interface와 freeze 일정에 미치는 영향"
    if "verification" in role_id:
        return "현재 step에서 실측 근거가 없을 때 필요한 최소 검증"
    if "program" in role_id:
        return "일정 이득과 rollback 비용 사이의 비대칭 위험"
    if "sw" in role_id:
        return "feature flag가 실제 복구 경로로 동작하는지 여부"
    return f"{role_id} 관점의 고유 제약"
