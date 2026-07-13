import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from openai import APIConnectionError, InternalServerError, RateLimitError

from soc_ot.agents.chair import validate_decision_policy
from soc_ot.agents.contracts import (
    ProviderAttemptMetadata,
    ProviderReviewResult,
    RoleReview,
)
from soc_ot.agents.multi_role import (
    ChairProviderResult,
    ChallengerProviderResult,
    ChallengerReview,
    DecisionDossier,
)
from soc_ot.agents.providers import (
    ProviderUsageLimitError,
    ReviewProvider,
    StructuredReviewError,
)
from soc_ot.application.packets import ObservableCasePacket
from soc_ot.domain.models import DecisionType

AttemptSink = Callable[[ProviderAttemptMetadata], None]
ResultValidator = Callable[[ProviderReviewResult], None]


class ReviewExecutionError(RuntimeError):
    def __init__(self, code: str, provider_attempts: int) -> None:
        super().__init__(code)
        self.code = code
        self.provider_attempts = provider_attempts


class ProviderCallTimeout(TimeoutError):
    pass


def execute_chair_review(
    packet: ObservableCasePacket,
    dossier: DecisionDossier,
    allowed_decision_types: list[DecisionType],
    provider: ReviewProvider,
    *,
    max_provider_attempts: int,
    attempt_sink: AttemptSink | None = None,
    timeout_seconds: float = 180.0,
) -> ChairProviderResult:
    decide = getattr(provider, "decide", None)
    if not callable(decide):
        raise ReviewExecutionError("CHAIR_PROVIDER_UNSUPPORTED", 0)
    attempts = 0
    feedback: str | None = None
    retry_reason: str | None = None
    transport_retries = 0
    schema_retries = 0
    policy_retries = 0
    while attempts < max_provider_attempts:
        attempts += 1
        attempt_id = str(uuid4())
        started_at = datetime.now(UTC)
        started = time.perf_counter()
        _emit_chair_attempt(
            attempt_sink,
            attempt_id=attempt_id,
            provider=provider,
            started_at=started_at,
            started=started,
            retry_reason=retry_reason,
            validation_result="started",
            final_status="running",
            completed=False,
        )
        try:
            result = _chair_with_timeout(
                provider,
                packet,
                dossier,
                allowed_decision_types,
                feedback,
                timeout_seconds,
            )
        except ProviderUsageLimitError as error:
            _emit_chair_attempt(
                attempt_sink,
                attempt_id=attempt_id,
                provider=provider,
                started_at=started_at,
                started=started,
                retry_reason=retry_reason,
                validation_result="PROVIDER_USAGE_LIMIT",
                final_status="failed",
            )
            raise ReviewExecutionError("PROVIDER_USAGE_LIMIT", attempts) from error
        except (ConnectionError, APIConnectionError, RateLimitError, InternalServerError) as error:
            retry = transport_retries < 1 and attempts < max_provider_attempts
            _emit_chair_attempt(
                attempt_sink,
                attempt_id=attempt_id,
                provider=provider,
                started_at=started_at,
                started=started,
                retry_reason=retry_reason,
                validation_result=type(error).__name__,
                final_status="retryable_failed" if retry else "failed",
            )
            if not retry:
                raise ReviewExecutionError("TRANSPORT_RETRY_EXHAUSTED", attempts) from error
            transport_retries += 1
            retry_reason = "transport_error"
            continue
        except (StructuredReviewError, ProviderCallTimeout) as error:
            is_timeout = isinstance(error, ProviderCallTimeout)
            retry = not is_timeout and schema_retries < 1 and attempts < max_provider_attempts
            code = (
                "CHAIR_TIMEOUT"
                if is_timeout
                else cast(StructuredReviewError, error).code
            )
            _emit_chair_attempt(
                attempt_sink,
                attempt_id=attempt_id,
                provider=provider,
                started_at=started_at,
                started=started,
                retry_reason=retry_reason,
                validation_result=code,
                final_status="retryable_failed" if retry else "failed",
            )
            if not retry:
                raise ReviewExecutionError(code, attempts) from error
            schema_retries += 1
            retry_reason = "schema_invalid"
            feedback = "Return a valid SimulatedDecision matching the schema exactly."
            continue
        try:
            _validate_chair(
                packet, dossier, allowed_decision_types, result
            )
        except ValueError as error:
            retry = policy_retries < 1 and attempts < max_provider_attempts
            _emit_chair_attempt(
                attempt_sink,
                attempt_id=attempt_id,
                provider=provider,
                started_at=started_at,
                started=started,
                retry_reason=retry_reason,
                validation_result=str(error),
                final_status="retryable_failed" if retry else "failed",
                result=result,
            )
            if not retry:
                raise ReviewExecutionError("CHAIR_POLICY_RETRY_EXHAUSTED", attempts) from error
            policy_retries += 1
            retry_reason = "policy_violation"
            feedback = f"Correct this validator failure: {error}"
            continue
        if result.usage.output_tokens > 3_000:
            _emit_chair_attempt(
                attempt_sink,
                attempt_id=attempt_id,
                provider=provider,
                started_at=started_at,
                started=started,
                retry_reason=retry_reason,
                validation_result="AGENT_BUDGET_EXCEEDED:CHAIR_OUTPUT_TOKENS",
                final_status="failed",
                result=result,
            )
            raise ReviewExecutionError(
                "AGENT_BUDGET_EXCEEDED:CHAIR_OUTPUT_TOKENS", attempts
            )
        _emit_chair_attempt(
            attempt_sink,
            attempt_id=attempt_id,
            provider=provider,
            started_at=started_at,
            started=started,
            retry_reason=retry_reason,
            validation_result="accepted",
            final_status="accepted",
            result=result,
        )
        return result.model_copy(
            update={
                "usage": result.usage.model_copy(
                    update={"provider_attempts": attempts}
                )
            }
        )
    raise ReviewExecutionError("PROVIDER_ATTEMPT_BUDGET_EXHAUSTED", attempts)


