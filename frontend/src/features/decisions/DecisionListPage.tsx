import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { getDecisionCases } from "../../api/client";

export function DecisionListPage() {
  const query = useQuery({ queryKey: ["decision-cases"], queryFn: getDecisionCases });

  return (
    <main className="app-shell">
      <header className="page-header">
        <div>
          <p className="eyebrow">Synthetic fixture · Replay</p>
          <h1>결정 목록</h1>
          <p>지금 검토할 결정과 기한을 확인하세요.</p>
        </div>
        <Link className="secondary-link" to="/dev/fixtures">
          Fixture 관리
        </Link>
      </header>
      {query.isPending && <p role="status">결정 목록을 불러오는 중…</p>}
      {query.isError && <p role="alert">{query.error.message}</p>}
      {query.data?.length === 0 && <p>등록된 결정이 없습니다.</p>}
      <section className="case-grid" aria-label="결정 목록">
        {query.data?.map((item) => (
          <article className="case-card" key={item.case_id}>
            <p className="status-chip">{item.case_status}</p>
            <h2>{item.title_ko}</h2>
            <p>{item.decision_question}</p>
            <dl>
              <div>
                <dt>결정 기한</dt>
                <dd>{item.deadline_milestone_id}</dd>
              </div>
              <div>
                <dt>Blocker</dt>
                <dd>{item.tracks.reduce((total, track) => total + track.blocker_count, 0)}개</dd>
              </div>
            </dl>
            <Link className="primary-link" to={`/decisions/${item.case_id}`}>
              결정 검토
            </Link>
          </article>
        ))}
      </section>
    </main>
  );
}

