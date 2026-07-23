import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { getProjects } from "../../api/client";
import type { ProjectListItem } from "../../api/generated";
import {
  attentionLabel,
  lifecycleLabel,
  riskLevelLabel,
  riskStatusLabel,
  stepDistance,
} from "./projectPresentation";

export function ProjectPortfolioPage() {
  const query = useQuery({ queryKey: ["projects"], queryFn: getProjects });

  return (
    <main className="app-shell project-portfolio-shell" id="main-content" tabIndex={-1}>
      <header className="project-page-header">
        <div>
          <p className="eyebrow">합성 데이터 · 개발 운영 트윈</p>
          <h1>개발 과제 현황</h1>
          <p className="page-lead">
            막힌 작업, 활성 Risk와 가까운 기준점을 바탕으로 먼저 확인할 과제를 보여줍니다.
          </p>
        </div>
        <Link className="secondary-button recovery-link" to="/decisions">결정 검토 목록</Link>
      </header>

      <aside className="scope-notice" aria-label="데이터 범위">
        <strong>Local PoC</strong>
        <span>실제 Jira·Confluence가 아닌 합성 fixture이며, 판단이나 승인 결과를 쓰지 않습니다.</span>
      </aside>

      {query.isPending ? <ProjectPortfolioLoading /> : null}

      {query.isError ? (
        <section className="list-feedback" role="alert">
          <h2>과제 현황을 불러오지 못했습니다</h2>
          <p>현재 개발 상태를 확인할 수 없습니다. 연결 상태를 확인한 뒤 다시 시도하세요.</p>
          <button
            className="primary-button"
            type="button"
            onClick={() => void query.refetch()}
            disabled={query.isFetching}
          >
            {query.isFetching ? "다시 불러오는 중…" : "다시 시도"}
          </button>
        </section>
      ) : null}

      {query.data?.length === 0 ? (
        <section className="list-feedback">
          <h2>등록된 개발 과제가 없습니다</h2>
          <p>검증된 Project fixture가 준비되면 전체 상태가 여기에 표시됩니다.</p>
        </section>
      ) : null}

      {query.data && query.data.length > 0 ? (
        <section aria-labelledby="portfolio-priority-heading">
          <header className="portfolio-section-heading">
            <div>
              <p className="section-kicker">전체 {query.data.length}개 과제</p>
              <h2 id="portfolio-priority-heading">지금 먼저 확인할 순서</h2>
            </div>
            <p>점수 대신 막힌 작업, Risk와 기준점 근거를 사용합니다.</p>
          </header>
          <div className="project-card-list">
            {query.data.map((project) => <ProjectCard key={project.project_id} project={project} />)}
          </div>
        </section>
      ) : null}
    </main>
  );
}

function ProjectCard({ project }: { project: ProjectListItem }) {
  const topRisk = project.top_risks[0];
  const primaryReason = project.attention_reasons[0];

  return (
    <article className="project-card" data-attention={project.attention}>
      <header className="project-card-header">
        <div>
          <div className="project-chip-row">
            <span className="project-attention-chip" data-attention={project.attention}>
              {attentionLabel(project.attention)}
            </span>
            <span className="project-stage-chip">{lifecycleLabel(project.lifecycle_stage)}</span>
          </div>
          <h3>{project.title_ko}</h3>
          <p className="project-step">현재 Step {project.current_step}</p>
        </div>
        <Link className="project-open-link" to={`/projects/${project.project_id}`}>
          과제 상황 보기 <span aria-hidden="true">→</span>
        </Link>
      </header>

      <div className="project-why-now">
        <p className="why-now-label">왜 먼저</p>
        <p>{primaryReason.summary_ko}</p>
      </div>

      {topRisk ? (
        <section className="portfolio-top-risk" aria-label={`${project.title_ko} 최상위 위험`}>
          <div className="risk-title-row">
            <p>최상위 Risk</p>
            <span className="risk-level-chip" data-level={topRisk.risk_level}>
              {riskLevelLabel(topRisk.risk_level)} · {riskStatusLabel(topRisk.status)}
            </span>
          </div>
          <strong>{topRisk.statement}</strong>
          <p className="source-count">근거 {topRisk.source_refs.length}개 · 영향 작업 {topRisk.affected_work_item_ids.length}개</p>
        </section>
      ) : (
        <p className="portfolio-no-risk">현재 표시할 활성 Risk가 없습니다.</p>
      )}

      <dl className="project-card-metrics">
        <div><dt>열린 Issue</dt><dd>{project.active_issue_count}</dd></div>
        <div><dt>활성 Risk</dt><dd>{project.active_risk_count}</dd></div>
        <div><dt>막힌 작업</dt><dd>{project.blocked_work_item_count}</dd></div>
        <div>
          <dt>가장 가까운 기준점</dt>
          <dd><span>{project.nearest_milestone_title}</span><small>{stepDistance(project.nearest_milestone_step, project.current_step)}</small></dd>
        </div>
      </dl>
    </article>
  );
}

function ProjectPortfolioLoading() {
  return (
    <section className="project-card-list" aria-labelledby="project-loading-label">
      <p id="project-loading-label" role="status">개발 과제 현황을 불러오는 중…</p>
      {[0, 1, 2].map((item) => <div className="project-card project-card-skeleton" aria-hidden="true" key={item} />)}
    </section>
  );
}