def execute_challenger_review(
    packet: ObservableCasePacket,
    reviews: list[RoleReview],
    provider: ReviewProvider,
    *,
    max_provider_attempts: int,
    attempt_sink: AttemptSink | None = None,
    timeout_seconds: float = 120.0,
) -> ChallengerProviderResult:
    challenge = getattr(provider, "challenge", None)
    if not callable(challenge):
        raise ReviewExecutionError("CHALLENGER_PROVIDER_UNSUPPORTED", 0)
    attempts = 0
    feedback: str | None = None
    retry_reason: str | None = None
    transport_retries = 0
    schema_retries = 0
    policy_retries = 0
    while attempts < max_provider_attempts:
        attempts += 1
        attempt_id = str(uuid4())
        started_at = datetime.now(UTC)
        started = time.perf_counter()
        _emit_challenger_attempt(
            attempt_sink,
            attempt_id=attempt_id,
            provider=provider,
            started_at=started_at,
            started=started,
            retry_reason=retry_reason,
            validation_result="started",
            final_status="running",
            completed=False,
        )
        try:
            result = _challenge_with_timeout(
                provider, packet, reviews, feedback, timeout_seconds
            )
        except ProviderUsageLimitError as error:
            _emit_challenger_attempt(
                attempt_sink,
                attempt_id=attempt_id,
                provider=provider,
                started_at=started_at,
                started=started,
                retry_reason=retry_reason,
                validation_result="PROVIDER_USAGE_LIMIT",
                final_status="failed",
            )
            raise ReviewExecutionError("PROVIDER_USAGE_LIMIT", attempts) from error
        except (ConnectionError, APIConnectionError, RateLimitError, InternalServerError) as error:
            retry = transport_retries < 1 and attempts < max_provider_attempts
            _emit_challenger_attempt(
                attempt_sink,
                attempt_id=attempt_id,
                provider=provider,
                started_at=started_at,
                started=started,
                retry_reason=retry_reason,
                validation_result=type(error).__name__,
                final_status="retryable_failed" if retry else "failed",
            )
            if not retry:
                raise ReviewExecutionError("TRANSPORT_RETRY_EXHAUSTED", attempts) from error
            transport_retries += 1
            retry_reason = "transport_error"
            continue
        except (StructuredReviewError, ProviderCallTimeout) as error:
            is_timeout = isinstance(error, ProviderCallTimeout)
            retry = not is_timeout and schema_retries < 1 and attempts < max_provider_attempts
            code = (
                "CHALLENGER_TIMEOUT"
                if isinstance(error, ProviderCallTimeout)
                else error.code
            )
            _emit_challenger_attempt(
                attempt_sink,
                attempt_id=attempt_id,
                provider=provider,
                started_at=started_at,
                started=started,
                retry_reason=retry_reason,
                validation_result=code,
                final_status="retryable_failed" if retry else "failed",
            )
            if not retry:
                raise ReviewExecutionError(code, attempts) from error
            schema_retries += 1
            retry_reason = "schema_invalid"
            feedback = "Return a valid ChallengerReview matching the schema exactly."
            continue
        try:
            _validate_challenger(packet, reviews, result.challenger)
        except ValueError as error:
            retry = policy_retries < 1 and attempts < max_provider_attempts
            _emit_challenger_attempt(
                attempt_sink,
                attempt_id=attempt_id,
                provider=provider,
                started_at=started_at,
                started=started,
                retry_reason=retry_reason,
                validation_result=str(error),
                final_status="retryable_failed" if retry else "failed",
                result=result,
            )
            if not retry:
                raise ReviewExecutionError("CHALLENGER_POLICY_RETRY_EXHAUSTED", attempts) from error
            policy_retries += 1
            retry_reason = "policy_violation"
            feedback = f"Correct this validator failure: {error}"
            continue
        if result.usage.output_tokens > 2_000:
            _emit_challenger_attempt(
                attempt_sink,
                attempt_id=attempt_id,
                provider=provider,
                started_at=started_at,
                started=started,
                retry_reason=retry_reason,
                validation_result="AGENT_BUDGET_EXCEEDED:CHALLENGER_OUTPUT_TOKENS",
                final_status="failed",
                result=result,
            )
            raise ReviewExecutionError(
                "AGENT_BUDGET_EXCEEDED:CHALLENGER_OUTPUT_TOKENS", attempts
            )
        _emit_challenger_attempt(
            attempt_sink,
            attempt_id=attempt_id,
            provider=provider,
            started_at=started_at,
            started=started,
            retry_reason=retry_reason,
            validation_result="accepted",
            final_status="accepted",
            result=result,
        )
        return result.model_copy(
            update={
                "usage": result.usage.model_copy(
                    update={"provider_attempts": attempts}
                )
            }
        )
    raise ReviewExecutionError("CHALLENGER_ATTEMPT_BUDGET_EXHAUSTED", attempts)


