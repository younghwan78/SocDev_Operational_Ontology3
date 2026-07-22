import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router";

import { ApiError, getProjectRiskDetail, getProjectSituation } from "../../api/client";
import type { ProjectRiskDetail, ProjectSituation } from "../../api/generated";
import {
  epistemicStatusLabel,
  evidenceLimitationLabel,
  inferenceBasisLabel,
  postureDimensionLabel,
  rankingReasonLabel,
  riskLevelLabel,
  riskStatusLabel,
  stateLabel,
  stepDistance,
} from "./projectPresentation";

export function ProjectRiskDetailPage() {
  const { projectId = "", riskId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedStep = parseStep(searchParams.get("at_step"));
  const riskQuery = useQuery({
    queryKey: ["project-risk-detail", projectId, riskId, selectedStep ?? "current"],
    queryFn: () => getProjectRiskDetail(projectId, riskId, selectedStep),
    enabled: Boolean(projectId && riskId),
  });
  const situationQuery = useQuery({
    queryKey: ["project-situation", projectId, selectedStep ?? "current"],
    queryFn: () => getProjectSituation(projectId, selectedStep),
    enabled: Boolean(projectId),
  });

  function selectStep(step: number | undefined) {
    const next = new URLSearchParams(searchParams);
    if (step === undefined || step === situationQuery.data?.current_step) next.delete("at_step");
    else next.set("at_step", String(step));
    setSearchParams(next);
  }

  if (riskQuery.isPending || situationQuery.isPending) {
    return (
      <main className="app-shell project-situation-shell risk-detail-shell" id="main-content" tabIndex={-1}>
        <p role="status">Risk의 근거와 대응 경로를 재구성하는 중…</p>
        <div className="project-situation-skeleton" aria-hidden="true" />
      </main>
    );
  }

  if (riskQuery.isError || situationQuery.isError) {
    return (
      <RiskDetailError
        error={riskQuery.error ?? situationQuery.error}
        selectedStep={selectedStep}
        projectId={projectId}
        onRetry={() => void Promise.all([riskQuery.refetch(), situationQuery.refetch()])}
        onCurrent={() => selectStep(undefined)}
      />
    );
  }

  const detail = riskQuery.data;
  const situation = situationQuery.data;
  const historical = detail.reconstructed_at_step !== situation.current_step;
  const returnStep = historical ? detail.reconstructed_at_step : undefined;

  return (
    <main className="app-shell project-situation-shell risk-detail-shell" id="main-content" tabIndex={-1}>
      <nav className="project-breadcrumb" aria-label="Risk 탐색">
        <Link className="back-link" to="/projects">과제 포트폴리오</Link>
        <span aria-hidden="true">/</span>
        <Link className="back-link" to={projectSituationPath(projectId, returnStep)}>과제 상황</Link>
        <span aria-hidden="true">/</span>
        <span>Risk 상세</span>
      </nav>

      <header className="risk-detail-hero">
        <div>
          <div className="project-chip-row">
            <span className="risk-level-chip" data-level={detail.risk.risk_level}>
              우선순위 {detail.risk.rank} · {riskLevelLabel(detail.risk.risk_level)}
            </span>
            <span className="project-stage-chip">{riskStatusLabel(detail.risk.status)}</span>
            <span className="epistemic-chip" data-status={detail.epistemic_status}>
              {epistemicStatusLabel(detail.epistemic_status)}
            </span>
            {historical ? <span className="history-chip">과거 상태</span> : null}
          </div>
          <p className="section-kicker">{situation.title_ko}</p>
          <h1>{detail.risk.statement}</h1>
          <p>Step {detail.reconstructed_at_step}에서 확인 가능한 정보만으로 Risk의 인과와 대응을 추적합니다.</p>
        </div>
        <label className="project-step-selector">
          <span>관찰 시점</span>
          <select
            value={historical ? String(detail.reconstructed_at_step) : "current"}
            onChange={(event) => selectStep(event.target.value === "current" ? undefined : Number(event.target.value))}
          >
            <option value="current">현재 Step {situation.current_step}</option>
            {Array.from({ length: situation.current_step }, (_, index) => situation.current_step - index - 1).map((step) => (
              <option value={step} key={step}>Step {step}</option>
            ))}
          </select>
        </label>
      </header>

      {historical ? (
        <aside className="historical-project-notice">
          <strong>선택한 Step 당시 Risk</strong>
          <span>Step {detail.reconstructed_at_step} 이후의 Event, Evidence, Decision과 Action은 표시하지 않습니다.</span>
          <button className="secondary-button" type="button" onClick={() => selectStep(undefined)}>현재 시점 보기</button>
        </aside>
      ) : null}

      <nav className="risk-trace-guide" aria-label="Risk 추적 순서">
        <a href="#risk-source"><b>1</b><span>발생 근거</span></a>
        <a href="#risk-inference"><b>2</b><span>추론·우선순위</span></a>
        <a href="#risk-impact"><b>3</b><span>개발 영향</span></a>
        <a href="#risk-treatment"><b>4</b><span>Decision·Action</span></a>
      </nav>

      <SourceSection detail={detail} />
      <InferenceSection detail={detail} />
      <ImpactSection detail={detail} />
      <TreatmentSection detail={detail} situation={situation} returnStep={returnStep} />
    </main>
  );
}

function SourceSection({ detail }: { detail: ProjectRiskDetail }) {
  const hasSources = detail.source_issues.length + detail.source_events.length + detail.source_evidence.length + detail.cross_project_sources.length > 0;
  return (
    <section className="project-section risk-trace-section" id="risk-source" aria-labelledby="risk-source-heading">
      <TraceHeading number="1" kicker="발생 근거" title="이 Risk는 어디에서 나왔는가" id="risk-source-heading" />
      {hasSources ? (
        <div className="risk-evidence-grid">
          {detail.source_issues.map((issue) => (
            <article key={issue.issue_id}>
              <span>관측된 Issue</span>
              <h3>{issue.title}</h3>
              <p><b>{stateLabel(issue.status)}</b> · 연결 근거 {issue.source_refs.length}개</p>
              <small translate="no">{issue.issue_id}</small>
            </article>
          ))}
          {detail.source_events.map((event) => (
            <article key={event.event_id}>
              <span>개발 Event</span>
              <h3>{event.summary}</h3>
              <p>Step {event.observed_at_step} 관측</p>
              <small translate="no">{event.event_id}</small>
            </article>
          ))}
          {detail.source_evidence.map((evidence) => (
            <article key={evidence.evidence_id}>
              <span>Evidence</span>
              <h3>{evidence.title}</h3>
              <p><b>{stateLabel(evidence.status)}</b>{evidence.available_at_step === null ? " · 아직 미확보" : ` · Step ${evidence.available_at_step} 확보`}</p>
              {evidence.limitations.length > 0 ? <p className="evidence-limitation">한계: {evidence.limitations.map(evidenceLimitationLabel).join(" · ")}</p> : null}
              <small translate="no">{evidence.evidence_id}</small>
            </article>
          ))}
          {detail.cross_project_sources.map((source) => (
            <article className="cross-project-source" key={source.source_id}>
              <span>다른 과제의 학습</span>
              <h3>{source.lesson}</h3>
              <p>Step {source.available_at_step}부터 사용 가능한 유사 Event</p>
              <small translate="no">{source.source_project_id} · {source.source_event_id}</small>
            </article>
          ))}
        </div>
      ) : <p className="empty-state-copy">이 Step에서 확인 가능한 직접 근거가 없습니다. 근거 없이 원인을 확정하지 않습니다.</p>}
    </section>
  );
}

function InferenceSection({ detail }: { detail: ProjectRiskDetail }) {
  const dimensions = [
    ["실패 영향", detail.downside],
    ["영향 범위", detail.blast_radius],
    ["긴급도", detail.urgency],
    ["가역성", detail.reversibility],
  ];
  return (
    <section className="project-section risk-trace-section" id="risk-inference" aria-labelledby="risk-inference-heading">
      <TraceHeading number="2" kicker="추론과 우선순위" title="근거에서 무엇을 추론했고 왜 먼저 보는가" id="risk-inference-heading" />
      <div className="risk-inference-layout">
        <article className="inference-basis-card">
          <span className="epistemic-chip" data-status={detail.epistemic_status}>{epistemicStatusLabel(detail.epistemic_status)}</span>
          <h3>추론 근거</h3>
          {detail.inference_basis.length > 0 ? (
            <ul>{detail.inference_basis.map((basis) => (
              <li key={basis}>
                <span>{inferenceBasisLabel(basis)}</span>
                {inferenceBasisLabel(basis) !== basis ? <small translate="no">{basis}</small> : null}
              </li>
            ))}</ul>
          ) : <p>명시된 추론 근거가 없습니다.</p>}
        </article>
        <div className="risk-posture-grid">
          {dimensions.map(([label, value]) => (
            <div key={label}><span>{label}</span><strong>{postureDimensionLabel(value)}</strong></div>
          ))}
        </div>
      </div>
      <div className="priority-reasons">
        <h3>우선순위 판정 이유</h3>
        <ol>{detail.risk.ranking_reasons.map((reason) => <li key={reason}>{rankingReasonLabel(reason)}</li>)}</ol>
      </div>
      {detail.risk.missing_evidence_ids.length > 0 ? (
        <aside className="missing-evidence">
          <strong>판단 후에도 남는 불확실성</strong>
          <span>아직 확보되지 않은 Evidence: <b translate="no">{detail.risk.missing_evidence_ids.join(" · ")}</b></span>
        </aside>
      ) : null}
    </section>
  );
}

function ImpactSection({ detail }: { detail: ProjectRiskDetail }) {
  return (
    <section className="project-section risk-trace-section" id="risk-impact" aria-labelledby="risk-impact-heading">
      <TraceHeading number="3" kicker="개발 영향" title="어떤 작업과 기준점이 영향을 받는가" id="risk-impact-heading" />
      {detail.affected_objects.length > 0 ? (
        <div className="risk-impact-list">
          {detail.affected_objects.map((object) => (
            <article key={`${object.object_type}-${object.object_id}`}>
              <span>{object.object_type === "WORK_ITEM" ? "개발 작업" : "기준점"}</span>
              <h3>{object.title}</h3>
              <p className="state-chip" data-state={object.state}>{stateLabel(object.state)}</p>
              <small translate="no">{object.object_id}</small>
            </article>
          ))}
        </div>
      ) : <p className="empty-state-copy">직접 연결된 작업 또는 기준점이 없습니다.</p>}
    </section>
  );
}

function TreatmentSection({
  detail,
  situation,
  returnStep,
}: {
  detail: ProjectRiskDetail;
  situation: ProjectSituation;
  returnStep: number | undefined;
}) {
  const evidenceTitles = new Map(situation.evidence.map((item) => [item.evidence_id, item.title]));
  return (
    <section className="project-section risk-trace-section risk-treatment-section" id="risk-treatment" aria-labelledby="risk-treatment-heading">
      <TraceHeading number="4" kicker="위험 처리" title="어떤 Decision과 Action으로 위험을 제한하는가" id="risk-treatment-heading" />
      <div className="risk-treatment-grid">
        <div>
          <h3>연결된 Decision</h3>
          {detail.decisions.length > 0 ? detail.decisions.map((decision) => (
            <article className="decision-treatment-card" key={decision.case_id}>
              <span className="state-chip" data-state={decision.status}>{stateLabel(decision.status)}</span>
              <h4>{decision.title}</h4>
              <p>이 Risk의 trade-off와 안전 조건을 검토합니다.</p>
              <Link className="primary-button recovery-link" to={decisionPath(decision.href, detail.project_id, detail.risk.risk_id, returnStep)}>
                Decision 검토 열기
              </Link>
            </article>
          )) : <p className="empty-state-copy">이 Step에서 연결된 Decision이 없습니다.</p>}
        </div>
        <div>
          <h3>실행·검증 Action</h3>
          {detail.treatment_actions.length > 0 ? detail.treatment_actions.map((action) => (
            <article className="action-treatment-card" key={action.action_id}>
              <span className="state-chip" data-state={action.status}>{stateLabel(action.status)}</span>
              <h4>{action.title}</h4>
              <dl>
                <div><dt>기한</dt><dd>Step {action.due_at_step} · {stepDistance(action.due_at_step, detail.reconstructed_at_step)}</dd></div>
                <div><dt>검증</dt><dd>{action.verification_evidence_ids.map((id) => evidenceTitles.get(id) ?? id).join(" · ") || "검증 Evidence 미지정"}</dd></div>
                <div><dt>중단·복귀</dt><dd>{action.rollback_condition ?? "명시된 rollback 조건 없음"}</dd></div>
              </dl>
            </article>
          )) : <p className="empty-state-copy">이 Step에서 연결된 실행 Action이 없습니다.</p>}
        </div>
      </div>
    </section>
  );
}

function TraceHeading({ number, kicker, title, id }: { number: string; kicker: string; title: string; id: string }) {
  return (
    <header className="project-section-header risk-trace-heading">
      <b aria-hidden="true">{number}</b>
      <div><p className="section-kicker">{kicker}</p><h2 id={id}>{title}</h2></div>
    </header>
  );
}

function RiskDetailError({
  error,
  selectedStep,
  projectId,
  onRetry,
  onCurrent,
}: {
  error: unknown;
  selectedStep: number | undefined;
  projectId: string;
  onRetry: () => void;
  onCurrent: () => void;
}) {
  const unavailableStep = error instanceof ApiError && error.code === "PROJECT_STEP_OUT_OF_RANGE";
  const missingRisk = error instanceof ApiError && ["PROJECT_RISK_NOT_FOUND", "PROJECT_NOT_FOUND"].includes(error.code ?? "");
  return (
    <main className="app-shell project-situation-shell risk-detail-shell" id="main-content" tabIndex={-1}>
      <section className="list-feedback" role="alert">
        <h1>{unavailableStep ? `선택한 Step ${selectedStep}의 Risk를 재구성할 수 없습니다` : missingRisk ? "Risk를 찾을 수 없습니다" : "Risk 상세를 불러오지 못했습니다"}</h1>
        <p>{unavailableStep ? "이후 정보를 섞지 않기 위해 해당 시점의 인과 경로를 표시하지 않았습니다." : "불완전한 인과 경로는 표시하지 않았습니다. 연결 상태를 확인한 뒤 다시 시도하세요."}</p>
        <div className="recovery-actions">
          {unavailableStep ? <button className="primary-button" type="button" onClick={onCurrent}>현재 시점 보기</button> : <button className="primary-button" type="button" onClick={onRetry}>다시 시도</button>}
          <Link className="secondary-button recovery-link" to={`/projects/${encodeURIComponent(projectId)}`}>과제 상황으로 돌아가기</Link>
        </div>
      </section>
    </main>
  );
}

function decisionPath(href: string, projectId: string, riskId: string, projectStep?: number) {
  const query = new URLSearchParams({ from_project: projectId, from_risk: riskId });
  if (projectStep !== undefined) query.set("from_project_step", String(projectStep));
  return `${href}${href.includes("?") ? "&" : "?"}${query}`;
}

function projectSituationPath(projectId: string, atStep?: number) {
  const query = atStep === undefined ? "" : `?${new URLSearchParams({ at_step: String(atStep) })}`;
  return `/projects/${encodeURIComponent(projectId)}${query}`;
}

function parseStep(value: string | null) {
  if (value === null) return undefined;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : undefined;
}
