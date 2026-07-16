import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";

import {
  advanceOutcome,
  cancelReviewRun,
  createDossierRun,
  createReviewRun,
  createSimulatedDecision,
  evaluateOutcome,
  getDecisionTimeline,
  getDecisionWorkspace,
  getReviewRun,
  isCaseVersionConflict,
  retryReviewRun,
} from "../../api/client";
import type { DecisionWorkspace, DevelopmentTimeline } from "../../api/generated";

export function DecisionWorkspacePage() {
  const { caseId = "" } = useParams();
  const [selectedStep, setSelectedStep] = useState<number | undefined>();
  const [runId, setRunId] = useState<string | null>(null);
  const [dossierRunId, setDossierRunId] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["decision-workspace", caseId, selectedStep ?? "current"],
    queryFn: () => getDecisionWorkspace(caseId, selectedStep),
    enabled: Boolean(caseId),
  });
  const timelineQuery = useQuery({
    queryKey: ["development-timeline", caseId, selectedStep ?? "current"],
    queryFn: () => getDecisionTimeline(caseId, selectedStep),
    enabled: Boolean(caseId),
  });
  const runQuery = useQuery({
    queryKey: ["review-run", runId],
    queryFn: () => getReviewRun(runId ?? ""),
    enabled: Boolean(runId),
    refetchInterval: (current) => {
      const status = current.state.data?.status;
      return status && ["PARTIALLY_COMPLETED", "COMPLETED", "FAILED", "CANCELLED"].includes(status)
        ? false
        : 1000;
    },
  });
  const startReview = useMutation({
    mutationFn: () => createReviewRun(caseId, query.data?.aggregate_version ?? 0),
    onSuccess: (run) => setRunId(run.run_id),
  });
  const cancelReview = useMutation({
    mutationFn: (id: string) => cancelReviewRun(id, query.data?.aggregate_version ?? 0),
  });
  const retryReview = useMutation({
    mutationFn: (id: string) => retryReviewRun(id, query.data?.aggregate_version ?? 0),
    onSuccess: (run) => setRunId(run.run_id),
  });
  const dossierRunQuery = useQuery({
    queryKey: ["dossier-run", dossierRunId],
    queryFn: () => getReviewRun(dossierRunId ?? ""),
    enabled: Boolean(dossierRunId),
    refetchInterval: (current) => {
      const status = current.state.data?.status;
      return status && ["PARTIALLY_COMPLETED", "COMPLETED", "FAILED", "CANCELLED"].includes(status)
        ? false
        : 1000;
    },
  });
  const dossierStartMutation = useMutation({
    mutationFn: () => createDossierRun(caseId, query.data?.aggregate_version ?? 0),
    onSuccess: (run) => setDossierRunId(run.run_id),
  });
  const retryDossier = useMutation({
    mutationFn: (id: string) => retryReviewRun(id, query.data?.aggregate_version ?? 0),
    onSuccess: (run) => setDossierRunId(run.run_id),
  });
  const decisionMutation = useMutation({
    mutationFn: () => {
      if (!dossierRunId) throw new Error("먼저 다중 역할 검토를 완료하세요.");
      return createSimulatedDecision(
        caseId,
        query.data?.aggregate_version ?? 0,
        dossierRunId,
      );
    },
  });
  const outcomeMutation = useMutation({
    mutationFn: () => {
      if (!decisionMutation.data) throw new Error("먼저 모의 결정을 실행하세요.");
      const fromStep = query.data?.time_context.current_step ?? 0;
      return advanceOutcome(
        caseId,
        query.data?.aggregate_version ?? 0,
        decisionMutation.data.decision,
        fromStep,
        Math.max(fromStep + 1, 15),
      );
    },
    onSuccess: () => {
      void Promise.all([query.refetch(), timelineQuery.refetch()]);
    },
  });
  const evaluationMutation = useMutation({
    mutationFn: () => evaluateOutcome(caseId, query.data?.aggregate_version ?? 0),
  });
  const commandMutations = [
    startReview,
    cancelReview,
    retryReview,
    dossierStartMutation,
    retryDossier,
    decisionMutation,
    outcomeMutation,
    evaluationMutation,
  ];
  const stale = commandMutations.some((mutation) => isCaseVersionConflict(mutation.error));
  const refreshStaleWorkspace = async () => {
    setSelectedStep(undefined);
    await Promise.all([query.refetch(), timelineQuery.refetch()]);
    commandMutations.forEach((mutation) => mutation.reset());
  };

  if (query.isPending) {
    return (
      <main className="app-shell workspace-shell">
        <p role="status">선택한 Step의 검토 정보를 불러오는 중…</p>
      </main>
    );
  }
  if (query.isError) {
    return (
      <main className="app-shell workspace-shell">
        <section className="list-feedback" role="alert">
          <h1>결정 검토를 불러오지 못했습니다</h1>
          <p>{query.error.message}</p>
          <button className="primary-button" type="button" onClick={() => void query.refetch()}>
            다시 시도
          </button>
        </section>
      </main>
    );
  }
  if (!query.data) return null;

  const item = query.data;
  const commandsAllowed = item.time_context.commands_allowed_at_selected_step && !stale;
  const dossierResult = dossierRunQuery.data?.result;
  const dossierFailures = dossierResult && "failed_roles" in dossierResult
    ? dossierResult.failed_roles ?? []
    : [];
  const completedDossierRoles = dossierResult && "dossier" in dossierResult
    ? dossierResult.dossier.original_reviews.map((review) => review.role_id)
    : [];
  const primaryAction = item.workflow.primary_action;
  const runPrimaryAction = () => {
    if (primaryAction === "RUN_VIRTUAL_REVIEW" && !runId) {
      startReview.mutate();
      return;
    }
    const target = actionTarget(primaryAction);
    document.getElementById(target)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <main className="app-shell workspace-shell">
      <ContextBar item={item} />

      <DecisionBrief
        item={item}
        commandsAllowed={commandsAllowed}
        primaryActionLabel={
          primaryAction === "RUN_VIRTUAL_REVIEW" && runId
            ? "검토 진행 상태 보기"
            : workspaceActionLabel(primaryAction)
        }
        primaryActionPending={startReview.isPending}
        onPrimaryAction={runPrimaryAction}
      />

      {stale ? (
        <section className="panel stale-panel" role="alert">
          <h2>개발 상태가 변경되었습니다</h2>
          <p>현재 화면의 판단 기준이 이전 version입니다. 최신 상태를 확인한 뒤 다시 실행하세요.</p>
          <button
            className="primary-button"
            type="button"
            onClick={() => void refreshStaleWorkspace()}
            disabled={query.isFetching}
          >
            {query.isFetching ? "최신 상태 확인 중…" : "최신 상태 불러오기"}
          </button>
        </section>
      ) : null}

      <DevelopmentTwin
        item={item}
        timeline={timelineQuery.data}
        timelinePending={timelineQuery.isPending}
        timelineError={timelineQuery.isError}
        onSelectStep={(step) => {
          setSelectedStep(step === item.time_context.current_step ? undefined : step);
        }}
      />

      <DecisionPosture item={item} />

      <section className="panel agent-panel" id="alternatives" aria-labelledby="alternatives-title">
        <p className="section-kicker">선택지</p>
        <h2 id="alternatives-title">선택지와 되돌릴 수 있는 정도</h2>
        <div className="option-grid">
          {item.alternatives.items.map((option) => (
            <article className="option-card" key={option.option_id}>
              <p className="status-chip">{option.reversible ? "되돌릴 수 있음" : "되돌리기 어려움"}</p>
              <h3>{option.title}</h3>
              <p>{option.description}</p>
              <p className="muted-copy">전환 비용: {quantityLabel(option.switching_cost)}</p>
            </article>
          ))}
        </div>
        <h3>아직 확인할 것</h3>
        {item.deliberation.key_unknowns_ko.length > 0 ? (
          <ul>
            {item.deliberation.key_unknowns_ko.map((unknown) => <li key={unknown}>{unknown}</li>)}
          </ul>
        ) : (
          <p>현재 등록된 미확인 항목 없음</p>
        )}
      </section>

      <section className="panel agent-panel" id="agent-review" aria-labelledby="agent-review-title">
        <p className="section-kicker">가상 조언</p>
        <h2 id="agent-review-title">역할 기반 검토</h2>
        <p>현재 개발 진행, 근거와 불확실성을 함께 보고 위험을 줄이는 선택을 조언합니다.</p>
        {!runId ? (
          <button
            className="primary-button"
            type="button"
            onClick={() => startReview.mutate()}
            disabled={startReview.isPending || !commandsAllowed}
          >
            {startReview.isPending ? "검토 요청 중…" : "역할 검토 시작"}
          </button>
        ) : null}
        {startReview.isError ? <p role="alert">{startReview.error.message}</p> : null}
        {runQuery.data ? (
          <div className="run-progress" aria-live="polite">
            <p><strong>진행 상태:</strong> {runStatusLabel(runQuery.data.status)} · 시도 {runQuery.data.attempt_no}/{runQuery.data.max_attempts}</p>
            <p><strong>실행 한도:</strong> logical {runQuery.data.budget_plan.reserved_logical_calls}/{runQuery.data.budget_plan.max_logical_calls} · provider 시도 {runQuery.data.budget_plan.reserved_provider_attempts}/{runQuery.data.budget_plan.max_provider_attempts} · 최대 ${runQuery.data.budget_plan.maximum_cost_usd.toFixed(2)}</p>
            {["QUEUED", "RUNNING"].includes(runQuery.data.status) ? (
              <button className="secondary-button" type="button" onClick={() => cancelReview.mutate(runQuery.data.run_id)} disabled={!commandsAllowed}>취소</button>
            ) : null}
            {runQuery.data.error_code ? <p role="alert">실패 원인: {runQuery.data.error_code}</p> : null}
            {["FAILED", "CANCELLED", "PARTIALLY_COMPLETED"].includes(runQuery.data.status) ? (
              <button className="primary-button" type="button" onClick={() => retryReview.mutate(runQuery.data.run_id)} disabled={retryReview.isPending || !commandsAllowed}>{retryReview.isPending ? "재시도 요청 중…" : "검토 재시도"}</button>
            ) : null}
            {runQuery.data.result && "review" in runQuery.data.result ? (
              <article className="review-card">
                <p className="eyebrow">{roleLabel(runQuery.data.result.review.role_id)}</p>
                <h3>{runQuery.data.result.review.recommendation}</h3>
                <p>{runQuery.data.result.review.rationale}</p>
                <p><strong>확신 수준:</strong> {runQuery.data.result.review.confidence}</p>
              </article>
            ) : null}
          </div>
        ) : null}
        {runQuery.isError ? <p role="alert">진행 상태를 확인하지 못했습니다. 잠시 후 다시 시도하세요.</p> : null}
      </section>

      <section className="panel agent-panel" id="dossier" aria-labelledby="dossier-title">
        <h2 id="dossier-title">다중 역할 판단과 모의 결정</h2>
        <p>역할별 독립 검토와 반론을 거친 뒤, 실제 승인이 아닌 모의 Chair 결정을 만듭니다.</p>
        {!dossierRunId ? (
          <button className="primary-button" type="button" onClick={() => dossierStartMutation.mutate()} disabled={dossierStartMutation.isPending || !commandsAllowed}>
            {dossierStartMutation.isPending ? "검토 요청 중…" : "다중 역할 검토 시작"}
          </button>
        ) : null}
        {dossierRunQuery.data ? (
          <div aria-live="polite">
            <p><strong>다중 역할 진행:</strong> {runStatusLabel(dossierRunQuery.data.status)}</p>
            <p><strong>실행 한도:</strong> logical {dossierRunQuery.data.budget_plan.reserved_logical_calls}/{dossierRunQuery.data.budget_plan.max_logical_calls} · provider 시도 {dossierRunQuery.data.budget_plan.reserved_provider_attempts}/{dossierRunQuery.data.budget_plan.max_provider_attempts} · output {dossierRunQuery.data.budget_plan.reserved_output_tokens}/{dossierRunQuery.data.budget_plan.max_output_tokens} tokens · 최대 ${dossierRunQuery.data.budget_plan.maximum_cost_usd.toFixed(2)}</p>
            {dossierFailures.length > 0 ? (
              <>
                <p><strong>완료:</strong> {completedDossierRoles.map(roleLabel).join(", ")}</p>
                <p><strong>실패:</strong> {dossierFailures.map((failure) => `${roleLabel(failure.role_id)} (${failure.error_code})`).join(", ")}</p>
              </>
            ) : null}
            {dossierRunQuery.data.error_code ? <p role="alert">필수 역할 검토 실패: {dossierRunQuery.data.error_code}. 이 상태에서는 Chair 결정을 만들 수 없습니다.</p> : null}
            {["FAILED", "CANCELLED", "PARTIALLY_COMPLETED"].includes(dossierRunQuery.data.status) ? (
              <button className="primary-button" type="button" onClick={() => retryDossier.mutate(dossierRunQuery.data.run_id)} disabled={retryDossier.isPending || !commandsAllowed}>{retryDossier.isPending ? "재시도 요청 중…" : "다중 검토 재시도"}</button>
            ) : null}
          </div>
        ) : null}
        {dossierRunQuery.data?.status === "COMPLETED" && !decisionMutation.data ? (
          <button className="primary-button" type="button" onClick={() => decisionMutation.mutate()} disabled={decisionMutation.isPending || !commandsAllowed}>{decisionMutation.isPending ? "Chair 판단 중…" : "모의 Chair 결정"}</button>
        ) : null}
        {decisionMutation.isError ? <p role="alert">모의 결정을 만들지 못했습니다. 다시 시도하세요.</p> : null}
        {decisionMutation.data ? (
          <div className="decision-result">
            <p className="status-chip">모의 결정 · {decisionMutation.data.topology}</p>
            <h3>{decisionMutation.data.decision.decision_type}</h3>
            <p>{decisionMutation.data.decision.rationale}</p>
            <h3>다음 행동</h3>
            <article className="safeguard-card">
              <p><strong>담당:</strong> {roleLabel(decisionMutation.data.decision.action_plan.owner)}</p>
              <p><strong>할 일:</strong> {decisionMutation.data.decision.action_plan.action}</p>
              <p><strong>기한:</strong> Step {decisionMutation.data.decision.action_plan.due_at_step}</p>
              <p><strong>시작 조건:</strong> {decisionMutation.data.decision.action_plan.trigger}</p>
              <p><strong>확인 방법:</strong> {decisionMutation.data.decision.action_plan.verification}</p>
              <p><strong>실패 시:</strong> {decisionMutation.data.decision.action_plan.fallback_action}</p>
            </article>
            <h3>합의</h3>
            <ul>{decisionMutation.data.dossier.agreement_groups.map((group) => <li key={group.recommendation}>{group.recommendation}: {group.role_ids.map(roleLabel).join(", ")}</li>)}</ul>
            <h3>반대 의견</h3>
            {decisionMutation.data.dossier.dissent.length === 0 ? <p>기록된 반대 의견 없음</p> : <ul>{decisionMutation.data.dossier.dissent.map((entry) => <li key={entry.role_id}><strong>{roleLabel(entry.role_id)}</strong>: {entry.recommendation} — {entry.rationale}</li>)}</ul>}
            <h3>안전장치</h3>
            {decisionMutation.data.decision.safeguards.map((guard) => (
              <article className="safeguard-card" key={guard.safeguard_id}>
                <p><strong>측정 기준:</strong> {guard.metric_id} {guard.operator} {guard.threshold.value} {guard.threshold.unit} · Step {guard.check_at_step}</p>
                <p><strong>적용 조건:</strong> {guard.condition}</p>
                <p><strong>중단·복구 기준:</strong> {guard.rollback_trigger}</p>
                <p><strong>실행 조치:</strong> {guard.violation_action} · Step {guard.expires_at_step} 재검토</p>
                <p><strong>담당:</strong> {roleLabel(guard.owner)}</p>
              </article>
            ))}
            <h3>남은 불확실성</h3>
            <ul>{decisionMutation.data.dossier.unresolved_uncertainties.map((entry) => <li key={entry}>{entry}</li>)}</ul>
          </div>
        ) : null}
      </section>

      <section className="panel agent-panel" id="outcome" aria-labelledby="outcome-title">
        <h2 id="outcome-title">결과와 판단 품질 확인</h2>
        <p>모의 시간을 진행해 숨겨진 결과를 공개하고, 판단 과정과 실제 결과를 분리해 평가합니다.</p>
        {!outcomeMutation.data ? (
          <button className="primary-button" type="button" onClick={() => outcomeMutation.mutate()} disabled={outcomeMutation.isPending || !decisionMutation.data || !commandsAllowed}>{outcomeMutation.isPending ? "결과 계산 중…" : "다음 Step 진행"}</button>
        ) : null}
        {outcomeMutation.isError ? <p role="alert">결과 평가를 완료하지 못했습니다.</p> : null}
        {outcomeMutation.data ? (
          <div className="decision-result">
            <p className="status-chip">Step {outcomeMutation.data.current_step} · {outcomeMutation.data.guardrail_state}</p>
            <h3>공개된 결과</h3>
            <ul>{[...outcomeMutation.data.revealed_evidence, ...outcomeMutation.data.consequences].map((entry) => <li key={entry}>{entry}</li>)}</ul>
            {outcomeMutation.data.executed_actions.length > 0 ? <p><strong>실행된 보호 조치:</strong> {outcomeMutation.data.executed_actions.join(", ")}</p> : null}
            {!evaluationMutation.data ? (
              <button className="primary-button" type="button" onClick={() => evaluationMutation.mutate()} disabled={evaluationMutation.isPending || !commandsAllowed}>{evaluationMutation.isPending ? "평가 중…" : "판단 품질 평가"}</button>
            ) : null}
            {evaluationMutation.data ? (
              <>
                <h3>과정 평가</h3><p>{evaluationMutation.data.process_evaluation.passed ? "필수 근거·의존성·안전장치를 충족했습니다." : "판단 과정의 필수 항목이 부족합니다."}</p>
                <h3>결과 평가</h3><p>{evaluationMutation.data.outcome_evaluation.passed ? "위험 신호에 보호 조치가 실행되었습니다." : "위험 통제에 실패했습니다."}</p>
                <p className="explanation"><strong>왜 과정과 결과가 다를 수 있나요?</strong> 당시 이용할 수 있는 근거로 합리적으로 판단했어도 숨겨진 원인 때문에 결과가 나쁠 수 있고, 반대로 근거가 빈약한 판단이 우연히 좋은 결과를 낼 수도 있기 때문입니다.</p>
              </>
            ) : null}
          </div>
        ) : null}
      </section>
    </main>
  );
}