def execute_grounded_review(
    packet: ObservableCasePacket,
    role_id: str,
    provider: ReviewProvider,
    *,
    validator: ResultValidator,
    max_provider_attempts: int,
    attempt_sink: AttemptSink | None = None,
    review_round: int = 0,
    timeout_seconds: float = 120.0,
    max_output_tokens: int = 1_500,
    initial_feedback: str | None = None,
) -> ProviderReviewResult:
    if max_provider_attempts < 1:
        raise ValueError("AGENT_BUDGET_EXCEEDED:PROVIDER_ATTEMPTS")
    attempts = 0
    transport_retries = 0
    schema_retries = 0
    policy_retries = 0
    retry_reason: str | None = None
    feedback = initial_feedback

    while attempts < max_provider_attempts:
        attempts += 1
        attempt_id = str(uuid4())
        started_at = datetime.now(UTC)
        started = time.perf_counter()
        _emit_attempt(
            attempt_sink,
            attempt_id=attempt_id,
            provider=provider,
            role_id=role_id,
            review_round=review_round,
            started_at=started_at,
            started=started,
            retry_reason=retry_reason,
            validation_result="started",
            final_status="running",
            completed=False,
        )
        try:
            result = _review_with_timeout(
                provider, packet, role_id, feedback, timeout_seconds
            )
        except ProviderUsageLimitError as error:
            _emit_attempt(
                attempt_sink,
                attempt_id=attempt_id,
                provider=provider,
                role_id=role_id,
                review_round=review_round,
                started_at=started_at,
                started=started,
                retry_reason=retry_reason,
                validation_result="PROVIDER_USAGE_LIMIT",
                final_status="failed",
            )
            raise ReviewExecutionError("PROVIDER_USAGE_LIMIT", attempts) from error
        except ProviderCallTimeout as error:
            _emit_attempt(
                attempt_sink,
                attempt_id=attempt_id,
                provider=provider,
                role_id=role_id,
                review_round=review_round,
                started_at=started_at,
                started=started,
                retry_reason=retry_reason,
                validation_result="ROLE_TIMEOUT",
                final_status="failed",
            )
            raise ReviewExecutionError("ROLE_TIMEOUT", attempts) from error
        except (ConnectionError, APIConnectionError, RateLimitError, InternalServerError) as error:
            retry = transport_retries < 1 and attempts < max_provider_attempts
            _emit_attempt(
                attempt_sink,
                attempt_id=attempt_id,
                provider=provider,
                role_id=role_id,
                review_round=review_round,
                started_at=started_at,
                started=started,
                retry_reason=retry_reason,
                validation_result=type(error).__name__,
                final_status="retryable_failed" if retry else "failed",
            )
            if not retry:
                raise ReviewExecutionError("TRANSPORT_RETRY_EXHAUSTED", attempts) from error
            transport_retries += 1
            retry_reason = "transport_error"
            feedback = None
            continue
        except StructuredReviewError as error:
            retry = schema_retries < 1 and attempts < max_provider_attempts
            _emit_attempt(
                attempt_sink,
                attempt_id=attempt_id,
                provider=provider,
                role_id=role_id,
                review_round=review_round,
                started_at=started_at,
                started=started,
                retry_reason=retry_reason,
                validation_result=error.code,
                final_status="retryable_failed" if retry else "failed",
            )
            if not retry:
                raise ReviewExecutionError("SCHEMA_REPAIR_EXHAUSTED", attempts) from error
            schema_retries += 1
            retry_reason = "schema_invalid"
            feedback = "Return a valid RoleReview matching the declared schema exactly."
            continue
        except Exception as error:
            _emit_attempt(
                attempt_sink,
                attempt_id=attempt_id,
                provider=provider,
                role_id=role_id,
                review_round=review_round,
                started_at=started_at,
                started=started,
                retry_reason=retry_reason,
                validation_result=type(error).__name__,
                final_status="failed",
            )
            raise ReviewExecutionError("PROVIDER_ATTEMPT_FAILED", attempts) from error

        if result.usage.output_tokens > max_output_tokens:
            _emit_attempt(
                attempt_sink,
                attempt_id=attempt_id,
                provider=provider,
                role_id=role_id,
                review_round=review_round,
                started_at=started_at,
                started=started,
                retry_reason=retry_reason,
                validation_result="AGENT_BUDGET_EXCEEDED:ROLE_OUTPUT_TOKENS",
                final_status="failed",
                result=result,
            )
            raise ReviewExecutionError(
                "AGENT_BUDGET_EXCEEDED:ROLE_OUTPUT_TOKENS", attempts
            )

        try:
            validator(result)
        except ValueError as error:
            retry = policy_retries < 1 and attempts < max_provider_attempts
            _emit_attempt(
                attempt_sink,
                attempt_id=attempt_id,
                provider=provider,
                role_id=role_id,
                review_round=review_round,
                started_at=started_at,
                started=started,
                retry_reason=retry_reason,
                validation_result=str(error),
                final_status="retryable_failed" if retry else "failed",
                result=result,
            )
            if not retry:
                raise ReviewExecutionError("POLICY_RETRY_EXHAUSTED", attempts) from error
            policy_retries += 1
            retry_reason = "policy_violation"
            feedback = f"Correct this validator failure without adding new sources: {error}"
            continue

        _emit_attempt(
            attempt_sink,
            attempt_id=attempt_id,
            provider=provider,
            role_id=role_id,
            review_round=review_round,
            started_at=started_at,
            started=started,
            retry_reason=retry_reason,
            validation_result="accepted",
            final_status="accepted",
            result=result,
        )
        return result.model_copy(
            update={
                "usage": result.usage.model_copy(
                    update={"provider_attempts": attempts}
                )
            }
        )
    raise ReviewExecutionError("PROVIDER_ATTEMPT_BUDGET_EXHAUSTED", attempts)


