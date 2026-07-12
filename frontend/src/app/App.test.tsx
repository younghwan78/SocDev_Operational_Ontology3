import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const caseItem = {
  projection_schema_version: "decision-workspace.v1",
  case_id: "CASE-VR-001",
  fixture_version: 1,
  aggregate_version: 1,
  title_ko: "UHD60 EIS 전력 여유 검토",
  case_status: "DECISION_REQUIRED",
  current_step: 12,
  decision_question: "UHD60 EIS를 제한 조건으로 진행할 것인가?",
  deadline_milestone_id: "M2-ARCH-FREEZE",
  deadline_title: "Architecture Freeze",
  deadline_step: 13,
  tracks: [{ track_id: "TRACK-ARCH", name: "Architecture", status: "IN_PROGRESS", blocker_count: 1 }],
  alternative_count: 2,
  evidence_count: 2,
  uncertainty_count: 2,
  alternatives: [{ option_id: "OPT-SW-GUARDED", title: "제한 진행", description: "feature flag", reversible: true }],
  blockers: [{ work_item_title: "HW 검토", track_id: "TRACK-HW", blocker: "option 미결정", dependency_ids: [] }],
  eligible_evidence_titles: ["전력 모델"],
  evidence: [{ evidence_id: "EVD-1", title: "전력 모델", evidence_type: "simulation_prediction", source_ref: "FIXTURE:1", available_at_step: 10, eligible_now: true, limitations: ["silicon 미측정"] }],
  claims: [{ claim_id: "CLM-1", statement: "되돌릴 수 있다", epistemic_status: "fact", confidence_level: "high", source_refs: ["EVD-1"] }],
  uncertainties: ["실측 bandwidth"],
};

function renderApp(path = "/decisions") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("App", () => {
  it("shows the Korean decision list", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([caseItem]), { status: 200 }),
    );
    renderApp();
    expect(await screen.findByRole("heading", { name: "결정 목록" })).toBeInTheDocument();
    expect(await screen.findByText("UHD60 EIS 전력 여유 검토")).toBeInTheDocument();
  });

  it("shows a decision workspace without raw ontology", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(caseItem), { status: 200 }),
    );
    renderApp("/decisions/CASE-VR-001");
    expect(await screen.findByRole("heading", { name: "현재 개발 상황" })).toBeInTheDocument();
    expect(screen.queryByText("ontology_relations")).not.toBeInTheDocument();
  });

  it("shows a stale-state recovery action after an aggregate conflict", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (_input, init) => {
      if (init?.method === "POST") {
        return new Response(
          JSON.stringify({ detail: { code: "CASE_VERSION_CONFLICT" } }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(JSON.stringify(caseItem), { status: 200 });
    });
    renderApp("/decisions/CASE-VR-001");
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "역할 검토 시작" }));

    expect(await screen.findByRole("heading", { name: "개발 상태가 변경되었습니다" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "최신 상태 불러오기" })).toBeInTheDocument();
  });
});