function ContextBar({ item }: { item: DecisionWorkspace }) {
  const isHistorical = item.time_context.mode === "historical";
  return (
    <nav className="decision-context-bar" aria-label="결정 검토 문맥">
      <Link className="back-link" to="/decisions">← 결정 목록</Link>
      <div className="context-facts">
        <span>가상 판단</span>
        <span>{isHistorical ? `과거 Step ${item.time_context.selected_step}` : `현재 Step ${item.time_context.current_step}`}</span>
        <span>{isHistorical ? "당시 관측 상태" : "최신 상태"}</span>
        <span>{phaseLabel(item.header.workspace_phase)}</span>
      </div>
    </nav>
  );
}

function DecisionBrief({
  item,
  commandsAllowed,
  primaryActionLabel,
  primaryActionPending,
  onPrimaryAction,
}: {
  item: DecisionWorkspace;
  commandsAllowed: boolean;
  primaryActionLabel: string;
  primaryActionPending: boolean;
  onPrimaryAction: () => void;
}) {
  return (
    <header className="decision-brief">
      <div className="brief-main">
        <p className="section-kicker">{item.header.title_ko}</p>
        <h1>{item.header.decision_question}</h1>
        <p className="brief-state">{item.current_brief.state_or_recommendation_ko}</p>
        <p className="brief-reason">{item.current_brief.one_line_reason_ko}</p>
      </div>
      <aside className="brief-action" aria-label="현재 할 일">
        <p className="brief-action-label">지금 할 일</p>
        <p className="deadline-copy">Step {item.header.deadline.at_step} · {item.header.deadline.title}</p>
        <p>{deadlineLabel(item.header.deadline.remaining_steps)}</p>
        {item.workflow.primary_action ? (
          <button className="primary-button brief-primary-action" type="button" onClick={onPrimaryAction} disabled={!commandsAllowed || primaryActionPending}>
            {primaryActionPending ? "검토 요청 중…" : primaryActionLabel}
          </button>
        ) : (
          <p className="historical-notice">과거 Step에서는 실행할 수 없습니다.</p>
        )}
      </aside>
      <div className="why-now workspace-why-now">
        <p className="why-now-label">왜 지금</p>
        <p>{item.current_brief.why_now_ko}</p>
      </div>
    </header>
  );
}

