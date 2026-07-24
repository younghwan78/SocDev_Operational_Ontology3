import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import {
  ApiError,
  advanceOutcome,
  cancelReviewRun,
  createDossierRun,
  createSimulatedDecision,
  evaluateOutcome,
  getDecisionEvaluationResponse,
  getDecisionTimeline,
  getDecisionWorkspace,
  getReviewRun,
  isCaseVersionConflict,
  recordFinalDecisionResponse,
  recordInitialDecisionResponse,
  revealDecisionAdvice,
  retryReviewRun,
} from "../../api/client";
import type { DecisionWorkspace, DevelopmentTimeline } from "../../api/generated";
import { AlternativeComparison } from "./AlternativeComparison";
import { DecisionDeliberation } from "./DecisionDeliberation";
import { DecisionEvaluationResponse } from "./DecisionEvaluationResponse";
import { DecisionExecution } from "./DecisionExecution";

export function DecisionWorkspacePage() {
  const { caseId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedStep = parseSearchStep(searchParams.get("at_step"));
  const selectedOptionPosition = parseSearchPosition(searchParams.get("option"));
  const evaluationMode = searchParams.get("interaction") === "evaluation";
  const riskReturn = parseRiskReturn(searchParams);
  const [dossierRunId, setDossierRunId] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["decision-workspace", caseId, selectedStep ?? "current"],
    queryFn: () => getDecisionWorkspace(caseId, selectedStep),
    enabled: Boolean(caseId),
  });
  const activeDossierRunId = dossierRunId ?? query.data?.workflow.dossier_run_id ?? null;
  const timelineQuery = useQuery({
    queryKey: ["development-timeline", caseId, selectedStep ?? "current"],
    queryFn: () => getDecisionTimeline(caseId, selectedStep),
    enabled: Boolean(caseId),
  });
  const evaluationResponseQuery = useQuery({
    queryKey: ["decision-evaluation-response", caseId],
    queryFn: () => getDecisionEvaluationResponse(caseId),
    enabled: Boolean(caseId) && evaluationMode && selectedStep === undefined,
  });
  const dossierRunQuery = useQuery({
    queryKey: ["dossier-run", activeDossierRunId],
    queryFn: () => getReviewRun(activeDossierRunId ?? ""),
    enabled: Boolean(activeDossierRunId),
    refetchInterval: (current) => {
      const status = current.state.data?.status;
      return status && ["PARTIALLY_COMPLETED", "COMPLETED", "FAILED", "CANCELLED"].includes(status)
        ? false
        : 1000;
    },
  });
  const dossierStartMutation = useMutation({
    mutationFn: () => createDossierRun(caseId, query.data?.aggregate_version ?? 0),
    onSuccess: (run) => {
      setDossierRunId(run.run_id);
      void query.refetch();
    },
  });
  const retryDossier = useMutation({
    mutationFn: (id: string) => retryReviewRun(id, query.data?.aggregate_version ?? 0),
    onSuccess: (run) => {
      setDossierRunId(run.run_id);
      void query.refetch();
    },
  });
  const cancelDossier = useMutation({
    mutationFn: (id: string) => cancelReviewRun(id, query.data?.aggregate_version ?? 0),
    onSuccess: () => void query.refetch(),
  });
  const decisionMutation = useMutation({
    mutationFn: () => {
      if (!activeDossierRunId) throw new Error("먼저 가상 역할 검토를 완료하세요.");
      return createSimulatedDecision(
        caseId,
        query.data?.aggregate_version ?? 0,
        activeDossierRunId,
      );
    },
    onSuccess: () => void query.refetch(),
  });
  const outcomeMutation = useMutation({
    mutationFn: () => {
      const fromStep = query.data?.time_context.current_step ?? 0;
      return advanceOutcome(
        caseId,
        query.data?.aggregate_version ?? 0,
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
    onSuccess: () => void query.refetch(),
  });
  const initialResponseMutation = useMutation({
    mutationFn: (command: Parameters<typeof recordInitialDecisionResponse>[2]) => (
      recordInitialDecisionResponse(caseId, query.data?.aggregate_version ?? 0, command)
    ),
    onSuccess: () => void evaluationResponseQuery.refetch(),
  });
  const adviceRevealMutation = useMutation({
    mutationFn: () => revealDecisionAdvice(caseId, query.data?.aggregate_version ?? 0),
    onSuccess: () => void evaluationResponseQuery.refetch(),
  });
  const finalResponseMutation = useMutation({
    mutationFn: (command: Parameters<typeof recordFinalDecisionResponse>[2]) => (
      recordFinalDecisionResponse(caseId, query.data?.aggregate_version ?? 0, command)
    ),
    onSuccess: () => void evaluationResponseQuery.refetch(),
  });
  const commandMutations = [
    dossierStartMutation,
    retryDossier,
    cancelDossier,
    decisionMutation,
    outcomeMutation,
    evaluationMutation,
    initialResponseMutation,
    adviceRevealMutation,
    finalResponseMutation,
  ];
  const stale = commandMutations.some((mutation) => isCaseVersionConflict(mutation.error));
  const dossierStatus = dossierRunQuery.data?.status;
  const refetchWorkspace = query.refetch;
  useEffect(() => {
    if (
      selectedStep === undefined
      && dossierStatus
      && ["PARTIALLY_COMPLETED", "COMPLETED"].includes(dossierStatus)
    ) {
      void refetchWorkspace();
    }
  }, [dossierStatus, refetchWorkspace, selectedStep]);
  const setWorkspaceParam = (
    name: "at_step" | "option" | "interaction",
    value: string | null,
  ) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (value === null) next.delete(name);
      else next.set(name, value);
      return next;
    });
  };
  const refreshStaleWorkspace = async () => {
    setWorkspaceParam("at_step", null);
    await Promise.all([query.refetch(), timelineQuery.refetch()]);
    commandMutations.forEach((mutation) => mutation.reset());
  };

  if (query.isPending) {
    return (
      <main className="app-shell workspace-shell" id="main-content" tabIndex={-1}>
        <p role="status">선택한 Step의 검토 정보를 불러오는 중…</p>
      </main>
    );
  }
  if (query.isError) {
    const errorCopy = workspaceLoadErrorCopy(query.error, selectedStep);
    return (
      <main className="app-shell workspace-shell" id="main-content" tabIndex={-1}>
        <section className="list-feedback" role="alert">
          <h1>결정 검토를 불러오지 못했습니다</h1>
          <p>{errorCopy.reason}</p>
          <p>{errorCopy.recovery}</p>
          <div className="recovery-actions">
            {errorCopy.action === "current" ? (
              <button className="primary-button" type="button" onClick={() => setWorkspaceParam("at_step", null)}>
                현재 시점 보기
              </button>
            ) : errorCopy.action === "retry" ? (
              <button className="primary-button" type="button" onClick={() => void query.refetch()} disabled={query.isFetching}>
                {query.isFetching ? "다시 불러오는 중…" : "다시 시도"}
              </button>
            ) : null}
            <Link className="secondary-button recovery-link" to={riskReturn?.to ?? "/decisions"}>
              {riskReturn ? "Risk 상세로 돌아가기" : "결정 목록으로 돌아가기"}
            </Link>
          </div>
        </section>
      </main>
    );
  }
  if (!query.data) return null;

  const item = query.data;
  const evaluationResponse = evaluationResponseQuery.data;
  const initialResponseRecorded = Boolean(evaluationResponse?.initial_response);
  const adviceRevealed = Boolean(evaluationResponse?.advice_snapshot);
  const finalResponseRecorded = Boolean(evaluationResponse?.final_response);
  const commandsAllowed = item.time_context.commands_allowed_at_selected_step && !stale;
  const dossierResult = dossierRunQuery.data?.result;
  const dossierFailures = dossierResult && "failed_roles" in dossierResult
    ? dossierResult.failed_roles ?? []
    : [];
  const completedDossierRoles = dossierResult && "dossier" in dossierResult
    ? dossierResult.dossier.original_reviews.map((review) => review.role_id)
    : [];
  const primaryAction = item.workflow.primary_action;
  const primaryActionPending = (
    primaryAction === "RUN_VIRTUAL_REVIEW" && dossierStartMutation.isPending
  ) || (
    primaryAction === "RUN_SIMULATED_DECISION" && decisionMutation.isPending
  ) || (
    primaryAction === "ADVANCE_SIMULATION" && outcomeMutation.isPending
  ) || (
    primaryAction === "VIEW_EVALUATION" && evaluationMutation.isPending
  ) || initialResponseMutation.isPending
    || adviceRevealMutation.isPending
    || finalResponseMutation.isPending;
  const evaluationPrimaryAction = evaluationMode
    ? !initialResponseRecorded
      ? "RECORD_INITIAL"
      : item.controls.action_plan && !adviceRevealed
        ? "REVEAL_ADVICE"
        : adviceRevealed && !finalResponseRecorded
          ? "RECORD_FINAL"
          : null
    : null;
  const runPrimaryAction = () => {
    if (evaluationPrimaryAction === "RECORD_INITIAL" || evaluationPrimaryAction === "RECORD_FINAL") {
      focusSection("evaluation-response");
      return;
    }
    if (evaluationPrimaryAction === "REVEAL_ADVICE") {
      adviceRevealMutation.mutate();
      return;
    }
    if (primaryAction === "RUN_VIRTUAL_REVIEW") {
      dossierStartMutation.mutate();
      return;
    }
    if (primaryAction === "RUN_SIMULATED_DECISION") {
      decisionMutation.mutate();
      return;
    }
    if (primaryAction === "ADVANCE_SIMULATION") {
      outcomeMutation.mutate();
      return;
    }
    if (primaryAction === "VIEW_EVALUATION") {
      evaluationMutation.mutate();
      return;
    }
    focusSection(actionTarget(primaryAction));
  };
  const preDecisionReview = (
    <>
      <DevelopmentTwin
        item={item}
        timeline={timelineQuery.data}
        timelinePending={timelineQuery.isPending}
        timelineError={timelineQuery.isError}
        onSelectStep={(step) => {
          setWorkspaceParam("at_step", step === item.time_context.current_step ? null : String(step));
        }}
      />
      <DecisionPosture item={item} />
      <AlternativeComparison
        alternatives={item.alternatives}
        selectedOptionPosition={selectedOptionPosition}
        onSelectOption={(position) => setWorkspaceParam("option", position === null ? null : String(position))}
      />
      {!evaluationMode || adviceRevealed ? (
        <DecisionDeliberation deliberation={item.deliberation} />
      ) : null}
    </>
  );

  return (
    <main className="app-shell workspace-shell" id="main-content" tabIndex={-1}>
      <ContextBar
        item={item}
        riskReturn={riskReturn}
        evaluationMode={evaluationMode}
        onModeChange={(mode) => setWorkspaceParam(
          "interaction",
          mode === "evaluation" ? "evaluation" : null,
        )}
      />

      <DecisionBrief
        item={item}
        commandsAllowed={commandsAllowed}
        primaryActionLabel={
          evaluationPrimaryAction === "RECORD_INITIAL"
            ? "사전 판단 기록"
            : evaluationPrimaryAction === "REVEAL_ADVICE"
              ? "가상 조언 공개"
              : evaluationPrimaryAction === "RECORD_FINAL"
                ? "최종 판단 기록"
                : workspaceActionLabel(primaryAction)
        }
        primaryActionPending={primaryActionPending}
        primaryActionPendingLabel={
          adviceRevealMutation.isPending
            ? "가상 조언 공개 중…"
            : workspaceActionPendingLabel(primaryAction)
        }
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

      {item.controls.action_plan && (!evaluationMode || adviceRevealed) ? (
        <>
          <DecisionExecution item={item} />
          <details className="predecision-review">
            <summary>결정 당시 검토 내용 보기</summary>
            {preDecisionReview}
          </details>
        </>
      ) : preDecisionReview}

      {evaluationMode && item.time_context.mode === "current" ? (
        evaluationResponseQuery.isPending ? (
          <section className="panel" aria-live="polite">
            <p>기록된 평가 응답을 확인하는 중…</p>
          </section>
        ) : (
          <DecisionEvaluationResponse
            item={item}
            response={evaluationResponse}
            pending={
              initialResponseMutation.isPending
              || adviceRevealMutation.isPending
              || finalResponseMutation.isPending
            }
            error={evaluationResponseError(
              initialResponseMutation.error
              ?? adviceRevealMutation.error
              ?? finalResponseMutation.error
              ?? evaluationResponseQuery.error,
            )}
            onRecordInitial={(command) => initialResponseMutation.mutate(command)}
            onRevealAdvice={() => adviceRevealMutation.mutate()}
            onRecordFinal={(command) => finalResponseMutation.mutate(command)}
          />
        )
      ) : null}

      {!item.controls.action_plan
        && item.time_context.mode === "current"
        && (!evaluationMode || initialResponseRecorded) ? (
      <section className="panel virtual-review-panel" id="review" aria-labelledby="review-title" tabIndex={-1}>
        <p className="section-kicker">{evaluationMode ? "조언 준비" : "가상 조언"}</p>
        <h2 id="review-title">{evaluationMode ? "가상 조언을 생성합니다" : "가상 역할 검토와 최종 판단"}</h2>
        <p>{evaluationMode
          ? "사전 판단은 이미 잠겼습니다. 조언을 만들되 내용은 공개 버튼을 누르기 전까지 숨깁니다."
          : "현재 검증된 독립 역할 검토를 한 번 실행합니다. 단일 역할 실험과 구성 비교는 개발자 평가 화면의 범위입니다."}</p>
        {!activeDossierRunId ? <p className="empty-copy">화면 상단의 ‘가상 역할 검토 실행’으로 시작합니다.</p> : null}
        {dossierStartMutation.isError ? <p role="alert">가상 역할 검토를 시작하지 못했습니다. 개발 상태를 새로고침한 뒤 다시 실행하세요.</p> : null}
        {dossierRunQuery.data ? (
          <div aria-live="polite">
            <p><strong>관점별 검토:</strong> {runStatusLabel(dossierRunQuery.data.status)}</p>
            {dossierFailures.length > 0 ? (
              <>
                <p><strong>완료:</strong> {completedDossierRoles.map(roleLabel).join(", ")}</p>
                <p><strong>실패:</strong> {dossierFailures.map((failure) => `${roleLabel(failure.role_id)} · ${runErrorLabel(failure.error_code)}`).join(", ")}</p>
              </>
            ) : null}
            {dossierRunQuery.data.error_code ? <p role="alert">필수 역할 검토가 완료되지 않았습니다. 이 상태에서는 가상 최종 판단을 만들 수 없으므로 실패한 역할을 재시도하세요.</p> : null}
            {["QUEUED", "RUNNING"].includes(dossierRunQuery.data.status) ? (
              <button className="secondary-button" type="button" onClick={() => cancelDossier.mutate(dossierRunQuery.data.run_id)} disabled={!commandsAllowed || cancelDossier.isPending}>검토 취소</button>
            ) : null}
            {["FAILED", "CANCELLED", "PARTIALLY_COMPLETED"].includes(dossierRunQuery.data.status) ? (
              <button className="secondary-button" type="button" onClick={() => retryDossier.mutate(dossierRunQuery.data.run_id)} disabled={retryDossier.isPending || !commandsAllowed}>{retryDossier.isPending ? "재시도 요청 중…" : "가상 역할 검토 재시도"}</button>
            ) : null}
          </div>
        ) : null}
        {dossierRunQuery.data?.status === "COMPLETED" && !decisionMutation.data ? (
          <button className="secondary-button decision-command" type="button" onClick={() => decisionMutation.mutate()} disabled={decisionMutation.isPending || !commandsAllowed}>{decisionMutation.isPending ? "가상 판단 중…" : "가상 최종 판단 실행"}</button>
        ) : null}
        {decisionMutation.isError ? <p role="alert">가상 판단을 만들지 못했습니다. 역할 검토가 완료 상태인지 확인한 뒤 다시 시도하세요.</p> : null}
      </section>
      ) : null}
      {outcomeMutation.isError ? <p className="panel" role="alert">Simulation Step을 진행하지 못했습니다. 개발 상태를 새로고침한 뒤 다시 실행하세요.</p> : null}
      {evaluationMutation.isError ? <p className="panel" role="alert">판단 품질 평가를 완료하지 못했습니다. 결과 공개 상태를 확인한 뒤 다시 실행하세요.</p> : null}
    </main>
  );
}

