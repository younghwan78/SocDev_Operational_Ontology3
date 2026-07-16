import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
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

const decisionListItem = {
  projection_schema_version: "decision-list-item.v1",
  case_id: "CASE-VR-001",
  title_ko: "UHD60 EIS 전력 여유 검토",
  decision_question: "UHD60 EIS를 제한 조건으로 진행할 것인가?",
  case_status: "DECISION_REQUIRED",
  current_state_ko: "결정 필요",
  group: "ACTION_REQUIRED",
  group_label_ko: "지금 확인할 결정",
  deadline: {
    milestone_title: "Architecture Freeze",
    at_step: 13,
    remaining_steps: 1,
    attention: "DUE_SOON",
    label_ko: "1 Step 남음",
  },
  why_now_ko: "Architecture Freeze까지 1 Step 남았습니다. HW 검토가 방향 결정을 기다립니다.",
  blocker: {
    blocker_count: 1,
    critical_track_name: "Architecture",
    critical_work_item_title: "EIS 구현 option 결정",
    downstream_work_item_titles: ["HW carry-over 가능성 검토"],
    impacted_milestone_titles: ["RTL Freeze"],
    summary_ko: "EIS 구현 option 결정이 HW carry-over 가능성 검토를 막고 있습니다.",
  },
  next_action: "OPEN_DECISION",
  next_action_ko: "결정 검토",
  stale: false,
  simulated: true,
};

const timelineItem = {
  projection_schema_version: "development-timeline.v1",
  case_id: "CASE-VR-001",
  aggregate_version: 1,
  current_step: 12,
  reconstructed_at_step: 12,
  work_items: [],
  milestones: [],
  evidence: [],
  actions: [],
  events: [],
  blocker_propagations: [],
};

function workspaceResponse(input: RequestInfo | URL) {
  const url = String(input);
  const payload = url.includes("/timeline") ? timelineItem : caseItem;
  return Promise.resolve(new Response(JSON.stringify(payload), { status: 200 }));
}

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

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("App", () => {
  it("shows the Korean decision list", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([decisionListItem]), { status: 200 }),
    );
    renderApp();
    expect(await screen.findByRole("heading", { name: "결정 목록" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "지금 확인할 결정" })).toBeInTheDocument();
    expect(await screen.findByText("UHD60 EIS 전력 여유 검토")).toBeInTheDocument();
    expect(screen.getByText("1 Step 남음")).toBeInTheDocument();
    expect(screen.getByText(decisionListItem.why_now_ko)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "결정 검토" })).toBeInTheDocument();
    expect(screen.queryByText("CASE-VR-001")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Fixture 관리" })).not.toBeInTheDocument();
  });

  it("explains an empty decision inbox", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 }),
    );
    renderApp();

    expect(
      await screen.findByRole("heading", { name: "현재 검토할 결정이 없습니다" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/새로운 결정이 준비되면/)).toBeInTheDocument();
  });

  it("offers a retry when the decision inbox fails", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response("service unavailable", { status: 503 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify([decisionListItem]), { status: 200 }),
      );
    renderApp();
    const user = userEvent.setup();

    expect(
      await screen.findByRole("heading", { name: "결정 목록을 불러오지 못했습니다" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(await screen.findByText(decisionListItem.decision_question)).toBeInTheDocument();
  });

  it("shows a decision workspace without raw ontology", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(workspaceResponse);
    renderApp("/decisions/CASE-VR-001");
    expect(await screen.findByRole("heading", { name: "현재 개발 상황" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "개발 진행 타임라인" })).toBeInTheDocument();
    expect(screen.getByText("기록된 개발 변경 없음")).toBeInTheDocument();
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
      return workspaceResponse(_input);
    });
    renderApp("/decisions/CASE-VR-001");
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "역할 검토 시작" }));

    expect(await screen.findByRole("heading", { name: "개발 상태가 변경되었습니다" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "최신 상태 불러오기" })).toBeInTheDocument();
  });
});