function DevelopmentTwin({
  item,
  timeline,
  timelinePending,
  timelineError,
  onSelectStep,
}: {
  item: DecisionWorkspace;
  timeline: DevelopmentTimeline | undefined;
  timelinePending: boolean;
  timelineError: boolean;
  onSelectStep: (step: number) => void;
}) {
  const time = item.time_context;
  const steps = Array.from(
    { length: time.latest_observable_step - time.earliest_available_step + 1 },
    (_, index) => time.earliest_available_step + index,
  );
  return (
    <section className="development-twin" aria-labelledby="development-twin-title">
      <header className="twin-header">
        <div>
          <p className="section-kicker">Development Twin</p>
          <h2 id="development-twin-title">선택한 시점의 개발 상태와 변화 원인</h2>
          <p>{time.mode === "historical" ? "이후에 알려진 검토·판단·결과를 제외한 당시 관측 상태입니다." : "현재 결정과 직접 연결된 상태·원인·선택 영향을 보여줍니다."}</p>
        </div>
        <label className="step-selector">
          관찰 시점
          <select value={time.selected_step} onChange={(event) => onSelectStep(Number(event.target.value))}>
            {steps.map((step) => <option value={step} key={step}>{step === time.current_step ? `현재 Step ${step}` : `Step ${step}`}</option>)}
          </select>
        </label>
      </header>

      <div className="twin-summary-grid">
        <section className="twin-card twin-state" aria-labelledby="track-state-title">
          <h3 id="track-state-title">Step {time.selected_step} 개발 상태</h3>
          <div className="track-state-list">
            {item.development_twin.state_at_selected_step.tracks.map((track) => (
              <article className="track-state-card" key={track.track_id}>
                <div className="track-state-heading">
                  <strong>{track.name}</strong>
                  <span className="state-label">{workStatusLabel(track.status)}</span>
                </div>
                <p>{track.current_work_item_title}</p>
                <dl>
                  <div><dt>담당</dt><dd>{roleLabel(track.owner)}</dd></div>
                  <div><dt>대기 원인</dt><dd>{track.blocker ?? "없음"}</dd></div>
                  <div><dt>다음 기준점</dt><dd>{track.next_milestone_title ? `${track.next_milestone_title} · Step ${track.next_milestone_step}` : "등록 없음"}</dd></div>
                </dl>
              </article>
            ))}
          </div>
        </section>

        <section className="twin-card" aria-labelledby="commitment-title">
          <h3 id="commitment-title">가장 가까운 Commitment Window</h3>
          {item.development_twin.commitment_windows.length > 0 ? (
            item.development_twin.commitment_windows.slice(0, 3).map((window) => (
              <article className="commitment-card" key={`${window.subject_type}-${window.subject_id}`}>
                <p className="state-label">{window.closes_at_step !== null && window.closes_at_step !== undefined ? `Step ${window.closes_at_step} 종료` : "Milestone에서 종료"}</p>
                <h4>{window.subject_title}</h4>
                <p>{window.closing_reason_ko}</p>
                <p><strong>닫힌 뒤:</strong> {window.post_window_impact_ko}</p>
                <p><strong>전환 비용:</strong> {window.switching_cost ? quantityLabel(window.switching_cost) : "정량화되지 않음"}</p>
              </article>
            ))
          ) : (
            <p className="empty-copy">이 Step에서 확인 가능한 commitment window가 없습니다.</p>
          )}
        </section>
      </div>

      <section className="twin-card causal-panel" aria-labelledby="causal-title">
        <h3 id="causal-title">무엇이 바뀌었고 어디까지 영향을 주는가</h3>
        {(item.development_twin.blocker_impacts ?? []).length > 0 ? (
          <div className="blocker-impact-list">
            {(item.development_twin.blocker_impacts ?? []).map((impact) => (
              <article key={`${impact.source_work_item_title}-${impact.blocker_ko}`}>
                <p className="knowledge-label inferred">현재 blocker 전파</p>
                <h4>{impact.source_work_item_title}</h4>
                <p><strong>대기 원인:</strong> {impact.blocker_ko}</p>
                <p><strong>영향 작업:</strong> {(impact.downstream_work_item_titles ?? []).length > 0 ? (impact.downstream_work_item_titles ?? []).join(", ") : "직접 후속 작업 없음"}</p>
                <p><strong>영향 기준점:</strong> {(impact.impacted_milestone_titles ?? []).length > 0 ? (impact.impacted_milestone_titles ?? []).join(", ") : "확인된 영향 없음"}{impact.reaches_decision_deadline ? " · 결정 기한 영향" : ""}</p>
              </article>
            ))}
          </div>
        ) : null}
        {item.development_twin.causal_chains.length > 0 ? (
          <ol className="causal-list">
            {item.development_twin.causal_chains.map((chain) => (
              <li key={chain.source_event_id}>
                <p className="causal-step">Step {chain.observed_at_step}</p>
                <h4>{chain.title_ko}</h4>
                {chain.links.map((link, index) => (
                  <p key={`${chain.source_event_id}-${index}`}>
                    <span className={`knowledge-label ${link.relation_kind}`}>{link.relation_kind === "observed" ? "관측" : "근거 기반 추론"}</span>
                    {link.statement_ko}
                  </p>
                ))}
              </li>
            ))}
          </ol>
        ) : (
          <p className="empty-copy">현재 전파는 계산할 수 있지만 원인이 된 관측 event는 아직 기록되지 않았습니다.</p>
        )}
      </section>

      <section className="transition-section" aria-labelledby="expected-transition-title">
        <div className="transition-heading">
          <div>
            <p className="section-kicker">선택 영향</p>
            <h3 id="expected-transition-title">선택지별 예상 상태 변화</h3>
          </div>
          <p>관측 결과가 아니라 observable model에 근거한 예상입니다.</p>
        </div>
        <div className="transition-grid">
          {item.expected_option_transitions.map((transition) => (
            <article className="transition-card expected" key={transition.option_id}>
              <p className="knowledge-label expected">예상</p>
              <h4>{transition.option_title}</h4>
              {transition.state_changes.length > 0 ? (
                <ul className="state-change-list">
                  {transition.state_changes.map((change) => <li key={`${change.entity_type}-${change.entity_id}`}>{change.entity_title}: {change.from_state} → {change.to_state}</li>)}
                </ul>
              ) : (
                <p>검증된 상태 변화 모델 없음</p>
              )}
              {(transition.preserved_options_ko ?? []).length > 0 ? <p><strong>유지:</strong> {(transition.preserved_options_ko ?? []).join(", ")}</p> : null}
              {(transition.lost_options_ko ?? []).length > 0 ? <p><strong>잃는 선택:</strong> {(transition.lost_options_ko ?? []).join(", ")}</p> : null}
              {(transition.unknown_impacts_ko ?? []).length > 0 ? <p className="unknown-copy"><strong>아직 모름:</strong> {(transition.unknown_impacts_ko ?? []).join(", ")}</p> : null}
            </article>
          ))}
          <article className="transition-card observed">
            <p className="knowledge-label observed">관측</p>
            <h4>결정 이후 실제 상태 변화</h4>
            {item.observed_decision_transitions.available ? (
              <ul className="state-change-list">{(item.observed_decision_transitions.state_changes ?? []).map((change) => <li key={`${change.entity_type}-${change.entity_id}`}>{change.entity_title}: {change.from_state} → {change.to_state}</li>)}</ul>
            ) : (
              <p>아직 결정 이후 event로 확인된 변화가 없습니다.</p>
            )}
          </article>
        </div>
      </section>

      <details className="timeline-details">
        <summary>개발 진행 전체 보기</summary>
        {timelinePending ? <p role="status">개발 변경 이력을 불러오는 중…</p> : null}
        {timelineError ? <p role="alert">개발 변경 이력을 불러오지 못했습니다.</p> : null}
        {timeline && timeline.events.length === 0 ? <p>기록된 개발 변경 없음</p> : null}
        {timeline && timeline.events.length > 0 ? (
          <ol className="timeline-list">{timeline.events.map((event) => <li key={event.event_id}><strong>Step {event.observed_at_step} · {developmentEventLabel(event.event_type)}</strong><p>{event.summary}</p><p><strong>원인:</strong> {event.cause}</p></li>)}</ol>
        ) : null}
      </details>
    </section>
  );
}