function ContextBar({
  item,
  riskReturn,
  evaluationMode,
  onModeChange,
}: {
  item: DecisionWorkspace;
  riskReturn: RiskReturn | null;
  evaluationMode: boolean;
  onModeChange: (mode: "demo" | "evaluation") => void;
}) {
  const isHistorical = item.time_context.mode === "historical";
  return (
    <nav className="decision-context-bar" aria-label="결정 검토 문맥">
      <Link className="back-link" to={riskReturn?.to ?? "/decisions"}>
        ← {riskReturn ? "Risk 상세" : "결정 목록"}
      </Link>
      <div className="context-facts">
        <div className="interaction-mode" aria-label="상호작용 모드">
          <button
            type="button"
            aria-pressed={!evaluationMode}
            onClick={() => onModeChange("demo")}
          >
            데모
          </button>
          <button
            type="button"
            aria-pressed={evaluationMode}
            onClick={() => onModeChange("evaluation")}
          >
            조언 영향 평가
          </button>
        </div>
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
  primaryActionPendingLabel,
  onPrimaryAction,
}: {
  item: DecisionWorkspace;
  commandsAllowed: boolean;
  primaryActionLabel: string;
  primaryActionPending: boolean;
  primaryActionPendingLabel: string;
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
            {primaryActionPending ? primaryActionPendingLabel : primaryActionLabel}
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
    <section className="development-twin" id="development-twin" aria-labelledby="development-twin-title" tabIndex={-1}>
      <header className="twin-header">
        <div>
          <p className="section-kicker">개발 진행 트윈</p>
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
          <h3 id="commitment-title">가장 가까운 선택 가능 기한(Commitment Window)</h3>
          {item.development_twin.commitment_windows.length > 0 ? (
            item.development_twin.commitment_windows.slice(0, 3).map((window) => (
              <article className="commitment-card" key={`${window.subject_type}-${window.subject_id}`}>
                <p className="state-label">{window.closes_at_step !== null && window.closes_at_step !== undefined ? `Step ${window.closes_at_step} 종료` : "기준점에서 종료"}</p>
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
      <p className="section-kicker">판단 조건</p>
      <h2 id="posture-title">데이터가 완전하지 않아도 판단할 수 있는 정도</h2>
      <div className="posture-grid">{dimensions.map(([label, value]) => <div key={label}><span>{label}</span><strong>{postureLabel(value)}</strong></div>)}</div>
      <ul>{posture.explanations_ko.map((entry) => <li key={entry}>{entry}</li>)}</ul>
    </section>
  );
}

function parseSearchStep(value: string | null): number | undefined {
  if (value === null || value.trim() === "") return undefined;
  const step = Number(value);
  return Number.isSafeInteger(step) && step >= 0 ? step : undefined;
}

function parseSearchPosition(value: string | null): number | undefined {
  const position = parseSearchStep(value);
  return position !== undefined && position >= 1 ? position : undefined;
}

type RiskReturn = { to: string };

function parseRiskReturn(searchParams: URLSearchParams): RiskReturn | null {
  const projectId = searchParams.get("from_project");
  const riskId = searchParams.get("from_risk");
  const safeId = /^[A-Z0-9]+(?:-[A-Z0-9]+)*$/;
  if (!projectId || !riskId || !safeId.test(projectId) || !safeId.test(riskId)) return null;
  const projectStep = parseSearchStep(searchParams.get("from_project_step"));
  const query = projectStep === undefined ? "" : `?${new URLSearchParams({ at_step: String(projectStep) })}`;
  return { to: `/projects/${encodeURIComponent(projectId)}/risks/${encodeURIComponent(riskId)}${query}` };
}

function workspaceLoadErrorCopy(error: unknown, selectedStep: number | undefined) {
  if (error instanceof ApiError && error.status === 404) {
    return {
      reason: "요청한 결정 검토를 찾을 수 없습니다.",
      recovery: "결정 목록에서 현재 확인 가능한 검토 대상을 다시 선택하세요.",
      action: "list" as const,
    };
  }
  if (
    selectedStep !== undefined
    && error instanceof ApiError
    && [400, 422].includes(error.status)
  ) {
    return {
      reason: `선택한 Step ${selectedStep}의 개발 상태를 재구성할 수 없습니다.`,
      recovery: "현재 시점으로 돌아가면 최신 관측 상태에서 검토를 계속할 수 있습니다.",
      action: "current" as const,
    };
  }
  if (error instanceof ApiError && error.code === "CONNECTION_FAILED") {
    return {
      reason: "의사결정 트윈 서비스에 연결할 수 없습니다.",
      recovery: "새 검토 정보는 표시하지 않았습니다. 연결 상태를 확인한 뒤 다시 시도하세요.",
      action: "retry" as const,
    };
  }
  return {
    reason: "의사결정 트윈 서비스가 검토 요청을 완료하지 못했습니다.",
    recovery: "현재 화면에는 불완전한 정보를 표시하지 않았습니다. 잠시 후 다시 시도하세요.",
    action: "retry" as const,
  };
}

function evaluationResponseError(error: unknown): string | null {
  if (!error) return null;
  if (error instanceof ApiError) {
    return ({
      INITIAL_RESPONSE_IMMUTABLE: "사전 판단은 이미 기록되어 변경할 수 없습니다.",
      ADVICE_REVEAL_IMMUTABLE: "가상 조언은 이미 공개되었습니다.",
      FINAL_RESPONSE_IMMUTABLE: "최종 판단은 이미 기록되어 변경할 수 없습니다.",
      SIMULATED_ADVICE_REQUIRED: "먼저 가상 최종 판단을 완료하세요.",
      ACCEPT_MUST_MATCH_ADVICE: "조언 수용을 선택하면 권고 선택지를 유지해야 합니다.",
      CASE_VERSION_CONFLICT: "개발 상태가 변경되었습니다. 최신 상태를 불러오세요.",
    } as Record<string, string>)[error.code ?? ""]
      ?? "평가 응답을 처리하지 못했습니다. 단계와 입력을 확인한 뒤 다시 시도하세요.";
  }
  return "평가 응답을 처리하지 못했습니다. 잠시 후 다시 시도하세요.";
}

function actionTarget(action: DecisionWorkspace["workflow"]["primary_action"]) {
  if (action === "VIEW_DOSSIER") return "deliberation";
  if (action === "VIEW_REVIEW_PROGRESS" || action === "RUN_SIMULATED_DECISION") return "review";
  if (action === "VIEW_LEARNING_SUMMARY") return "learning";
  if (action === "ADVANCE_SIMULATION" || action === "VIEW_EVALUATION") return "execution";
  return "development-twin";
}

function focusSection(targetId: string) {
  const target = document.getElementById(targetId);
  if (!target) return;
  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
  target.scrollIntoView?.({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
  target.focus({ preventScroll: true });
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

function workspaceActionPendingLabel(action: DecisionWorkspace["workflow"]["primary_action"]) {
  if (action === "RUN_VIRTUAL_REVIEW") return "가상 역할 검토 요청 중…";
  if (action === "RUN_SIMULATED_DECISION") return "가상 판단 중…";
  if (action === "ADVANCE_SIMULATION") return "Simulation Step 진행 중…";
  if (action === "VIEW_EVALUATION") return "판단 품질 평가 중…";
  return "처리 중…";
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
    architecture_system: "Architecture",
    hw_rtl: "HW/RTL",
    sw: "SW/FW/HAL",
    verification_measurement: "Verification/Measurement",
    program_risk: "Technical PM",
  } as Record<string, string>)[roleId] ?? roleId.replace(/^ROLE-/, "");
}

function runErrorLabel(errorCode: string) {
  return ({
    PROVIDER_USAGE_LIMIT: "실행 한도 초과",
    PROVIDER_ATTEMPT_FAILED: "응답 검증 실패",
    PROVIDER_ATTEMPT_BUDGET_EXHAUSTED: "재시도 한도 초과",
    ROLE_REVIEW_FAILED: "역할 검토 실패",
  } as Record<string, string>)[errorCode] ?? "역할 검토 실패";
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
    milestone: "기준점",
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
    BLOCKER_CHANGE: "대기 원인 변경",
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
