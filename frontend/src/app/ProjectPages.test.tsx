import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ProjectListItem, ProjectRiskSummary, ProjectSituation, ProjectTimeline } from "../api/generated";
import { App } from "./App";

const topRisk = {
  projection_schema_version: "project-risk-summary.v1",
  project_id: "PROJECT-V",
  risk_id: "RISK-V-WRONG-COMMIT",
  statement: "불완전한 모델로 HW 방향을 확정하면 silicon 수정 비용이 커질 수 있습니다.",
  status: "TREATING",
  risk_level: "CRITICAL",
  rank: 1,
  policy_version: "project-risk-order.v1",
  ranking_reasons: ["DOWNSIDE_SEVERE", "URGENCY_BEFORE_MILESTONE", "IRREVERSIBLE_COMMITMENT"],
  source_refs: ["EVD-V-PRESI-MODEL", "EVENT-V-018-MODEL-ARRIVED", "ISSUE-V-INTERFACE"],
  affected_work_item_ids: ["WORK-V-HW-PATH", "WORK-V-PRESI-VERIFY"],
  affected_milestone_ids: ["M-V-ARCH-FREEZE"],
  treatment_decision_case_ids: ["CASE-HO-002"],
  treatment_action_ids: ["ACTION-V-BOUNDED-CHANGE"],
  missing_evidence_ids: ["EVD-V-SILICON-CORR"],
} satisfies ProjectRiskSummary;

const projectList = [{
  projection_schema_version: "project-list-item.v1",
  project_id: "PROJECT-V",
  title_ko: "차세대 Multimedia SoC Pre-silicon HW Closure",
  lifecycle_stage: "PRE_SILICON_CLOSURE",
  aggregate_version: 1,
  current_step: 22,
  attention: "BLOCKED",
  attention_policy_version: "project-attention.v1",
  attention_reasons: [{ code: "WORK_ITEM_BLOCKED", summary_ko: "현재 진행을 막는 작업이 1개 있습니다.", source_refs: ["WORK-V-PRESI-VERIFY"] }],
  active_issue_count: 1,
  active_risk_count: 2,
  blocked_work_item_count: 1,
  nearest_milestone_id: "M-V-ARCH-FREEZE",
  nearest_milestone_step: 24,
  top_risks: [topRisk],
}] satisfies ProjectListItem[];

const projectSituation = {
  projection_schema_version: "project-situation.v1",
  project_id: "PROJECT-V",
  title_ko: projectList[0].title_ko,
  lifecycle_stage: "PRE_SILICON_CLOSURE",
  fixture_version: 1,
  aggregate_version: 1,
  current_step: 22,
  reconstructed_at_step: 22,
  attention: "BLOCKED",
  attention_policy_version: "project-attention.v1",
  attention_reasons: projectList[0].attention_reasons,
  tracks: [
    { track_id: "TRACK-V-HW", name: "Power Architecture", status: "IN_PROGRESS", blocked_work_item_count: 0, next_milestone_id: "M-V-ARCH-FREEZE" },
    { track_id: "TRACK-V-VERIF", name: "Pre-silicon Verification", status: "BLOCKED", blocked_work_item_count: 1, next_milestone_id: "M-V-ARCH-FREEZE" },
  ],
  work_items: [
    { work_item_id: "WORK-V-HW-PATH", track_id: "TRACK-V-HW", title: "전력 경로 설계 closure", status: "IN_PROGRESS", blocker: null, planned_at_step: 23, dependency_ids: [] },
    { work_item_id: "WORK-V-PRESI-VERIFY", track_id: "TRACK-V-VERIF", title: "대표 workload 사전 검증", status: "BLOCKED", blocker: "공용 emulator 자원 충돌", planned_at_step: 24, dependency_ids: ["WORK-V-HW-PATH"] },
  ],
  milestones: [{ milestone_id: "M-V-ARCH-FREEZE", title: "HW Architecture Freeze", kind: "GATE", status: "AT_RISK", planned_at_step: 24, remaining_steps: 2, commitment_at_step: 23 }],
  issues: [{ issue_id: "ISSUE-V-INTERFACE", title: "전력 제어 경로의 HW/firmware interface 불일치", status: "MITIGATING", observed_at_step: 18, source_refs: ["EVD-V-PRESI-MODEL"], affected_work_item_ids: ["WORK-V-HW-PATH"], affected_milestone_ids: ["M-V-ARCH-FREEZE"] }],
  risks: [topRisk],
  evidence: [
    { evidence_id: "EVD-V-PRESI-MODEL", title: "대표 경로 전력 pre-silicon model 결과", evidence_type: "presilicon_model", status: "RECEIVED", expected_at_step: 18, available_at_step: 18, source_ref: "FIXTURE:MODEL", limitations: ["field correlation 없음"] },
    { evidence_id: "EVD-V-SILICON-CORR", title: "first silicon 상관 분석", evidence_type: "silicon_measurement", status: "REQUESTED", expected_at_step: 28, available_at_step: null, source_ref: null, limitations: ["silicon 미확보"] },
  ],
  decision_case_refs: [{ case_id: "CASE-HO-002", title: "Silicon 변경 비용과 비가역성 검토", status: "DECISION_REQUIRED", treated_risk_ids: ["RISK-V-WRONG-COMMIT"], href: "/decisions/CASE-HO-002" }],
} satisfies ProjectSituation;

