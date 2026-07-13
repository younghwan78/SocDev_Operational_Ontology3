"""Upgrade persisted simulated decisions to the executable action-plan contract."""

from collections.abc import Sequence

from alembic import op

revision: str = "0017_decision_action_plan_v2"
down_revision: str | None = "0016_agent_run_budget_plan"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _action_plan(decision: str, current_step: str) -> str:
    decision_type = f"({decision} ->> 'decision_type')"
    return f"""
        jsonb_build_object(
            'schema_version', 'decision-action-plan.v1',
            'action_type', CASE
                WHEN {decision_type} IN (
                    'APPROVE', 'APPROVE_WITH_GUARDRAILS', 'RUN_REVERSIBLE_TRIAL'
                ) THEN 'execute'
                WHEN {decision_type} = 'COLLECT_MINIMUM_EVIDENCE' THEN 'collect_evidence'
                WHEN {decision_type} = 'DEFER_UNTIL_TRIGGER' THEN 'defer'
                WHEN {decision_type} = 'ESCALATE' THEN 'escalate'
                ELSE 'reject'
            END,
            'owner', 'decision_chair',
            'action', '기존 v1 결정의 후속 행동을 실행 전에 재검토한다.',
            'due_at_step', {current_step},
            'trigger', 'v2 계약 전환 후 첫 결정 재검토',
            'verification', '새 v2 검토에서 실행 계획의 유효성을 확인한다.',
            'fallback_action', '재검토 전에는 추가 실행 권한을 부여하지 않는다.',
            'evidence_required', CASE
                WHEN {decision_type} = 'COLLECT_MINIMUM_EVIDENCE'
                THEN jsonb_build_array('기존 결정에 필요한 최소 근거 재확인')
                ELSE '[]'::jsonb
            END,
            'escalation_target', CASE
                WHEN {decision_type} = 'ESCALATE' THEN 'program_owner'
                ELSE NULL
            END,
            'questions_to_resolve', CASE
                WHEN {decision_type} = 'ESCALATE'
                THEN jsonb_build_array('기존 결정의 미해결 권한 또는 위험 쟁점')
                ELSE '[]'::jsonb
            END,
            'reopen_condition', CASE
                WHEN {decision_type} = 'REJECT'
                THEN '새로운 관측 근거 또는 수정된 선택지가 확보된다.'
                ELSE NULL
            END
        )
    """


def _upgrade_decision(
    *,
    table: str,
    alias: str,
    column: str,
    path: tuple[str, ...],
    current_step: str,
    extra_where: str = "TRUE",
) -> None:
    json_path = "{" + ",".join(path) + "}"
    decision = f"({alias}.{column} #> '{json_path}')"
    upgraded = (
        f"({decision} || jsonb_build_object("
        f"'schema_version', 'simulated-decision.v2', "
        f"'action_plan', {_action_plan(decision, current_step)}))"
    )
    op.execute(
        f"UPDATE {table} AS {alias} "
        f"SET {column} = jsonb_set({alias}.{column}, '{json_path}', {upgraded}, false) "
        f"WHERE {decision} ->> 'schema_version' = 'simulated-decision.v1' "
        f"AND {extra_where}"
    )


def _downgrade_decision(
    *, table: str, alias: str, column: str, path: tuple[str, ...]
) -> None:
    json_path = "{" + ",".join(path) + "}"
    decision = f"({alias}.{column} #> '{json_path}')"
    downgraded = (
        f"(({decision} - 'action_plan') || "
        "jsonb_build_object('schema_version', 'simulated-decision.v1'))"
    )
    op.execute(
        f"UPDATE {table} AS {alias} "
        f"SET {column} = jsonb_set({alias}.{column}, '{json_path}', {downgraded}, false) "
        f"WHERE {decision} ->> 'schema_version' = 'simulated-decision.v2'"
    )


def upgrade() -> None:
    simulation_step = (
        "COALESCE((SELECT state.current_step FROM observable.simulation_states state "
        "WHERE state.case_id = decision_row.case_id), 0)"
    )
    _upgrade_decision(
        table="observable.simulated_decisions",
        alias="decision_row",
        column="payload",
        path=("decision",),
        current_step=simulation_step,
    )
    run_step = (
        "COALESCE((SELECT state.current_step FROM observable.simulation_states state "
        "JOIN observable.agent_runs run ON run.case_id = state.case_id "
        "WHERE run.run_id = run_step.run_id), 0)"
    )
    _upgrade_decision(
        table="observable.agent_run_steps",
        alias="run_step",
        column="normalized_output",
        path=("decision",),
        current_step=run_step,
        extra_where="run_step.step_kind = 'chair'",
    )
    run_result_step = (
        "COALESCE((SELECT state.current_step FROM observable.simulation_states state "
        "WHERE state.case_id = run_result.case_id), 0)"
    )
    _upgrade_decision(
        table="observable.agent_runs",
        alias="run_result",
        column="result",
        path=("chair_provider_result", "decision"),
        current_step=run_result_step,
        extra_where="run_result.result IS NOT NULL",
    )
    evaluation_step = (
        "COALESCE((SELECT state.current_step FROM observable.simulation_states state "
        "WHERE state.case_id = evaluation_row.case_id), 0)"
    )
    _upgrade_decision(
        table="hidden.outcome_evaluations",
        alias="evaluation_row",
        column="payload",
        path=("ablation", "decision"),
        current_step=evaluation_step,
    )
    op.execute(
        "UPDATE hidden.outcome_evaluations AS evaluation_row "
        "SET payload = jsonb_set(payload, "
        "'{process_evaluation,decision_action_complete}', 'true'::jsonb, true) "
        "WHERE payload #> '{process_evaluation}' IS NOT NULL "
        "AND NOT (payload #> '{process_evaluation}' ? 'decision_action_complete')"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE hidden.outcome_evaluations AS evaluation_row "
        "SET payload = payload #- '{process_evaluation,decision_action_complete}' "
        "WHERE payload #> '{process_evaluation}' ? 'decision_action_complete'"
    )
    _downgrade_decision(
        table="hidden.outcome_evaluations",
        alias="evaluation_row",
        column="payload",
        path=("ablation", "decision"),
    )
    _downgrade_decision(
        table="observable.agent_runs",
        alias="run_result",
        column="result",
        path=("chair_provider_result", "decision"),
    )
    _downgrade_decision(
        table="observable.agent_run_steps",
        alias="run_step",
        column="normalized_output",
        path=("decision",),
    )
    _downgrade_decision(
        table="observable.simulated_decisions",
        alias="decision_row",
        column="payload",
        path=("decision",),
    )