function DecisionPosture({ item }: { item: DecisionWorkspace }) {
  const posture = item.decision_posture;
  const dimensions = [
    ["근거", posture.evidence_state],
    ["가역성", posture.reversibility],
    ["관측 가능성", posture.detectability],
    ["복구 가능성", posture.recoverability],
    ["실패 영향", posture.downside],
    ["영향 범위", posture.blast_radius],
    ["긴급도", posture.urgency],
  ];
  return (
    <section className="panel posture-panel" aria-labelledby="posture-title">
      <p className="section-kicker">Decision Posture</p>
      <h2 id="posture-title">데이터가 완전하지 않아도 판단할 수 있는 정도</h2>
      <div className="posture-grid">{dimensions.map(([label, value]) => <div key={label}><span>{label}</span><strong>{postureLabel(value)}</strong></div>)}</div>
      <ul>{posture.explanations_ko.map((entry) => <li key={entry}>{entry}</li>)}</ul>
    </section>
  );
}

function actionTarget(action: DecisionWorkspace["workflow"]["primary_action"]) {
  if (action === "VIEW_DOSSIER" || action === "RUN_SIMULATED_DECISION") return "dossier";
  if (action === "ADVANCE_SIMULATION" || action === "VIEW_EVALUATION" || action === "VIEW_LEARNING_SUMMARY") return "outcome";
  return "agent-review";
}

