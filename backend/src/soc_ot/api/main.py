import json
import time
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from soc_ot import __version__
from soc_ot.agents.multi_role import AblationResult, DossierExecution
from soc_ot.api.contracts import (
    OutcomeAdvanceRequest,
    ReviewRunRequest,
    ReviewRunView,
    RunTelemetryView,
)
from soc_ot.application.development_twin import (
    DevelopmentTimelineProjection,
    build_development_timeline,
)
from soc_ot.application.evaluation import CaseEvaluation
from soc_ot.application.multi_role import finalize_dossier_decision
from soc_ot.application.outcome_advances import (
    InMemoryOutcomeAdvanceRepository,
    OutcomeAdvanceConflict,
    OutcomeAdvanceRepository,
    PostgresOutcomeAdvanceRepository,
)
from soc_ot.application.outcomes import OutcomeSnapshot
from soc_ot.application.packets import build_observable_case_packet
from soc_ot.application.ports import EvaluationRepository, HiddenCaseReader
from soc_ot.application.projections import (
    DecisionListItemProjection,
    build_decision_list_item,
    sort_decision_list_items,
)
from soc_ot.application.repositories import CaseRepository, PostgresCaseRepository, StoredCase
from soc_ot.application.review_runs import (
    InMemoryReviewRunRepository,
    PostgresReviewRunRepository,
    ReviewRun,
    ReviewRunRepository,
    enqueue_dossier_review,
    enqueue_role_review,
)
from soc_ot.application.simulated_decisions import (
    InMemorySimulatedDecisionRepository,
    PostgresSimulatedDecisionRepository,
    SimulatedDecisionConflict,
    SimulatedDecisionRepository,
)
from soc_ot.application.workspace_contracts import DecisionWorkspaceProjectionV2
from soc_ot.application.workspace_projection_v2 import build_workspace_projection_v2
from soc_ot.config import ROOT_DIR, get_settings
from soc_ot.domain.models import AgentRunStatus, Evidence
from soc_ot.infrastructure.database import get_outcome_engine, get_runtime_engine
from soc_ot.infrastructure.evaluation_repository import (
    EvaluationConflict,
    FixtureEvaluationRepository,
    PostgresEvaluationRepository,
)
from soc_ot.infrastructure.fixtures import FixtureRepository
from soc_ot.infrastructure.hidden_repository import (
    FixtureHiddenCaseReader,
    PostgresHiddenCaseRepository,
)

EXPECTED_DB_REVISION = "0019_agent_run_topology"


def _default_repository() -> CaseRepository:
    return PostgresCaseRepository(get_runtime_engine())


