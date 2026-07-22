import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import { ApiError, getProjectSituation, getProjectTimeline } from "../../api/client";
import type { ProjectRiskSummary, ProjectSituation, ProjectTimeline } from "../../api/generated";
import {
  attentionLabel,
  lifecycleLabel,
  rankingReasonLabel,
  riskLevelLabel,
  riskStatusLabel,
  stateLabel,
  stepDistance,
} from "./projectPresentation";

export function ProjectSituationPage() {
  const { projectId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedStep = parseStep(searchParams.get("at_step"));
  const situationQuery = useQuery({
    queryKey: ["project-situation", projectId, selectedStep ?? "current"],
    queryFn: () => getProjectSituation(projectId, selectedStep),
    enabled: projectId.length > 0,
  });
  const timelineQuery = useQuery({
    queryKey: ["project-timeline", projectId, selectedStep ?? "current"],
    queryFn: () => getProjectTimeline(projectId, selectedStep),
    enabled: projectId.length > 0,
  });
  const sourceViews = useMemo(
    () => buildSourceViews(situationQuery.data, timelineQuery.data),
    [situationQuery.data, timelineQuery.data],
  );

  function selectStep(step: number | undefined) {
    const next = new URLSearchParams(searchParams);
    if (step === undefined || step === situationQuery.data?.current_step) next.delete("at_step");
    else next.set("at_step", String(step));
    setSearchParams(next);
  }

  if (situationQuery.isPending) {
    return (
      <main className="app-shell project-situation-shell" id="main-content" tabIndex={-1}>
        <p role="status">과제 상황을 재구성하는 중…</p>
        <div className="project-situation-skeleton" aria-hidden="true" />
      </main>
    );
  }

  if (situationQuery.isError) {
    return (
      <ProjectSituationError
        error={situationQuery.error}
        selectedStep={selectedStep}
        onRetry={() => void situationQuery.refetch()}
        onCurrent={() => selectStep(undefined)}
      />
    );
  }

  const situation = situationQuery.data;
  const topRisk = situation.risks[0];
  const blockedItems = situation.work_items.filter((item) => item.status === "BLOCKED");
  const activeIssues = situation.issues.filter((item) => item.status !== "RESOLVED");
  const isHistorical = situation.reconstructed_at_step !== situation.current_step;

  return (
    <main className="app-shell project-situation-shell" id="main-content" tabIndex={-1}>
      <nav className="project-breadcrumb" aria-label="과제 탐색">
        <Link className="back-link" to="/projects">← 과제 포트폴리오</Link>
        <span aria-hidden="true">/</span>
        <span>과제 상황</span>
      </nav>

      <header className="situation-hero" data-attention={situation.attention}>
        <div className="situation-title-block">
          <div className="project-chip-row">
            <span className="project-attention-chip" data-attention={situation.attention}>
              {attentionLabel(situation.attention)}
            </span>
            <span className="project-stage-chip">{lifecycleLabel(situation.lifecycle_stage)}</span>
            {isHistorical ? <span className="history-chip">과거 상태</span> : null}
          </div>
          <h1>{situation.title_ko}</h1>
          <p>Step {situation.reconstructed_at_step} 기준 · Project 상태와 근거를 함께 봅니다.</p>
        </div>
        <label className="project-step-selector">
          <span>관찰 시점</span>
          <select
            value={isHistorical ? String(situation.reconstructed_at_step) : "current"}
            onChange={(event) => selectStep(event.target.value === "current" ? undefined : Number(event.target.value))}
          >
            <option value="current">현재 Step {situation.current_step}</option>
            {Array.from({ length: situation.current_step }, (_, index) => situation.current_step - index - 1).map((step) => (
              <option value={step} key={step}>Step {step}</option>
            ))}
          </select>
        </label>
      </header>

      {isHistorical ? (
        <aside className="historical-project-notice">
          <strong>선택한 Step 당시 상태</strong>
          <span>Step {situation.reconstructed_at_step} 이후에 관측된 Event, Evidence와 Risk 상태는 포함하지 않습니다.</span>
          <button className="secondary-button" type="button" onClick={() => selectStep(undefined)}>현재 시점 보기</button>
        </aside>
      ) : null}

      <section className="situation-overview" aria-labelledby="situation-overview-heading">
        <div className="situation-priority">
          <p className="section-kicker">전체 상황</p>
          <h2 id="situation-overview-heading">지금 가장 먼저 확인할 이유</h2>
          <ul className="attention-reason-list">
            {situation.attention_reasons.map((reason) => (
              <li key={reason.code}>
                <strong>{reason.summary_ko}</strong>
                <span>판정 근거 <b translate="no">{reason.source_refs.join(" · ")}</b></span>
              </li>
            ))}
          </ul>
        </div>
        <dl className="situation-counts">
          <div><dt>활성 Issue</dt><dd>{activeIssues.length}</dd></div>
          <div><dt>Risk</dt><dd>{situation.risks.length}</dd></div>
          <div><dt>막힌 작업</dt><dd>{blockedItems.length}</dd></div>
          <div><dt>개발 Track</dt><dd>{situation.tracks.length}</dd></div>
        </dl>
      </section>

      <TopRiskSection
        risk={topRisk}
        situation={situation}
        sourceViews={topRisk ? sourceViews.get(topRisk.risk_id) ?? [] : []}
      />

      {situation.risks.length > 1 ? (
        <section className="project-section" aria-labelledby="other-risks-heading">
          <header className="project-section-header">
            <div>
              <p className="section-kicker">나머지 위험</p>
              <h2 id="other-risks-heading">함께 추적할 Risk</h2>
            </div>
            <p>우선순위는 Backend의 동일한 Risk ordering policy를 따릅니다.</p>
          </header>
          <div className="other-risk-list">
            {situation.risks.slice(1).map((risk) => (
              <article key={risk.risk_id}>
                <div>
                  <span className="risk-level-chip" data-level={risk.risk_level}>
                    우선순위 {risk.rank} · {riskLevelLabel(risk.risk_level)}
                  </span>
                  <h3>{risk.statement}</h3>
                  <p>{risk.ranking_reasons.map(rankingReasonLabel).join(" · ")}</p>
                </div>
                <Link
                  className="secondary-button recovery-link"
                  to={riskDetailPath(situation.project_id, risk.risk_id, isHistorical ? situation.reconstructed_at_step : undefined)}
                >
                  Risk 상세 추적
                </Link>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      <section className="project-section" aria-labelledby="development-flow-heading">
        <header className="project-section-header">
          <div>
            <p className="section-kicker">개발 진행</p>
            <h2 id="development-flow-heading">어디가 막혔고 다음 기준점은 무엇인가</h2>
          </div>
          <p>Issue와 Risk를 작업 진행 상태와 섞지 않고 나누어 표시합니다.</p>
        </header>

        {blockedItems.length > 0 ? (
          <div className="blocked-work-list" aria-label="막힌 작업">
            {blockedItems.map((item) => (
              <article key={item.work_item_id}>
                <span className="state-chip" data-state={item.status}>막힌 작업</span>
                <h3>{item.title}</h3>
                <p>{item.blocker ?? "관측된 blocker 설명이 없습니다."}</p>
                <small>{trackTitle(situation, item.track_id)} · 계획 Step {item.planned_at_step}</small>
              </article>
            ))}
          </div>
        ) : <p className="empty-state-copy">현재 BLOCKED 상태인 작업은 없습니다.</p>}

        <div className="track-situation-grid">
          {situation.tracks.map((track) => (
            <article className="track-situation-card" key={track.track_id}>
              <div className="track-card-title">
                <h3>{track.name}</h3>
                <span className="state-chip" data-state={track.status}>{stateLabel(track.status)}</span>
              </div>
              <p>막힌 작업 {track.blocked_work_item_count}개</p>
              <p>다음 기준점 <strong translate="no">{track.next_milestone_id ?? "미정"}</strong></p>
              <ul>
                {situation.work_items.filter((item) => item.track_id === track.track_id).map((item) => (
                  <li key={item.work_item_id}>
                    <span>{item.title}</span>
                    <small>{stateLabel(item.status)} · Step {item.planned_at_step}</small>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>

        <div className="milestone-strip" aria-label="과제 기준점">
          {situation.milestones.map((milestone) => (
            <article key={milestone.milestone_id} data-state={milestone.status}>
              <p>{milestone.kind === "GATE" ? "Gate" : milestone.kind === "RELEASE" ? "Release" : "Checkpoint"}</p>
              <h3>{milestone.title}</h3>
              <span>{stateLabel(milestone.status)} · {stepDistance(milestone.planned_at_step, situation.reconstructed_at_step)}</span>
              {milestone.commitment_at_step !== null ? <small>확정 Step {milestone.commitment_at_step}</small> : null}
            </article>
          ))}
        </div>
      </section>

      <section className="project-section" aria-labelledby="evidence-heading">
        <header className="project-section-header">
          <div>
            <p className="section-kicker">관측과 불확실성</p>
            <h2 id="evidence-heading">이미 발생한 Issue와 아직 필요한 근거</h2>
          </div>
        </header>
        <div className="issue-evidence-grid">
          <div>
            <h3>관측된 Issue</h3>
            {situation.issues.length > 0 ? situation.issues.map((issue) => (
              <article className="issue-evidence-card" key={issue.issue_id}>
                <span className="state-chip" data-state={issue.status}>{stateLabel(issue.status)}</span>
                <h4>{issue.title}</h4>
                <p>Step {issue.observed_at_step} 관측 · 영향 작업 {issue.affected_work_item_ids.length}개</p>
              </article>
            )) : <p className="empty-state-copy">이 Step에서 관측된 Issue가 없습니다.</p>}
          </div>
          <div>
            <h3>Evidence 상태</h3>
            {situation.evidence.map((evidence) => (
              <article className="issue-evidence-card" key={evidence.evidence_id}>
                <span className="state-chip" data-state={evidence.status}>{stateLabel(evidence.status)}</span>
                <h4>{evidence.title}</h4>
                <p>예정 Step {evidence.expected_at_step}{evidence.available_at_step !== null ? ` · 확보 Step ${evidence.available_at_step}` : " · 아직 미확보"}</p>
                {evidence.limitations.length > 0 ? <small>한계 {evidence.limitations.length}개</small> : null}
              </article>
            ))}
          </div>
        </div>
      </section>

      <TimelineSection
        timeline={timelineQuery.data}
        isPending={timelineQuery.isPending}
        isError={timelineQuery.isError}
        onRetry={() => void timelineQuery.refetch()}
      />
    </main>
  );
}

function TopRiskSection({
  risk,
  situation,
  sourceViews,
}: {
  risk: ProjectRiskSummary | undefined;
  situation: ProjectSituation;
  sourceViews: SourceView[];
}) {
  if (!risk) {
    return (
      <section className="project-section">
        <p className="section-kicker">주요 위험</p>
        <h2>현재 표시할 Risk가 없습니다</h2>
      </section>
    );
  }

  const affectedWork = risk.affected_work_item_ids.map((id) => situation.work_items.find((item) => item.work_item_id === id)?.title ?? id);
  const affectedMilestones = risk.affected_milestone_ids.map((id) => situation.milestones.find((item) => item.milestone_id === id)?.title ?? id);
  const missingEvidence = risk.missing_evidence_ids.map((id) => situation.evidence.find((item) => item.evidence_id === id)?.title ?? id);

  return (
    <section className="project-section top-risk-section" aria-labelledby="top-risk-heading">
      <header className="project-section-header">
        <div>
          <p className="section-kicker">우선순위 1</p>
          <h2 id="top-risk-heading">가장 먼저 볼 Risk와 그 근거</h2>
        </div>
        <span className="risk-level-chip" data-level={risk.risk_level}>
          {riskLevelLabel(risk.risk_level)} · {riskStatusLabel(risk.status)}
        </span>
      </header>
      <p className="risk-statement">{risk.statement}</p>

      <div className="risk-reason-grid">
        <article>
          <h3>왜 우선인가</h3>
          <ul>{risk.ranking_reasons.map((reason) => <li key={reason}>{rankingReasonLabel(reason)}</li>)}</ul>
        </article>
        <article>
          <h3>어디에 영향이 있는가</h3>
          <dl>
            <div><dt>작업</dt><dd>{affectedWork.join(" · ") || "직접 영향 작업 없음"}</dd></div>
            <div><dt>기준점</dt><dd>{affectedMilestones.join(" · ") || "직접 영향 기준점 없음"}</dd></div>
          </dl>
        </article>
      </div>

      <div className="risk-source-panel">
        <h3>이 Risk는 어디에서 나왔는가</h3>
        <p>Backend가 반환한 source reference를 현재 Step에서 볼 수 있는 Issue, Evidence와 Event에 연결했습니다.</p>
        <ol className="risk-source-list">
          {sourceViews.map((source) => (
            <li key={source.reference}>
              <span>{source.kind}</span>
              <strong>{source.title}</strong>
              <small translate="no">{source.reference}</small>
            </li>
          ))}
        </ol>
        {missingEvidence.length > 0 ? (
          <aside className="missing-evidence">
            <strong>아직 확인이 필요한 근거</strong>
            <span>{missingEvidence.join(" · ")}</span>
          </aside>
        ) : null}
      </div>
      <div className="risk-detail-cta">
        <p>근거가 어떤 추론을 거쳐 개발 영향과 대응 Decision·Action으로 이어지는지 한 흐름으로 확인합니다.</p>
        <Link
          className="primary-button recovery-link"
          to={riskDetailPath(
            situation.project_id,
            risk.risk_id,
            situation.reconstructed_at_step === situation.current_step ? undefined : situation.reconstructed_at_step,
          )}
        >
          근거·영향·대응 상세 추적
        </Link>
      </div>
    </section>
  );
}

function TimelineSection({
  timeline,
  isPending,
  isError,
  onRetry,
}: {
  timeline: ProjectTimeline | undefined;
  isPending: boolean;
  isError: boolean;
  onRetry: () => void;
}) {
  return (
    <section className="project-section" aria-labelledby="timeline-heading">
      <header className="project-section-header">
        <div>
          <p className="section-kicker">변화 이력</p>
          <h2 id="timeline-heading">최근 관측이 현재 상태를 어떻게 만들었는가</h2>
        </div>
      </header>
      {isPending ? <p role="status">변화 이력을 불러오는 중…</p> : null}
      {isError ? (
        <div className="inline-feedback" role="alert">
          <p>변화 이력만 불러오지 못했습니다. 위의 현재 상황은 계속 검토할 수 있습니다.</p>
          <button className="secondary-button" type="button" onClick={onRetry}>이력 다시 시도</button>
        </div>
      ) : null}
      {timeline ? (
        timeline.events.length > 0 ? (
          <ol className="project-timeline">
            {[...timeline.events].slice(-6).reverse().map((event) => (
              <li key={event.event_id}>
                <div><span>Step {event.observed_at_step}</span><small>실제 영향 Step {event.effective_at_step}</small></div>
                <article>
                  <h3>{event.summary}</h3>
                  <p>{event.cause}</p>
                  <small>영향 객체 {event.affected_entity_ids.length}개 · 기준점 {event.impacted_milestone_ids.length}개</small>
                </article>
              </li>
            ))}
          </ol>
        ) : <p className="empty-state-copy">이 Step까지 관측된 변화 Event가 없습니다.</p>
      ) : null}
    </section>
  );
}

function ProjectSituationError({
  error,
  selectedStep,
  onRetry,
  onCurrent,
}: {
  error: unknown;
  selectedStep: number | undefined;
  onRetry: () => void;
  onCurrent: () => void;
}) {
  const unavailableStep = error instanceof ApiError && error.code === "PROJECT_STEP_OUT_OF_RANGE";
  const missingProject = error instanceof ApiError && error.code === "PROJECT_NOT_FOUND";
  return (
    <main className="app-shell project-situation-shell" id="main-content" tabIndex={-1}>
      <section className="list-feedback" role="alert">
        <h1>{unavailableStep ? `선택한 Step ${selectedStep}의 과제 상태를 재구성할 수 없습니다` : missingProject ? "과제를 찾을 수 없습니다" : "과제 상황을 불러오지 못했습니다"}</h1>
        <p>{unavailableStep ? "이후에 알려진 정보를 섞지 않기 위해 해당 시점 조회를 중단했습니다." : "과제 목록으로 돌아가거나 연결 상태를 확인한 뒤 다시 시도하세요."}</p>
        <div className="recovery-actions">
          {unavailableStep ? <button className="primary-button" type="button" onClick={onCurrent}>현재 시점 보기</button> : <button className="primary-button" type="button" onClick={onRetry}>다시 시도</button>}
          <Link className="secondary-button recovery-link" to="/projects">과제 포트폴리오</Link>
        </div>
      </section>
    </main>
  );
}

type SourceView = { reference: string; kind: string; title: string };

function buildSourceViews(situation?: ProjectSituation, timeline?: ProjectTimeline) {
  const result = new Map<string, SourceView[]>();
  if (!situation) return result;
  const issues = new Map(situation.issues.map((item) => [item.issue_id, item.title]));
  const evidence = new Map(situation.evidence.map((item) => [item.evidence_id, item.title]));
  const events = new Map((timeline?.events ?? []).map((item) => [item.event_id, item.summary]));
  for (const risk of situation.risks) {
    result.set(risk.risk_id, risk.source_refs.map((reference) => {
      if (issues.has(reference)) return { reference, kind: "관측 Issue", title: issues.get(reference)! };
      if (evidence.has(reference)) return { reference, kind: "Evidence", title: evidence.get(reference)! };
      if (events.has(reference)) return { reference, kind: "개발 Event", title: events.get(reference)! };
      if (reference.startsWith("CROSS-")) return { reference, kind: "다른 과제의 학습", title: "과제 간 전파 근거" };
      return { reference, kind: "추적 가능한 근거", title: reference };
    }));
  }
  return result;
}

function trackTitle(situation: ProjectSituation, trackId: string) {
  return situation.tracks.find((track) => track.track_id === trackId)?.name ?? trackId;
}

function parseStep(value: string | null) {
  if (value === null) return undefined;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : undefined;
}

function riskDetailPath(projectId: string, riskId: string, atStep?: number) {
  const query = atStep === undefined ? "" : `?${new URLSearchParams({ at_step: String(atStep) })}`;
  return `/projects/${encodeURIComponent(projectId)}/risks/${encodeURIComponent(riskId)}${query}`;
}