def _review(
    provider: ReviewProvider,
    packet: ObservableCasePacket,
    role_id: str,
    feedback: str | None,
) -> ProviderReviewResult:
    repair = getattr(provider, "review_with_feedback", None)
    if feedback and callable(repair):
        return cast(ProviderReviewResult, repair(packet, role_id, feedback))
    return provider.review(packet, role_id)


def _review_with_timeout(
    provider: ReviewProvider,
    packet: ObservableCasePacket,
    role_id: str,
    feedback: str | None,
    timeout_seconds: float,
) -> ProviderReviewResult:
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="soc-ot-attempt")
    future = executor.submit(_review, provider, packet, role_id, feedback)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError:
        future.cancel()
        raise ProviderCallTimeout("ROLE_TIMEOUT") from None
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _challenge_with_timeout(
    provider: ReviewProvider,
    packet: ObservableCasePacket,
    reviews: list[RoleReview],
    feedback: str | None,
    timeout_seconds: float,
) -> ChallengerProviderResult:
    challenge = getattr(provider, "challenge", None)
    retry = getattr(provider, "challenge_with_feedback", None)
    if not callable(challenge):
        raise ReviewExecutionError("CHALLENGER_PROVIDER_UNSUPPORTED", 0)
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="soc-ot-challenger")
    future = executor.submit(
        retry if feedback and callable(retry) else challenge,
        packet,
        reviews,
        *([feedback] if feedback and callable(retry) else []),
    )
    try:
        return cast(ChallengerProviderResult, future.result(timeout=timeout_seconds))
    except FutureTimeoutError:
        future.cancel()
        raise ProviderCallTimeout("CHALLENGER_TIMEOUT") from None
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _chair_with_timeout(
    provider: ReviewProvider,
    packet: ObservableCasePacket,
    dossier: DecisionDossier,
    allowed_decision_types: list[DecisionType],
    feedback: str | None,
    timeout_seconds: float,
) -> ChairProviderResult:
    decide = getattr(provider, "decide", None)
    retry = getattr(provider, "decide_with_feedback", None)
    if not callable(decide):
        raise ReviewExecutionError("CHAIR_PROVIDER_UNSUPPORTED", 0)
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="soc-ot-chair")
    future = executor.submit(
        retry if feedback and callable(retry) else decide,
        packet,
        dossier,
        allowed_decision_types,
        *([feedback] if feedback and callable(retry) else []),
    )
    try:
        return cast(ChairProviderResult, future.result(timeout=timeout_seconds))
    except FutureTimeoutError:
        future.cancel()
        raise ProviderCallTimeout("CHAIR_TIMEOUT") from None
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _validate_challenger(
    packet: ObservableCasePacket,
    reviews: list[RoleReview],
    challenger: ChallengerReview,
) -> None:
    role_ids = {item.role_id for item in reviews}
    claim_ids = {item.claim_id for item in packet.claims}
    for objection in challenger.objections:
        if objection.target_role_id not in role_ids:
            raise ValueError("CHALLENGER_TARGET_ROLE_UNKNOWN")
        if not set(objection.claim_ids) <= claim_ids:
            raise ValueError("CHALLENGER_CLAIM_UNKNOWN")


