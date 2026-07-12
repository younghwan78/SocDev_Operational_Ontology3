import argparse
import os
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError

from openai import APIConnectionError, InternalServerError, RateLimitError

from soc_ot.agents.contracts import ProviderReviewResult
from soc_ot.agents.providers import OpenAIResponsesProvider, ReplayProvider, ReviewProvider
from soc_ot.application.multi_role import AgentRuntimeBudget
from soc_ot.application.repositories import CaseRepository, PostgresCaseRepository
from soc_ot.application.review_runs import (
    AgentRunResult,
    PostgresReviewRunRepository,
    ReviewRun,
    ReviewRunRepository,
    RunConflictError,
    execute_claimed_run,
)
from soc_ot.config import Settings, get_settings
from soc_ot.infrastructure.database import get_runtime_engine


def build_provider(settings: Settings, provider_name: str) -> ReviewProvider:
    if provider_name == "replay":
        return ReplayProvider()
    if provider_name == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY_REQUIRED_FOR_LIVE_MODE")
        return OpenAIResponsesProvider(
            api_key=settings.openai_api_key,
            model=settings.role_model,
            challenger_model=settings.challenger_model,
            chair_model=settings.chair_model,
            timeout_seconds=min(settings.max_case_runtime_seconds, 120),
            input_cost_per_million_usd=settings.role_input_cost_per_million_usd,
            output_cost_per_million_usd=settings.role_output_cost_per_million_usd,
        )
    raise ValueError(f"UNSUPPORTED_PROVIDER:{provider_name}")


def process_one(worker_id: str | None = None, lease_seconds: int = 180) -> bool:
    settings = get_settings()
    cases = PostgresCaseRepository(get_runtime_engine())
    runs = PostgresReviewRunRepository(get_runtime_engine())
    worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"
    run = runs.claim(worker_id, lease_seconds)
    if run is None:
        return False
    try:
        provider = build_provider(settings, run.provider)
        result = execute_with_lease_heartbeat(
            run,
            cases,
            runs,
            provider,
            worker_id=worker_id,
            timeout_seconds=(
                settings.max_case_runtime_seconds
                if run.run_kind == "dossier"
                else min(
                    settings.max_case_runtime_seconds,
                    settings.role_timeout_seconds + 5,
                )
            ),
            lease_seconds=lease_seconds,
            runtime_budget=AgentRuntimeBudget(
                max_case_cost_usd=settings.max_case_cost_usd
            ),
        )
        result_cost = (
            result.usage.estimated_cost_usd
            if isinstance(result, ProviderReviewResult)
            else result.estimated_cost_usd
        )
        if result_cost > settings.max_case_cost_usd:
            raise ValueError("RUN_COST_BUDGET_EXCEEDED")
        runs.complete(run.run_id, worker_id, result)
    except RunConflictError:
        return True
    except Exception as error:
        runs.fail(
            run.run_id,
            worker_id,
            type(error).__name__,
            retryable=is_retryable(error),
        )
    return True


def execute_with_lease_heartbeat(
    run: ReviewRun,
    cases: CaseRepository,
    runs: ReviewRunRepository,
    provider: ReviewProvider,
    *,
    worker_id: str,
    timeout_seconds: float,
    lease_seconds: int,
    heartbeat_interval_seconds: float | None = None,
    runtime_budget: AgentRuntimeBudget | None = None,
) -> AgentRunResult:
    interval = heartbeat_interval_seconds or min(10.0, max(1.0, lease_seconds / 3))
    deadline = time.monotonic() + timeout_seconds
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="soc-ot-provider")
    checkpoints = {
        item.review.role_id: item for item in runs.review_checkpoints(run.run_id, 0)
    }
    revision_checkpoints = {
        item.review.role_id: item for item in runs.review_checkpoints(run.run_id, 1)
    }
    challenger_checkpoint = runs.challenger_checkpoint(run.run_id)
    chair_checkpoint = runs.chair_checkpoint(run.run_id)
    future = executor.submit(
        execute_claimed_run,
        run,
        cases,
        provider,
        lambda attempt: runs.record_attempt(run.run_id, attempt),
        checkpoints,
        lambda result, review_round: runs.save_review_checkpoint(
            run.run_id, worker_id, result, review_round
        ),
        runs.attempt_count(run.run_id),
        revision_checkpoints,
        challenger_checkpoint,
        lambda result: runs.save_challenger_checkpoint(
            run.run_id, worker_id, result
        ),
        chair_checkpoint,
        lambda result: runs.save_chair_checkpoint(run.run_id, worker_id, result),
        runtime_budget,
    )
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                future.cancel()
                raise TimeoutError("ROLE_TIMEOUT")
            try:
                return future.result(timeout=min(interval, remaining))
            except FutureTimeoutError:
                current = runs.get(run.run_id)
                if current is None or current.cancel_requested:
                    future.cancel()
                    raise RunConflictError("RUN_CANCELLED_DURING_EXECUTION") from None
                runs.heartbeat(run.run_id, worker_id, lease_seconds)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def is_retryable(error: Exception) -> bool:
    return isinstance(
        error,
        (ConnectionError, APIConnectionError, RateLimitError, InternalServerError),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="SoC OT durable agent worker")
    parser.add_argument("--once", action="store_true", help="claim at most one run")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()
    if args.once:
        process_one()
        return
    while True:
        if not process_one():
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
