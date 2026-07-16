import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const caseItem = {
  projection_schema_version: "decision-workspace.v2",
  generated_at: "2026-07-17T00:00:00Z",
  aggregate_version: 1,
  case_id: "CASE-VR-001",
  fixture_version: 1,
  stale: false,
  time_context: { current_step: 12, selected_step: 12, mode: "current", earliest_available_step: 9, latest_observable_step: 12, next_expected_evidence_step: 15, commands_allowed_at_selected_step: true },
  header: { title_ko: "UHD60 EIS 전력 여유 검토", decision_question: "UHD60 EIS를 제한 조건으로 진행할 것인가?", workspace_phase: "READY_FOR_REVIEW", case_status: "DECISION_REQUIRED", deadline: { milestone_id: "M2-ARCH-FREEZE", title: "Architecture Freeze", at_step: 13, remaining_steps: 1 }, simulated: true },
  current_brief: { state_or_recommendation_ko: "가상 역할 검토 준비", one_line_reason_ko: "선택지는 준비됐지만 역할별 검토가 필요합니다.", why_now_ko: "Architecture Freeze까지 1 Step 남았습니다.", key_conditions_ko: [], residual_risks_ko: ["실측 bandwidth"] },
  decision_posture: { evidence_state: "partial", reversibility: "high", detectability: "observable_now", recoverability: "high", downside: "medium", blast_radius: "cross_track", urgency: "high", explanations_ko: ["현재 근거는 일부만 준비되었습니다."] },
  development_twin: {
    state_at_selected_step: { reconstructed_at_step: 12, tracks: [{ track_id: "TRACK-ARCH", name: "Architecture", status: "BLOCKED", current_work_item_id: "WORK-ARCH", current_work_item_title: "EIS 구현 option 결정", owner: "ROLE-ARCH", blocker: "DDR 실측 없음", next_milestone_id: "M2-ARCH-FREEZE", next_milestone_title: "Architecture Freeze", next_milestone_step: 13 }], eligible_evidence_ids: ["EVD-1"], unavailable_evidence_ids: [], active_action_ids: [] },
    causal_chains: [{ source_event_id: "DEV-1", observed_at_step: 10, title_ko: "측정 지연으로 Architecture 판단 대기", links: [{ relation_kind: "observed", statement_ko: "측정 slot이 Step 15로 변경되었습니다.", source_refs: ["DEV-1"], inference_basis: [] }], impacted_milestone_ids: ["M2-ARCH-FREEZE"] }],
    commitment_windows: [{ subject_type: "interface", subject_id: "WORK-ARCH", subject_title: "EIS Architecture option", closes_at_step: 13, closes_at_milestone_id: "M2-ARCH-FREEZE", closing_reason_ko: "Architecture Freeze 이후 변경 비용이 증가합니다.", post_window_impact_ko: "추가 재검토와 일정 조정이 필요합니다.", owner: "ROLE-ARCH", switching_cost: { mode: "exact", unit: "step", value: 1 } }],
    delay_summary_ko: "결정 window가 줄어듭니다.", recent_decision_relevant_event_ids: ["DEV-1"],
  },
  expected_option_transitions: [{ option_id: "OPT-SW-GUARDED", option_title: "SW feature flag로 제한 진행", label: "expected_from_observable_model", state_changes: [{ provenance: "expected_model", entity_type: "action", entity_id: "ACT-1", entity_title: "UHD60 제한 적용", from_state: "PLANNED", to_state: "IN_PROGRESS", basis_refs: ["RULE-1"] }], preserved_options_ko: ["즉시 철회"], lost_options_ko: [], model_basis: ["RULE-1"], unknown_impacts_ko: ["장시간 thermal"] }, { option_id: "OPT-DEFER", option_title: "측정까지 연기", label: "expected_from_observable_model", state_changes: [], preserved_options_ko: ["실측 반영"], lost_options_ko: ["현재 Freeze 확정"], model_basis: [], unknown_impacts_ko: ["일정 지연 폭"] }],
  observed_decision_transitions: { available: false, decision_id: null, state_changes: [], guardrail_events_ko: [] },
  alternatives: { comparison_dimensions_ko: ["기대 효과"], items: [{ option_id: "OPT-SW-GUARDED", title: "SW feature flag로 제한 진행", description: "feature flag", reversible: true, switching_cost: { mode: "exact", unit: "person_day", value: 3 } }, { option_id: "OPT-DEFER", title: "측정까지 연기", description: "실측 후 판단", reversible: true, switching_cost: { mode: "exact", unit: "step", value: 3 } }] },
  deliberation: { agreement_ko: [], dissent_ko: [], needs_confirmation_ko: ["실측 bandwidth"], changed_after_challenge_ko: [], key_assumptions_ko: [], key_unknowns_ko: ["실측 bandwidth"] },
  controls: { safeguards: [], action_plan: null },
  outcome_and_evaluation: { outcome_state: "not_available", hidden_until_step_advance: true, expectation_vs_actual_ko: [], process_evaluation_ko: null, outcome_evaluation_ko: null, lessons_ko: [] },
  workflow: { primary_action: "RUN_VIRTUAL_REVIEW", allowed_actions: ["RUN_VIRTUAL_REVIEW"], running_operation_ko: null },
  details: { evidence_available: true, timeline_available: true, impact_path_available: true, role_originals_available: false },
};

const historicalCaseItem = {
  ...caseItem,
  time_context: { ...caseItem.time_context, selected_step: 9, mode: "historical", commands_allowed_at_selected_step: false },
  header: { ...caseItem.header, workspace_phase: null, case_status: null },
  current_brief: { ...caseItem.current_brief, state_or_recommendation_ko: "선택한 Step의 당시 개발 상태", one_line_reason_ko: "이후에 알려진 검토·판단·결과는 포함하지 않습니다." },
  development_twin: { ...caseItem.development_twin, state_at_selected_step: { ...caseItem.development_twin.state_at_selected_step, reconstructed_at_step: 9 }, causal_chains: [], commitment_windows: [] },
  expected_option_transitions: caseItem.expected_option_transitions.map((item) => ({ ...item, state_changes: [], model_basis: [], unknown_impacts_ko: ["선택한 Step에서 검증된 상태 전이 모델이 없습니다."] })),
  workflow: { primary_action: null, allowed_actions: [], running_operation_ko: null },
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
  const payload = url.includes("/timeline")
    ? timelineItem
    : url.includes("at_step=9")
      ? historicalCaseItem
      : caseItem;
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
    expect(await screen.findByRole("heading", { name: caseItem.header.decision_question })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "선택한 시점의 개발 상태와 변화 원인" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "가장 가까운 Commitment Window" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "선택지별 예상 상태 변화" })).toBeInTheDocument();
    expect(screen.getAllByText("예상").length).toBeGreaterThan(0);
    expect(screen.getAllByText("관측").length).toBeGreaterThan(0);
    expect(screen.queryByText("ontology_relations")).not.toBeInTheDocument();
    expect(screen.queryByText("CASE-VR-001")).not.toBeInTheDocument();
  });

  it("switches to a historical observable step and disables commands", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(workspaceResponse);
    renderApp("/decisions/CASE-VR-001");
    const user = userEvent.setup();

    await user.selectOptions(await screen.findByLabelText("관찰 시점"), "9");

    expect(await screen.findByText("선택한 Step의 당시 개발 상태")).toBeInTheDocument();
    expect(screen.getByText("과거 Step에서는 실행할 수 없습니다.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "역할 검토 시작" })).toBeDisabled();
    expect(screen.getByText("이 Step에서 확인 가능한 commitment window가 없습니다.")).toBeInTheDocument();
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
