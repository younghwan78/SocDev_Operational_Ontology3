import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";

import { advanceOutcome, cancelReviewRun, createDossierRun, createReviewRun, createSimulatedDecision, evaluateOutcome, getDecisionWorkspace, getReviewRun, isCaseVersionConflict, retryReviewRun } from "../../api/client";

export function DecisionWorkspacePage() {
  const { caseId = "" } = useParams();
  const [runId, setRunId] = useState<string | null>(null);
  const [dossierRunId, setDossierRunId] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["decision-workspace", caseId],
    queryFn: () => getDecisionWorkspace(caseId),
    enabled: Boolean(caseId),
  });
  const runQuery = useQuery({
    queryKey: ["review-run", runId],
    queryFn: () => getReviewRun(runId ?? ""),
    enabled: Boolean(runId),
    refetchInterval: (current) => {
      const status = current.state.data?.status;
      return status && ["PARTIALLY_COMPLETED", "COMPLETED", "FAILED", "CANCELLED"].includes(status) ? false : 1000;
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
      return status && ["PARTIALLY_COMPLETED", "COMPLETED", "FAILED", "CANCELLED"].includes(status) ? false : 1000;
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
      return createSimulatedDecision(caseId, query.data?.aggregate_version ?? 0, dossierRunId);
    },
  });
  const outcomeMutation = useMutation({
    mutationFn: () => {
      if (!decisionMutation.data) throw new Error("먼저 모의 결정을 실행하세요.");
      const fromStep = query.data?.current_step ?? 0;
      return advanceOutcome(
        caseId,
        query.data?.aggregate_version ?? 0,
        decisionMutation.data.decision,
        fromStep,
        Math.max(fromStep + 1, 15),
      );
    },
    onSuccess: () => { void query.refetch(); },
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
    await query.refetch();
    commandMutations.forEach((mutation) => mutation.reset());
  };

  if (query.isPending) return <main className="app-shell"><p role="status">검토 정보를 불러오는 중…</p></main>;
  if (query.isError) return <main className="app-shell"><p role="alert">{query.error.message}</p></main>;
  if (!query.data) return null;
  const item = query.data;
  const dossierResult = dossierRunQuery.data?.result;
  const dossierFailures = dossierResult && "failed_roles" in dossierResult
    ? dossierResult.failed_roles ?? []
    : [];
  const completedDossierRoles = dossierResult && "dossier" in dossierResult
    ? dossierResult.dossier.original_reviews.map((review) => review.role_id)
    : [];

  return (
    <main className="app-shell">
      <Link className="back-link" to="/decisions">← 결정 목록</Link>
      <header className="workspace-header">
        <p className="eyebrow">가상 판단 · Step {item.current_step}</p>
        <h1>{item.title_ko}</h1>
        <p className="question">{item.decision_question}</p>
        <p className="deadline">결정 기한: Step {item.deadline_step} · {item.deadline_title}</p>
      </header>
      {stale && (
        <section className="panel stale-panel" role="alert">
          <h2>개발 상태가 변경되었습니다</h2>
          <p>현재 화면의 판단 기준이 이전 version입니다. 최신 상태를 확인한 뒤 다시 실행하세요.</p>
          <button className="primary-button" type="button" onClick={() => void refreshStaleWorkspace()} disabled={query.isFetching}>
            {query.isFetching ? "최신 상태 확인 중…" : "최신 상태 불러오기"}
          </button>
        </section>
      )}
      <section className="panel">
        <h2>현재 개발 상황</h2>
        <div className="track-table" role="table" aria-label="개발 Track">
          {item.tracks.map((track) => (
            <div className="track-row" role="row" key={track.track_id}>
              <strong role="cell">{track.name}</strong>
              <span role="cell">{track.status}</span>
              <span role="cell">Blocker {track.blocker_count}개</span>
            </div>
          ))}
        </div>
      </section>
      <section className="summary-grid">
        <article className="panel"><h2>선택지</h2><p>{item.alternative_count}개</p></article>
        <article className="panel"><h2>현재 근거</h2><p>{item.evidence_count}개</p></article>
        <article className="panel"><h2>불확실성</h2><p>{item.uncertainty_count}개</p></article>
      </section>
      <section className="panel agent-panel">
        <h2>선택지와 되돌릴 수 있는 정도</h2>
        <div className="option-grid">
          {item.alternatives.map((option) => (
            <article className="option-card" key={option.option_id}>
              <p className="status-chip">{option.reversible ? "되돌릴 수 있음" : "되돌리기 어려움"}</p>
              <h3>{option.title}</h3>
              <p>{option.description}</p>
            </article>
          ))}
        </div>
        <h3>현재 blocker</h3>
        <ul>{item.blockers.map((blocker) => <li key={`${blocker.track_id}-${blocker.work_item_title}`}><strong>{blocker.work_item_title}</strong>: {blocker.blocker}</li>)}</ul>
        <h3>아직 모르는 것</h3>
        <ul>{item.uncertainties.map((uncertainty) => <li key={uncertainty}>{uncertainty}</li>)}</ul>
        <h3>근거와 한계</h3>
        <div className="evidence-list">
          {item.evidence.map((evidence) => (
            <article className="evidence-card" key={evidence.evidence_id}>
              <p className="status-chip">{evidence.eligible_now ? "현재 사용 가능" : `Step ${evidence.available_at_step} 공개`}</p>
              <h4>{evidence.title}</h4>
              <p>{evidence.evidence_type} · 출처 {evidence.source_ref}</p>
              {evidence.limitations.length > 0 && <p><strong>한계:</strong> {evidence.limitations.join(", ")}</p>}
            </article>
          ))}
        </div>
        <h3>주장의 근거 상태</h3>
        <ul>{item.claims.map((claim) => <li key={claim.claim_id}><strong>{epistemicLabel(claim.epistemic_status)}</strong> · {claim.statement} ({claim.confidence_level})</li>)}</ul>
      </section>
      <section className="panel agent-panel" aria-labelledby="agent-review-title">
        <h2 id="agent-review-title">역할 기반 검토</h2>
        <p>현재 개발 진행, 근거, 불확실성을 함께 보고 위험을 줄이는 선택을 조언합니다.</p>
        {!runId && (
          <button className="primary-button" type="button" onClick={() => startReview.mutate()} disabled={startReview.isPending || stale}>
            {startReview.isPending ? "검토 요청 중…" : "역할 검토 시작"}
          </button>
        )}
        {startReview.isError && <p role="alert">{startReview.error.message}</p>}
        {runQuery.data && (
          <div className="run-progress" aria-live="polite">
            <p><strong>진행 상태:</strong> {runStatusLabel(runQuery.data.status)} · 시도 {runQuery.data.attempt_no}/{runQuery.data.max_attempts}</p>
            <p><strong>실행 한도:</strong> logical {runQuery.data.budget_plan.reserved_logical_calls}/{runQuery.data.budget_plan.max_logical_calls} · provider 시도 {runQuery.data.budget_plan.reserved_provider_attempts}/{runQuery.data.budget_plan.max_provider_attempts} · 최대 ${runQuery.data.budget_plan.maximum_cost_usd.toFixed(2)}</p>
            {["QUEUED", "RUNNING"].includes(runQuery.data.status) && (
              <button className="secondary-button" type="button" onClick={() => cancelReview.mutate(runQuery.data.run_id)} disabled={stale}>취소</button>
            )}
            {runQuery.data.error_code && <p role="alert">실패 원인: {runQuery.data.error_code}</p>}
            {["FAILED", "CANCELLED", "PARTIALLY_COMPLETED"].includes(runQuery.data.status) && (
              <button className="primary-button" type="button" onClick={() => retryReview.mutate(runQuery.data.run_id)} disabled={retryReview.isPending || stale}>{retryReview.isPending ? "재시도 요청 중…" : "검토 재시도"}</button>
            )}
            {runQuery.data.result && "review" in runQuery.data.result && (
              <article className="review-card">
                <p className="eyebrow">{runQuery.data.result.review.role_id}</p>
                <h3>{runQuery.data.result.review.recommendation}</h3>
                <p>{runQuery.data.result.review.rationale}</p>
                <p><strong>확신 수준:</strong> {runQuery.data.result.review.confidence}</p>
              </article>
            )}
          </div>
        )}
        {runQuery.isError && <p role="alert">진행 상태를 확인하지 못했습니다. 잠시 후 다시 시도하세요.</p>}
      </section>
      <section className="panel agent-panel" aria-labelledby="dossier-title">
        <h2 id="dossier-title">다중 역할 판단과 모의 결정</h2>
        <p>역할별 독립 검토와 반론을 거친 뒤, 실제 승인이 아닌 모의 Chair 결정을 만듭니다.</p>
        {!dossierRunId && (
          <button className="primary-button" type="button" onClick={() => dossierStartMutation.mutate()} disabled={dossierStartMutation.isPending || stale}>
            {dossierStartMutation.isPending ? "검토 요청 중…" : "다중 역할 검토 시작"}
          </button>
        )}
        {dossierRunQuery.data && <div aria-live="polite">
          <p><strong>다중 역할 진행:</strong> {runStatusLabel(dossierRunQuery.data.status)}</p>
          <p><strong>실행 한도:</strong> logical {dossierRunQuery.data.budget_plan.reserved_logical_calls}/{dossierRunQuery.data.budget_plan.max_logical_calls} · provider 시도 {dossierRunQuery.data.budget_plan.reserved_provider_attempts}/{dossierRunQuery.data.budget_plan.max_provider_attempts} · output {dossierRunQuery.data.budget_plan.reserved_output_tokens}/{dossierRunQuery.data.budget_plan.max_output_tokens} tokens · 최대 ${dossierRunQuery.data.budget_plan.maximum_cost_usd.toFixed(2)}</p>
          {dossierFailures.length > 0 && <>
            <p><strong>완료:</strong> {completedDossierRoles.join(", ")}</p>
            <p><strong>실패:</strong> {dossierFailures.map((failure) => `${failure.role_id} (${failure.error_code})`).join(", ")}</p>
          </>}
          {dossierRunQuery.data.error_code && <p role="alert">필수 역할 검토 실패: {dossierRunQuery.data.error_code}. 이 상태에서는 Chair 결정을 만들 수 없습니다.</p>}
          {["FAILED", "CANCELLED", "PARTIALLY_COMPLETED"].includes(dossierRunQuery.data.status) && <button className="primary-button" type="button" onClick={() => retryDossier.mutate(dossierRunQuery.data.run_id)} disabled={retryDossier.isPending || stale}>{retryDossier.isPending ? "재시도 요청 중…" : "다중 검토 재시도"}</button>}
        </div>}
        {dossierRunQuery.data?.status === "COMPLETED" && !decisionMutation.data && <button className="primary-button" type="button" onClick={() => decisionMutation.mutate()} disabled={decisionMutation.isPending || stale}>{decisionMutation.isPending ? "Chair 판단 중…" : "모의 Chair 결정"}</button>}
        {decisionMutation.isError && <p role="alert">모의 결정을 만들지 못했습니다. 다시 시도하세요.</p>}
        {decisionMutation.data && (
          <div className="decision-result">
            <p className="status-chip">모의 결정 · {decisionMutation.data.topology}</p>
            <h3>{decisionMutation.data.decision.decision_type}</h3>
            <p>{decisionMutation.data.decision.rationale}</p>
            <h3>합의</h3>
            <ul>{decisionMutation.data.dossier.agreement_groups.map((group) => <li key={group.recommendation}>{group.recommendation}: {group.role_ids.join(", ")}</li>)}</ul>
            <h3>반대 의견</h3>
            {decisionMutation.data.dossier.dissent.length === 0 ? <p>기록된 반대 의견 없음</p> : <ul>{decisionMutation.data.dossier.dissent.map((item) => <li key={item.role_id}><strong>{item.role_id}</strong>: {item.recommendation} — {item.rationale}</li>)}</ul>}
            <h3>안전장치</h3>
            {decisionMutation.data.decision.safeguards.map((guard) => (
              <article className="safeguard-card" key={guard.safeguard_id}>
                <p><strong>측정 기준:</strong> {guard.metric_id} {guard.operator} {guard.threshold.value} {guard.threshold.unit} · Step {guard.check_at_step}</p>
                <p><strong>적용 조건:</strong> {guard.condition}</p>
                <p><strong>중단·복구 기준:</strong> {guard.rollback_trigger}</p>
                <p><strong>실행 조치:</strong> {guard.violation_action} · Step {guard.expires_at_step} 재검토</p>
                <p><strong>담당:</strong> {guard.owner}</p>
                <p><strong>확인 방법:</strong> {guard.verification}</p>
              </article>
            ))}
            <h3>Chair가 수용한 잔여 위험</h3>
            <ul>{decisionMutation.data.dossier.unresolved_uncertainties.map((item) => <li key={item}>{item}</li>)}</ul>
          </div>
        )}
      </section>
      <section className="panel agent-panel" aria-labelledby="outcome-title">
        <h2 id="outcome-title">결과와 판단 품질 확인</h2>
        <p>모의 시간을 진행해 숨겨진 결과를 공개하고, 판단 과정과 실제 결과를 분리해 평가합니다.</p>
        {!outcomeMutation.data && <button className="primary-button" type="button" onClick={() => outcomeMutation.mutate()} disabled={outcomeMutation.isPending || !decisionMutation.data || stale}>{outcomeMutation.isPending ? "결과 계산 중…" : "다음 Step 진행"}</button>}
        {outcomeMutation.isError && <p role="alert">결과 평가를 완료하지 못했습니다.</p>}
        {outcomeMutation.data && (
          <div className="decision-result">
            <p className="status-chip">Step {outcomeMutation.data.current_step} · {outcomeMutation.data.guardrail_state}</p>
            <h3>공개된 결과</h3>
            <ul>{[...outcomeMutation.data.revealed_evidence, ...outcomeMutation.data.consequences].map((item) => <li key={item}>{item}</li>)}</ul>
            {outcomeMutation.data.executed_actions.length > 0 && <p><strong>실행된 보호 조치:</strong> {outcomeMutation.data.executed_actions.join(", ")}</p>}
            {!evaluationMutation.data && <button className="primary-button" type="button" onClick={() => evaluationMutation.mutate()} disabled={evaluationMutation.isPending || stale}>{evaluationMutation.isPending ? "평가 중…" : "판단 품질 평가"}</button>}
            {evaluationMutation.data && <>
              <h3>과정 평가</h3><p>{evaluationMutation.data.process_evaluation.passed ? "필수 근거·의존성·안전장치를 충족했습니다." : "판단 과정의 필수 항목이 부족합니다."}</p>
              <h3>결과 평가</h3><p>{evaluationMutation.data.outcome_evaluation.passed ? "위험 신호에 보호 조치가 실행되었습니다." : "위험 통제에 실패했습니다."}</p>
              <p className="explanation"><strong>왜 과정과 결과가 다를 수 있나요?</strong> 당시 이용할 수 있는 근거로 합리적으로 판단했어도 숨겨진 원인 때문에 결과가 나쁠 수 있고, 반대로 근거가 빈약한 판단이 우연히 좋은 결과를 낼 수도 있기 때문입니다.</p>
            </>}
          </div>
        )}
      </section>
    </main>
  );
}

function runStatusLabel(status: string) {
  return ({ QUEUED: "대기 중", RUNNING: "검토 중", PARTIALLY_COMPLETED: "일부 완료", COMPLETED: "완료", FAILED: "실패", CANCELLED: "취소됨" } as Record<string, string>)[status] ?? status;
}

function epistemicLabel(status: string) {
  return ({ fact: "확인된 사실", inference: "근거 기반 추론", assumption: "검토할 가정", unknown: "아직 모름" } as Record<string, string>)[status] ?? status;
}
