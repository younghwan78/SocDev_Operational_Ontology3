import { Link } from "react-router";

export function FixturePage() {
  return (
    <main className="app-shell">
      <Link className="back-link" to="/decisions">← 결정 목록</Link>
      <p className="eyebrow">개발자 전용</p>
      <h1>Fixture 및 평가 관리</h1>
      <p>8개 synthetic case의 contract, hash manifest와 Replay 결과를 관리합니다.</p>
      <p className="notice">Hidden fixture는 이 화면과 HTTP API에서 조회할 수 없습니다.</p>
    </main>
  );
}