def _validate_chair(
    packet: ObservableCasePacket,
    dossier: DecisionDossier,
    allowed_decision_types: list[DecisionType],
    result: ChairProviderResult,
) -> None:
    decision = result.decision
    if decision.case_id != packet.case_id:
        raise ValueError("CHAIR_CASE_MISMATCH")
    valid_option_ids = {item.option_id for item in packet.alternatives}
    if (
        decision.selected_option_id is not None
        and decision.selected_option_id not in valid_option_ids
    ):
        raise ValueError("CHAIR_OPTION_UNKNOWN")
    dissent_roles = {item.role_id for item in dossier.dissent}
    if not dissent_roles <= set(decision.dissent_acknowledged):
        raise ValueError("CHAIR_DISSENT_NOT_ACKNOWLEDGED")
    validate_decision_policy(
        decision, allowed_decision_types, current_step=packet.current_step
    )


def _emit_chair_attempt(
    sink: AttemptSink | None,
    *,
    attempt_id: str,
    provider: ReviewProvider,
    started_at: datetime,
    started: float,
    retry_reason: str | None,
    validation_result: str,
    final_status: str,
    result: ChairProviderResult | None = None,
    completed: bool = True,
) -> None:
    if sink is None:
        return
    usage = result.usage if result is not None else None
    sink(
        ProviderAttemptMetadata(
            attempt_id=attempt_id,
            role_id="decision_chair",
            review_round=0,
            provider=provider.name,
            requested_model=str(getattr(provider, "chair_model", provider.name)),
            returned_model=result.returned_model if result else None,
            started_at=started_at,
            completed_at=datetime.now(UTC) if completed else None,
            duration_ms=(
                max(0, int((time.perf_counter() - started) * 1000)) if completed else 0
            ),
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
            estimated_cost_usd=usage.estimated_cost_usd if usage else 0.0,
            retry_reason=retry_reason,
            validation_result=validation_result[:200],
            final_status=final_status,
        )
    )