function workspaceActionLabel(action: DecisionWorkspace["workflow"]["primary_action"]) {
  if (!action) return "실행할 작업 없음";
  return ({
    BUILD_CONTEXT: "상황 구성",
    RUN_VIRTUAL_REVIEW: "가상 역할 검토 실행",
    VIEW_REVIEW_PROGRESS: "진행 상태 보기",
    VIEW_DOSSIER: "의견 종합 보기",
    RUN_SIMULATED_DECISION: "가상 최종 판단 실행",
    ADVANCE_SIMULATION: "다음 Simulation Step 진행",
    VIEW_EVALUATION: "판단 평가 보기",
    VIEW_LEARNING_SUMMARY: "학습 요약 보기",
    REFRESH_STALE: "최신 상태 불러오기",
  } as const)[action];
}

function phaseLabel(phase: DecisionWorkspace["header"]["workspace_phase"]) {
  if (!phase) return "과거 상태 보기";
  return ({
    CONTEXT_PREPARATION: "상황 구성 중",
    READY_FOR_REVIEW: "가상 검토 준비",
    REVIEW_RUNNING: "가상 검토 중",
    DOSSIER_READY: "의견 종합 준비",
    DECISION_REQUIRED: "가상 판단 필요",
    OUTCOME_RUNNING: "실행·관찰 중",
    EVALUATION_READY: "평가 확인 가능",
    CLOSED: "종료",
  } as const)[phase];
}