def create_app(
    repository: CaseRepository | None = None,
    run_repository: ReviewRunRepository | None = None,
    outcome_repository: OutcomeAdvanceRepository | None = None,
    hidden_reader: HiddenCaseReader | None = None,
    evaluation_repository: EvaluationRepository | None = None,
    decision_repository: SimulatedDecisionRepository | None = None,
) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="SoC Operational Decision Twin", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Idempotency-Key", "If-Match"],
    )
    repository_provider = (lambda: repository) if repository is not None else _default_repository
    local_runs = InMemoryReviewRunRepository() if repository is not None else None

    def run_repository_provider() -> ReviewRunRepository:
        if run_repository is not None:
            return run_repository
        if local_runs is not None:
            return local_runs
        return PostgresReviewRunRepository(get_runtime_engine())

    local_fixtures = FixtureRepository(ROOT_DIR / "fixtures")
    local_evaluations = evaluation_repository or (
        FixtureEvaluationRepository(local_fixtures)
        if repository is not None
        else PostgresEvaluationRepository(local_fixtures, get_outcome_engine())
    )
    local_decisions = decision_repository or (
        InMemorySimulatedDecisionRepository()
        if repository is not None
        else PostgresSimulatedDecisionRepository(get_runtime_engine())
    )

    def outcome_repository_provider() -> OutcomeAdvanceRepository:
        if outcome_repository is not None:
            return outcome_repository
        if repository is not None:
            return InMemoryOutcomeAdvanceRepository()
        return PostgresOutcomeAdvanceRepository(get_outcome_engine())

    local_outcomes = outcome_repository_provider()

    def stable_outcome_repository_provider() -> OutcomeAdvanceRepository:
        return local_outcomes

    def hidden_reader_provider() -> HiddenCaseReader:
        if hidden_reader is not None:
            return hidden_reader
        if repository is not None:
            return FixtureHiddenCaseReader(local_fixtures)
        return PostgresHiddenCaseRepository(get_outcome_engine())

    def evaluation_repository_provider() -> EvaluationRepository:
        return local_evaluations

    Repository = Annotated[CaseRepository, Depends(repository_provider)]
    RunRepository = Annotated[ReviewRunRepository, Depends(run_repository_provider)]
    OutcomeRepository = Annotated[
        OutcomeAdvanceRepository, Depends(stable_outcome_repository_provider)
    ]
    HiddenReader = Annotated[HiddenCaseReader, Depends(hidden_reader_provider)]
    Evaluations = Annotated[
        EvaluationRepository, Depends(evaluation_repository_provider)
    ]
    DecisionCommands = Annotated[
        SimulatedDecisionRepository, Depends(lambda: local_decisions)
    ]

    @app.get("/health/live", tags=["health"])
    def live() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/health/ready", tags=["health"])
    def ready() -> dict[str, str]:
        if repository is None:
            with get_runtime_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
                revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
                if revision != EXPECTED_DB_REVISION:
                    raise HTTPException(
                        status_code=503,
                        detail={
                            "code": "DATABASE_REVISION_MISMATCH",
                            "expected": EXPECTED_DB_REVISION,
                            "actual": revision,
                        },
                    )
        else:
            revision = "in-memory"
        return {"status": "ready", "stage": "I7", "database_revision": str(revision)}

    @app.get(
        "/api/v1/decision-cases",
        response_model=list[DecisionListItemProjection],
        tags=["decision-cases"],
    )
    def list_cases(repo: Repository) -> list[DecisionListItemProjection]:
        return sort_decision_list_items(
            [build_decision_list_item(item) for item in repo.list()]
        )

    @app.get(
        "/api/v1/decision-cases/{case_id}/workspace",
        response_model=DecisionWorkspaceProjectionV2,
        tags=["decision-cases"],
    )
    def get_workspace(
        case_id: str,
        repo: Repository,
        runs: RunRepository,
        decisions: DecisionCommands,
        outcomes: OutcomeRepository,
        evaluations: Evaluations,
        at_step: int | None = None,
    ) -> DecisionWorkspaceProjectionV2:
        try:
            stored = _require_case(repo, case_id)
            latest_dossier_run = runs.latest_for_case(case_id, run_kind="dossier")
            latest_decision = decisions.latest(case_id)
            latest_outcome = outcomes.latest(case_id)
            latest_evaluation = evaluations.latest(case_id)
            if (
                at_step is None
                and latest_outcome is not None
                and latest_outcome.current_step > stored.case.current_step
            ):
                stored = StoredCase(
                    case=stored.case.model_copy(
                        update={"current_step": latest_outcome.current_step}
                    ),
                    aggregate_version=stored.aggregate_version,
                )
            dossier = (
                latest_dossier_run.result.dossier
                if latest_dossier_run is not None
                and isinstance(latest_dossier_run.result, DossierExecution)
                else None
            )
            return build_workspace_projection_v2(
                stored,
                at_step=at_step,
                content=local_fixtures.load_workspace_ux(case_id),
                dossier=dossier,
                dossier_run_status=(
                    latest_dossier_run.status if latest_dossier_run is not None else None
                ),
                dossier_run_id=(
                    latest_dossier_run.run_id if latest_dossier_run is not None else None
                ),
                decision_result=latest_decision,
                outcome=latest_outcome,
                evaluation=latest_evaluation,
            )
        except ValueError as error:
            if str(error) == "DEVELOPMENT_STEP_OUT_OF_RANGE":
                raise HTTPException(
                    status_code=422,
                    detail={"code": "DEVELOPMENT_STEP_OUT_OF_RANGE"},
                ) from error
            raise

    @app.get(
        "/api/v1/decision-cases/{case_id}/timeline",
        response_model=DevelopmentTimelineProjection,
        tags=["decision-cases"],
    )
    def get_timeline(
        case_id: str, repo: Repository, at_step: int | None = None
    ) -> DevelopmentTimelineProjection:
        stored = _require_case(repo, case_id)
        try:
            return build_development_timeline(stored, at_step=at_step)
        except ValueError as error:
            if str(error) == "DEVELOPMENT_STEP_OUT_OF_RANGE":
                raise HTTPException(
                    status_code=422,
                    detail={"code": "DEVELOPMENT_STEP_OUT_OF_RANGE"},
                ) from error
            raise

    @app.get(
        "/api/v1/decision-cases/{case_id}/evidence",
        response_model=list[Evidence],
        tags=["decision-cases"],
    )
    def get_evidence(case_id: str, repo: Repository) -> list[Evidence]:
        case = _require_case(repo, case_id).case
        return [item for item in case.evidence if item.available_at_step <= case.current_step]

    @app.get("/api/v1/dev/fixtures/{case_id}/observable", tags=["developer"])
    def get_observable_packet(
        case_id: str, repo: Repository, at_step: int | None = None
    ) -> dict[str, object]:
        try:
            packet = build_observable_case_packet(
                _require_case(repo, case_id).case,
                at_step=at_step,
            )
        except ValueError as error:
            if str(error) == "DEVELOPMENT_STEP_OUT_OF_RANGE":
                raise HTTPException(
                    status_code=422,
                    detail={"code": "DEVELOPMENT_STEP_OUT_OF_RANGE"},
                ) from error
            raise
        return packet.model_dump(mode="json")

    @app.post("/api/v1/decision-cases/{case_id}/review-runs", tags=["agent-runs"])
    def create_review_run(
        case_id: str,
        repo: Repository,
        runs: RunRepository,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        if_match: Annotated[str, Header(alias="If-Match")],
        role_id: str | None = None,
        command: ReviewRunRequest | None = None,
    ) -> ReviewRunView:
        stored = _require_case(repo, case_id)
        _require_version(stored, if_match)
        request = command or ReviewRunRequest()
        selected_role = request.role_id or role_id or stored.case.required_role_ids[0]
        try:
            model = settings.role_model if settings.llm_mode == "openai" else "replay-v1"
            if request.scope == "dossier":
                run = enqueue_dossier_review(
                    repo,
                    runs,
                    case_id=case_id,
                    provider=settings.llm_mode,
                    model=model,
                    idempotency_key=idempotency_key,
                    actor_id=settings.local_actor_id,
                    max_case_cost_usd=settings.max_case_cost_usd,
                )
            else:
                run = enqueue_role_review(
                    repo,
                    runs,
                    case_id=case_id,
                    role_id=selected_role,
                    provider=settings.llm_mode,
                    model=model,
                    idempotency_key=idempotency_key,
                    actor_id=settings.local_actor_id,
                    max_case_cost_usd=settings.max_case_cost_usd,
                )
        except ValueError as error:
            raise HTTPException(status_code=422, detail={"code": str(error)}) from error
        return _run_response(run)

    @app.get("/api/v1/runs/{run_id}", tags=["agent-runs"])
    def get_run(run_id: str, runs: RunRepository) -> ReviewRunView:
        run = runs.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND"})
        return _run_response(run)

    @app.post("/api/v1/runs/{run_id}/cancel", tags=["agent-runs"])
    def cancel_run(
        run_id: str,
        repo: Repository,
        runs: RunRepository,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        if_match: Annotated[str, Header(alias="If-Match")],
    ) -> ReviewRunView:
        try:
            current = runs.get(run_id)
            if current is None:
                raise KeyError(run_id)
            _require_version(_require_case(repo, current.case_id), if_match)
            return _run_response(runs.cancel(run_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND"}) from error

    @app.post("/api/v1/runs/{run_id}/retry", tags=["agent-runs"])
    def retry_run(
        run_id: str,
        repo: Repository,
        runs: RunRepository,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        if_match: Annotated[str, Header(alias="If-Match")],
    ) -> ReviewRunView:
        try:
            current = runs.get(run_id)
            if current is None:
                raise KeyError(run_id)
            _require_version(_require_case(repo, current.case_id), if_match)
            return _run_response(runs.retry(run_id, idempotency_key=idempotency_key))
        except KeyError as error:
            raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND"}) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail={"code": str(error)}) from error

    @app.get("/api/v1/runs/{run_id}/events", tags=["agent-runs"])
    def stream_run_events(
        run_id: str,
        runs: RunRepository,
        follow: bool = True,
        last_event_id: Annotated[int | None, Header(alias="Last-Event-ID")] = None,
    ) -> StreamingResponse:
        if runs.get(run_id) is None:
            raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND"})

        def generate() -> Iterator[str]:
            cursor = last_event_id or 0
            started = time.monotonic()
            while True:
                emitted = False
                for event in runs.events(run_id):
                    sequence_value = event["sequence"]
                    if not isinstance(sequence_value, int):
                        raise ValueError("RUN_EVENT_SEQUENCE_INVALID")
                    sequence = sequence_value
                    if sequence <= cursor:
                        continue
                    emitted = True
                    cursor = sequence
                    yield (
                        f"id: {sequence}\nevent: {event['event_type']}\n"
                        f"data: {json.dumps(event)}\n\n"
                    )
                current = runs.get(run_id)
                terminal = current is None or current.status in {
                    AgentRunStatus.PARTIALLY_COMPLETED,
                    AgentRunStatus.COMPLETED,
                    AgentRunStatus.FAILED,
                    AgentRunStatus.CANCELLED,
                }
                if terminal or not follow:
                    break
                if not emitted:
                    yield ": heartbeat\n\n"
                if time.monotonic() - started >= 30:
                    break
                time.sleep(0.25)

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.post(
        "/api/v1/decision-cases/{case_id}/simulated-decisions",
        tags=["simulated-decisions"],
    )
    def create_simulated_decision(
        case_id: str,
        repo: Repository,
        runs: RunRepository,
        decisions: DecisionCommands,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        if_match: Annotated[str, Header(alias="If-Match")],
        review_run_id: str,
    ) -> AblationResult:
        stored = _require_case(repo, case_id)
        review_run = runs.get(review_run_id)
        if (
            review_run is None
            or review_run.status is not AgentRunStatus.COMPLETED
            or not isinstance(review_run.result, DossierExecution)
        ):
            raise HTTPException(status_code=409, detail={"code": "DOSSIER_RUN_NOT_READY"})

        def build_result() -> AblationResult:
            assert review_run is not None
            assert isinstance(review_run.result, DossierExecution)
            packet = build_observable_case_packet(stored.case)
            decision = finalize_dossier_decision(
                packet,
                review_run.result,
                stored.case.allowed_decision_types,
            )
            return AblationResult(
                topology=review_run.result.topology,
                role_count=review_run.result.role_count,
                challenger_used=review_run.result.challenger_used,
                chair_used=review_run.result.topology == "B3",
                input_tokens=review_run.result.input_tokens,
                output_tokens=review_run.result.output_tokens,
                estimated_cost_usd=review_run.result.estimated_cost_usd,
                provider_attempts=review_run.result.provider_attempts,
                dossier=review_run.result.dossier,
                decision=decision,
            )

        try:
            return decisions.create(
                case_id=case_id,
                review_run_id=review_run_id,
                idempotency_key=idempotency_key,
                expected_aggregate_version=_expected_version(if_match),
                actual_aggregate_version=stored.aggregate_version,
                actor_id=settings.local_actor_id,
                factory=build_result,
            )
        except SimulatedDecisionConflict as error:
            raise HTTPException(status_code=409, detail={"code": str(error)}) from error

    @app.post("/api/v1/decision-cases/{case_id}/outcome-advances", tags=["outcomes"])
    def create_outcome_advance(
        case_id: str,
        command: OutcomeAdvanceRequest,
        repo: Repository,
        outcomes: OutcomeRepository,
        decisions: DecisionCommands,
        hidden_cases: HiddenReader,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        if_match: Annotated[str, Header(alias="If-Match")],
    ) -> OutcomeSnapshot:
        stored = _require_case(repo, case_id)
        hidden = hidden_cases.get(case_id)
        if hidden is None:
            raise HTTPException(status_code=404, detail={"code": "HIDDEN_CASE_NOT_FOUND"})
        latest_decision = decisions.latest(case_id)
        decision = command.decision or (
            latest_decision.decision if latest_decision is not None else None
        )
        if decision is None:
            raise HTTPException(status_code=409, detail={"code": "DECISION_NOT_READY"})
        if latest_decision is not None and decision != latest_decision.decision:
            raise HTTPException(status_code=409, detail={"code": "DECISION_MISMATCH"})
        try:
            return outcomes.advance(
                stored.case,
                hidden,
                decision,
                from_step=command.from_step,
                to_step=command.to_step,
                idempotency_key=idempotency_key,
                expected_aggregate_version=_expected_version(if_match),
                actor_id=settings.local_actor_id,
            )
        except OutcomeAdvanceConflict as error:
            raise HTTPException(status_code=409, detail={"code": str(error)}) from error

    @app.post("/api/v1/decision-cases/{case_id}/evaluations", tags=["evaluations"])
    def create_evaluation(
        case_id: str,
        repo: Repository,
        evaluations: Evaluations,
        outcomes: OutcomeRepository,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
        if_match: Annotated[str, Header(alias="If-Match")],
    ) -> CaseEvaluation:
        stored = _require_case(repo, case_id)
        _require_version(stored, if_match)
        latest_outcome = outcomes.latest(case_id)
        _require_evaluation_ready(
            stored,
            evaluations,
            observed_step=(latest_outcome.current_step if latest_outcome else None),
        )
        try:
            return evaluations.evaluate(
                case_id,
                idempotency_key=idempotency_key,
                aggregate_version=stored.aggregate_version,
                actor_id=settings.local_actor_id,
            )
        except EvaluationConflict as error:
            raise HTTPException(status_code=409, detail={"code": str(error)}) from error

    @app.get("/api/v1/decision-cases/{case_id}/evaluation", tags=["evaluations"])
    def get_evaluation(
        case_id: str,
        repo: Repository,
        evaluations: Evaluations,
        outcomes: OutcomeRepository,
    ) -> CaseEvaluation:
        stored = _require_case(repo, case_id)
        latest_outcome = outcomes.latest(case_id)
        _require_evaluation_ready(
            stored,
            evaluations,
            observed_step=(latest_outcome.current_step if latest_outcome else None),
        )
        result = evaluations.latest(case_id)
        if result is None:
            raise HTTPException(status_code=404, detail={"code": "EVALUATION_NOT_FOUND"})
        return result

    @app.get("/api/v1/telemetry/agent-runs", tags=["telemetry"])
    def agent_run_telemetry(runs: RunRepository) -> RunTelemetryView:
        return RunTelemetryView.model_validate(runs.telemetry())

    return app


def _require_case(repository: CaseRepository, case_id: str) -> StoredCase:
    stored = repository.get(case_id)
    if stored is None:
        raise HTTPException(status_code=404, detail={"code": "CASE_NOT_FOUND"})
    return stored


def _require_version(stored: StoredCase, if_match: str) -> None:
    if _expected_version(if_match) != stored.aggregate_version:
        raise HTTPException(status_code=409, detail={"code": "CASE_VERSION_CONFLICT"})


def _expected_version(if_match: str) -> int:
    normalized = if_match.strip().strip('"')
    try:
        return int(normalized)
    except ValueError as error:
        raise HTTPException(
            status_code=422, detail={"code": "INVALID_IF_MATCH"}
        ) from error


def _require_evaluation_ready(
    stored: StoredCase,
    evaluations: EvaluationRepository,
    *,
    observed_step: int | None = None,
) -> None:
    required_step = evaluations.required_step(stored.case.case_id)
    current_step = max(stored.case.current_step, observed_step or 0)
    if current_step < required_step:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "OUTCOME_NOT_REVEALED",
                "current_step": current_step,
                "required_step": required_step,
            },
        )


app = create_app()


def _run_response(run: ReviewRun) -> ReviewRunView:
    return ReviewRunView.model_validate(
        {
            **run.__dict__,
            "status_url": f"/api/v1/runs/{run.run_id}",
            "events_url": f"/api/v1/runs/{run.run_id}/events",
        }
    )
