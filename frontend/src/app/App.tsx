import { Navigate, Route, Routes } from "react-router";

import { DecisionListPage } from "../features/decisions/DecisionListPage";
import { DecisionWorkspacePage } from "../features/decisions/DecisionWorkspacePage";
import { FixturePage } from "../features/fixtures/FixturePage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/decisions" replace />} />
      <Route path="/decisions" element={<DecisionListPage />} />
      <Route path="/decisions/:caseId" element={<DecisionWorkspacePage />} />
      <Route path="/dev/fixtures" element={<FixturePage />} />
    </Routes>
  );
}