function deadlineLabel(remaining: number) {
  if (remaining < 0) return `기한이 ${Math.abs(remaining)} Step 지났습니다.`;
  if (remaining === 0) return "현재 Step에서 결정해야 합니다.";
  return `${remaining} Step 남았습니다.`;
}

function quantityLabel(quantity: DecisionWorkspace["alternatives"]["items"][number]["switching_cost"]) {
  if (quantity.mode === "exact") return `${quantity.value} ${quantity.unit}`;
  if (quantity.mode === "range") return `${quantity.lower_bound}–${quantity.upper_bound} ${quantity.unit}`;
  if (quantity.mode === "qualitative") return `${postureLabel(quantity.qualitative)} 수준`;
  return "아직 정량화되지 않음";
}

function roleLabel(roleId: string) {
  return ({
    "ROLE-ARCH": "Architecture",
    "ROLE-HW": "HW/RTL",
    "ROLE-SW": "SW/FW/HAL",
    "ROLE-VERIF": "Verification/Measurement",
    "ROLE-PM": "Technical PM",
  } as Record<string, string>)[roleId] ?? roleId.replace(/^ROLE-/, "");
}

function workStatusLabel(status: string) {
  return ({
    PLANNED: "계획됨",
    READY: "시작 가능",
    IN_PROGRESS: "진행 중",
    BLOCKED: "대기 중",
    DONE: "완료",
    VERIFIED: "검증 완료",
    REWORK: "재작업",
    CANCELLED: "취소됨",
  } as Record<string, string>)[status] ?? status;
}

