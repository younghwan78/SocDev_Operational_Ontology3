from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from soc_ot.infrastructure.database import Base


class DecisionCaseRow(Base):
    __tablename__ = "decision_cases"
    __table_args__ = {"schema": "observable"}

    case_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    fixture_version: Mapped[int] = mapped_column(Integer, nullable=False)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    title_ko: Mapped[str] = mapped_column(String(240), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DomainEventRow(Base):
    __tablename__ = "domain_events"
    __table_args__ = (
        UniqueConstraint("case_id", "aggregate_version", name="uq_event_case_version"),
        {"schema": "audit"},
    )

    event_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(
        String(120), nullable=False, server_default="local-system"
    )
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FixtureImportRunRow(Base):
    __tablename__ = "fixture_import_runs"
    __table_args__ = {"schema": "audit"}

    import_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(80), nullable=False)
    fixture_version: Mapped[int] = mapped_column(Integer, nullable=False)
    fixture_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class HiddenAuthoringAuditRow(Base):
    __tablename__ = "hidden_authoring_audits"
    __table_args__ = {"schema": "audit"}

    audit_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    case_id: Mapped[str] = mapped_column(String(80), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AgentRunRow(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_agent_runs_idempotency_key"),
        {"schema": "observable"},
    )

    run_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    run_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    topology: Mapped[str | None] = mapped_column(String(2))
    case_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    packet_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    role_id: Mapped[str] = mapped_column(String(80), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    requested_model: Mapped[str] = mapped_column(String(100), nullable=False)
    returned_model: Mapped[str | None] = mapped_column(String(100))
    contract_version: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_bundle_version: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_bundle_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    budget_plan: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AgentRunEventRow(Base):
    __tablename__ = "agent_run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_agent_run_events_run_sequence"),
        {"schema": "audit"},
    )

    event_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AgentAttemptRow(Base):
    __tablename__ = "agent_attempts"
    __table_args__ = {"schema": "audit"}

    attempt_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(80), nullable=False)
    role_id: Mapped[str] = mapped_column(String(80), nullable=False)
    review_round: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    requested_model: Mapped[str] = mapped_column(String(100), nullable=False)
    returned_model: Mapped[str | None] = mapped_column(String(100))
    prompt_bundle_version: Mapped[str] = mapped_column(String(80), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(80), nullable=False)
    observable_packet_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    retry_reason: Mapped[str | None] = mapped_column(String(100))
    validation_result: Mapped[str] = mapped_column(String(240), nullable=False)
    final_status: Mapped[str] = mapped_column(String(40), nullable=False)


class AgentRunStepRow(Base):
    __tablename__ = "agent_run_steps"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "step_kind",
            "role_id",
            "review_round",
            name="uq_agent_run_steps_logical_step",
        ),
        {"schema": "observable"},
    )

    step_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    step_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    role_id: Mapped[str] = mapped_column(String(80), nullable=False)
    review_round: Mapped[int] = mapped_column(Integer, nullable=False)
    normalized_output: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class HiddenCaseRow(Base):
    __tablename__ = "hidden_cases"
    __table_args__ = {"schema": "hidden"}

    case_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    fixture_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OutcomeEvaluationRow(Base):
    __tablename__ = "outcome_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key", name="uq_outcome_evaluations_idempotency_key"
        ),
        {"schema": "hidden"},
    )

    evaluation_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    command_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SimulationStateRow(Base):
    __tablename__ = "simulation_states"
    __table_args__ = {"schema": "observable"}

    case_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SimulatedDecisionRow(Base):
    __tablename__ = "simulated_decisions"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key", name="uq_simulated_decisions_idempotency_key"
        ),
        {"schema": "observable"},
    )

    command_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    command_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    case_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    review_run_id: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OutcomeAdvanceRow(Base):
    __tablename__ = "outcome_advances"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_outcome_advances_idempotency_key"),
        {"schema": "hidden"},
    )

    advance_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    command_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    case_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    decision_id: Mapped[str] = mapped_column(String(80), nullable=False)
    from_step: Mapped[int] = mapped_column(Integer, nullable=False)
    to_step: Mapped[int] = mapped_column(Integer, nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
