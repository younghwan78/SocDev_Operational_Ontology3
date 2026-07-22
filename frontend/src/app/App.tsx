import { Navigate, Route, Routes } from "react-router";

import { DecisionListPage } from "../features/decisions/DecisionListPage";
import { DecisionWorkspacePage } from "../features/decisions/DecisionWorkspacePage";
import { FixturePage } from "../features/fixtures/FixturePage";
import { ProjectPortfolioPage } from "../features/projects/ProjectPortfolioPage";
import { ProjectRiskDetailPage } from "../features/projects/ProjectRiskDetailPage";
import { ProjectSituationPage } from "../features/projects/ProjectSituationPage";

export function App() {
  return (
    <>
      <a className="skip-link" href="#main-content">본문으로 건너뛰기</a>
      <Routes>
        <Route path="/" element={<Navigate to="/projects" replace />} />
        <Route path="/projects" element={<ProjectPortfolioPage />} />
        <Route path="/projects/:projectId" element={<ProjectSituationPage />} />
        <Route path="/projects/:projectId/risks/:riskId" element={<ProjectRiskDetailPage />} />
        <Route path="/decisions" element={<DecisionListPage />} />
        <Route path="/decisions/:caseId" element={<DecisionWorkspacePage />} />
        <Route path="/dev/fixtures" element={<FixturePage />} />
      </Routes>
    </>
  );
}