def _emit_challenger_attempt(
    sink: AttemptSink | None,
    *,
    attempt_id: str,
    provider: ReviewProvider,
    started_at: datetime,
    started: float,
    retry_reason: str | None,
    validation_result: str,
    final_status: str,
    result: ChallengerProviderResult | None = None,
    completed: bool = True,
) -> None:
    if sink is None:
        return
    usage = result.usage if result is not None else None
    sink(
        ProviderAttemptMetadata(
            attempt_id=attempt_id,
            role_id="challenger",
            review_round=0,
            provider=provider.name,
            requested_model=str(getattr(provider, "challenger_model", provider.name)),
            returned_model=result.returned_model if result else None,
            started_at=started_at,
            completed_at=datetime.now(UTC) if completed else None,
            duration_ms=(
                max(0, int((time.perf_counter() - started) * 1000)) if completed else 0
            ),
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
            estimated_cost_usd=usage.estimated_cost_usd if usage else 0.0,
            retry_reason=retry_reason,
            validation_result=validation_result[:200],
            final_status=final_status,
        )
    )


def _emit_attempt(
    sink: AttemptSink | None,
    *,
    attempt_id: str,
    provider: ReviewProvider,
    role_id: str,
    review_round: int,
    started_at: datetime,
    started: float,
    retry_reason: str | None,
    validation_result: str,
    final_status: str,
    result: ProviderReviewResult | None = None,
    completed: bool = True,
) -> None:
    if sink is None:
        return
    completed_at = datetime.now(UTC) if completed else None
    usage = result.usage if result is not None else None
    sink(
        ProviderAttemptMetadata(
            attempt_id=attempt_id,
            role_id=role_id,
            review_round=review_round,
            provider=provider.name,
            requested_model=str(getattr(provider, "model", provider.name)),
            returned_model=result.returned_model if result is not None else None,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=(
                max(0, int((time.perf_counter() - started) * 1000)) if completed else 0
            ),
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
            estimated_cost_usd=usage.estimated_cost_usd if usage else 0.0,
            retry_reason=retry_reason,
            validation_result=validation_result[:200],
            final_status=final_status,
        )
    )
