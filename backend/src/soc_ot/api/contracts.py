from datetime import datetime
from typing import Literal

from soc_ot.agents.contracts import AgentRunBudgetPlan, ProviderReviewResult
from soc_ot.agents.multi_role import DossierExecution, SimulatedDecision
from soc_ot.domain.models import AgentRunStatus, StrictModel


class ReviewRunView(StrictModel):
    run_id: str
    run_kind: Literal["role_review", "dossier"]
    topology: Literal["B1", "B2", "B3"] | None
    case_id: str
    actor_id: str
    packet_hash: str
    role_id: str
    provider: str
    requested_model: str
    returned_model: str | None
    contract_version: str
    prompt_bundle_version: str
    prompt_bundle_hash: str
    policy_version: str
    budget_plan: AgentRunBudgetPlan
    status: AgentRunStatus
    attempt_no: int
    max_attempts: int
    cancel_requested: bool
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    heartbeat_at: datetime | None = None
    next_retry_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    result: ProviderReviewResult | DossierExecution | None = None
    error_code: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    status_url: str
    events_url: str


class RunTelemetryView(StrictModel):
    run_count: int
    completed_count: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    provider_attempts: int


class OutcomeAdvanceRequest(StrictModel):
    command_schema_version: str = "outcome-advance-command.v1"
    from_step: int
    to_step: int
    decision: SimulatedDecision | None = None


class ReviewRunRequest(StrictModel):
    command_schema_version: str = "review-run-command.v1"
    scope: Literal["role_review", "dossier"] = "dossier"
    role_id: str | None = None
