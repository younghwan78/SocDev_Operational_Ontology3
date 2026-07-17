import { Navigate, Route, Routes } from "react-router";

import { DecisionListPage } from "../features/decisions/DecisionListPage";
import { DecisionWorkspacePage } from "../features/decisions/DecisionWorkspacePage";
import { FixturePage } from "../features/fixtures/FixturePage";

export function App() {
  return (
    <>
      <a className="skip-link" href="#main-content">본문으로 건너뛰기</a>
      <Routes>
        <Route path="/" element={<Navigate to="/decisions" replace />} />
        <Route path="/decisions" element={<DecisionListPage />} />
        <Route path="/decisions/:caseId" element={<DecisionWorkspacePage />} />
        <Route path="/dev/fixtures" element={<FixturePage />} />
      </Routes>
    </>
  );
}