const projectTimeline = {
  projection_schema_version: "project-timeline.v1",
  project_id: "PROJECT-V",
  aggregate_version: 1,
  current_step: 22,
  reconstructed_at_step: 22,
  attention: "BLOCKED",
  events: [{
    event_id: "EVENT-V-018-MODEL-ARRIVED",
    event_type: "EVIDENCE_RECEIVED",
    effective_at_step: 17,
    observed_at_step: 18,
    summary: "Pre-silicon model 결과가 도착했습니다.",
    cause: "대표 workload 검증 결과 등록",
    affected_entity_ids: ["WORK-V-HW-PATH"],
    impacted_milestone_ids: ["M-V-ARCH-FREEZE"],
  }],
} satisfies ProjectTimeline;

function projectResponse(input: RequestInfo | URL) {
  const url = String(input);
  if (url.includes("/timeline")) return response(projectTimeline);
  if (url.includes("/situation")) {
    const historical = url.includes("at_step=20");
    return response({ ...projectSituation, reconstructed_at_step: historical ? 20 : 22 });
  }
  return response(projectList);
}

function response(payload: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json" } }));
}

function renderApp(path = "/projects") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <App />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="test-location" hidden>{location.pathname}{location.search}</output>;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("Project Operations pages", () => {
  it("opens the portfolio first and preserves backend priority with its reason", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(projectResponse);
    renderApp("/");

    expect(await screen.findByRole("heading", { name: "개발 과제 현황" })).toBeInTheDocument();
    expect(await screen.findByText("현재 진행을 막는 작업이 1개 있습니다.")).toBeInTheDocument();
    expect(screen.getByText(topRisk.statement)).toBeInTheDocument();
    expect(screen.getByText("근거 3개 · 영향 작업 2개")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /과제 상황 보기/ })).toHaveAttribute("href", "/projects/PROJECT-V");
    expect(screen.getByTestId("test-location")).toHaveTextContent("/projects");
  });

  it("explains the top risk through visible Issue, Evidence, Event and affected work", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(projectResponse);
    renderApp("/projects/PROJECT-V");

    expect(await screen.findByRole("heading", { name: "가장 먼저 볼 Risk와 그 근거" })).toBeInTheDocument();
    expect(screen.getByText("실패 영향이 큼")).toBeInTheDocument();
    expect(screen.getAllByText("전력 제어 경로의 HW/firmware interface 불일치")).toHaveLength(2);
    expect(screen.getAllByText("대표 경로 전력 pre-silicon model 결과")).toHaveLength(2);
    expect(screen.getAllByText("Pre-silicon model 결과가 도착했습니다.")).toHaveLength(2);
    expect(screen.getByText("전력 경로 설계 closure · 대표 workload 사전 검증")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Decision|결정 검토/ })).not.toBeInTheDocument();
  });

  it("keeps a historical project Step in the URL and returns to current state", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(projectResponse);
    renderApp("/projects/PROJECT-V");
    const user = userEvent.setup();

    await user.selectOptions(await screen.findByLabelText("관찰 시점"), "20");
    expect(await screen.findByText("선택한 Step 당시 상태")).toBeInTheDocument();
    expect(screen.getByTestId("test-location")).toHaveTextContent("?at_step=20");
    await user.click(screen.getByRole("button", { name: "현재 시점 보기" }));
    expect(await screen.findByText("Step 22 기준 · Project 상태와 근거를 함께 봅니다.")).toBeInTheDocument();
    expect(screen.getByTestId("test-location")).toHaveTextContent("/projects/PROJECT-V");
  });

  it("recovers an unavailable historical project Step without leaking future state", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("at_step=99")) return response({ detail: { code: "PROJECT_STEP_OUT_OF_RANGE" } }, 422);
      return projectResponse(input);
    });
    renderApp("/projects/PROJECT-V?at_step=99");
    const user = userEvent.setup();

    expect(await screen.findByRole("heading", { name: "선택한 Step 99의 과제 상태를 재구성할 수 없습니다" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "현재 시점 보기" }));
    expect(await screen.findByRole("heading", { name: projectSituation.title_ko })).toBeInTheDocument();
    expect(screen.getByTestId("test-location")).toHaveTextContent("/projects/PROJECT-V");
  });
});