function postureLabel(value: string | null | undefined) {
  if (!value) return "아직 모름";
  return ({
    sufficient: "충분",
    partial: "일부 확보",
    insufficient: "부족",
    high: "높음",
    medium: "중간",
    low: "낮음",
    critical: "치명적",
    observable_now: "지금 관측 가능",
    observable_later: "나중에 관측 가능",
    limited: "제한적",
    cross_track: "여러 Track",
    milestone: "Milestone",
    project: "과제 전체",
    expired: "기한 경과",
    unknown: "아직 모름",
  } as Record<string, string>)[value] ?? value;
}

function runStatusLabel(status: string) {
  return ({ QUEUED: "대기 중", RUNNING: "검토 중", PARTIALLY_COMPLETED: "일부 완료", COMPLETED: "완료", FAILED: "실패", CANCELLED: "취소됨" } as Record<string, string>)[status] ?? status;
}

function developmentEventLabel(eventType: string) {
  return ({
    WORK_PROGRESS: "작업 진행",
    BLOCKER_CHANGE: "Blocker 변경",
    PLAN_CHANGE: "계획 변경",
    DEPENDENCY_CHANGE: "의존성 변경",
    EVIDENCE_CHANGE: "측정·근거 변경",
    REWORK: "재작업",
    INTERFACE_CHANGE: "인터페이스 변경",
    RESOURCE_CONFLICT: "자원 충돌",
    PRIORITY_CHANGE: "우선순위 변경",
    DECISION_ACTION_PROGRESS: "결정 후속 조치",
  } as Record<string, string>)[eventType] ?? eventType;
}
