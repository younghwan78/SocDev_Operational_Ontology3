import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { getDecisionCases } from "../../api/client";
import type { DecisionListItem } from "../../api/generated";

type DecisionGroup = {
  key: DecisionListItem["group"];
  label: string;
  items: DecisionListItem[];
};

export function DecisionListPage() {
  const query = useQuery({ queryKey: ["decision-cases"], queryFn: getDecisionCases });
  const groups = query.data ? groupInApiOrder(query.data) : [];

  return (
    <main className="app-shell decision-list-shell" id="main-content" tabIndex={-1}>
      <header className="decision-list-header">
        <Link className="back-link" to="/projects">← 과제 포트폴리오</Link>
        <p className="eyebrow">합성 데이터 · 가상 판단</p>
        <h1>결정 목록</h1>
        <p className="page-lead">
          기한과 개발 영향을 기준으로 지금 확인할 결정을 먼저 보여줍니다.
        </p>
      </header>

      {query.isPending ? <DecisionListLoading /> : null}

      {query.isError ? (
        <section className="list-feedback" role="alert">
          <h2>결정 목록을 불러오지 못했습니다</h2>
          <p>현재 개발 상태를 확인할 수 없습니다. 잠시 후 다시 시도하세요.</p>
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
          <h2>현재 검토할 결정이 없습니다</h2>
          <p>새로운 결정이 준비되면 기한과 다음 행동이 여기에 표시됩니다.</p>
        </section>
      ) : null}

      {groups.length > 0 ? (
        <div className="decision-groups">
          {groups.map((group) => (
            <section
              className="decision-group"
              aria-labelledby={`decision-group-${group.key}`}
              key={group.key}
            >
              <header className="decision-group-header">
                <div>
                  <h2 id={`decision-group-${group.key}`}>{group.label}</h2>
                  <p>{groupDescription(group.key)}</p>
                </div>
                <p className="group-count" aria-label={`${group.items.length}건`}>
                  {group.items.length}건
                </p>
              </header>
              <div className="decision-card-list">
                {group.items.map((item) => (
                  <DecisionCard item={item} key={item.case_id} />
                ))}
              </div>
            </section>
          ))}
        </div>
      ) : null}
    </main>
  );
}

function DecisionCard({ item }: { item: DecisionListItem }) {
  const milestoneImpact = (item.blocker.impacted_milestone_titles ?? []).join(", ");
  return (
    <article className="decision-card" data-attention={item.deadline.attention}>
      <div className="decision-card-meta">
        <span className="attention-chip" data-attention={item.deadline.attention}>
          {item.deadline.label_ko}
        </span>
        <span className="simulation-label">가상 판단</span>
      </div>

      <p className="decision-context">{item.title_ko}</p>
      <h3>{item.decision_question}</h3>

      <div className="why-now">
        <p className="why-now-label">왜 지금</p>
        <p>{item.why_now_ko}</p>
      </div>

      <Link className="decision-card-action" to={`/decisions/${item.case_id}`}>
        {item.next_action_ko}
        <span aria-hidden="true">→</span>
      </Link>

      <dl className="decision-card-details">
        <div>
          <dt>현재 상태</dt>
          <dd>{item.current_state_ko}</dd>
        </div>
        <div>
          <dt>막힌 개발</dt>
          <dd>{item.blocker.summary_ko}</dd>
        </div>
        <div>
          <dt>영향 기준점</dt>
          <dd>{milestoneImpact || item.deadline.milestone_title}</dd>
        </div>
      </dl>
    </article>
  );
}

function DecisionListLoading() {
  return (
    <section className="decision-list-loading" aria-labelledby="decision-list-loading-label">
      <p id="decision-list-loading-label" role="status">
        결정 목록을 불러오는 중…
      </p>
      <div className="decision-card-list" aria-hidden="true">
        {[0, 1, 2].map((item) => (
          <div className="decision-card decision-card-skeleton" key={item} />
        ))}
      </div>
    </section>
  );
}

function groupInApiOrder(items: DecisionListItem[]): DecisionGroup[] {
  const grouped = new Map<DecisionListItem["group"], DecisionGroup>();
  for (const item of items) {
    const current = grouped.get(item.group);
    if (current) {
      current.items.push(item);
    } else {
      grouped.set(item.group, {
        key: item.group,
        label: item.group_label_ko,
        items: [item],
      });
    }
  }
  return [...grouped.values()];
}

function groupDescription(group: DecisionListItem["group"]) {
  if (group === "ACTION_REQUIRED") return "기한과 막힌 개발을 확인하고 다음 판단을 시작하세요.";
  if (group === "IN_REVIEW") return "역할별 검토가 진행 중이거나 결과 확인을 기다립니다.";
  if (group === "ACTION_AND_OBSERVATION") return "결정 후 action과 guardrail을 추적합니다.";
  return "결정 과정과 결과에서 재사용할 학습을 확인합니다.";
}
