import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
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
  alternatives: {
    comparison_dimensions_ko: ["기대 효과", "일정 영향", "실패 영향", "가역성", "필요한 근거", "안전 조건", "남는 위험"],
    items: [
      {
        option_id: "OPT-SW-GUARDED",
        title: "SW feature flag로 제한 진행",
        description: "feature flag로 범위를 제한합니다.",
        reversible: true,
        switching_cost: { mode: "exact", unit: "person_day", value: 3 },
        expected_effect_ko: "Architecture Freeze 전에 제한된 구현 경로를 확보합니다.",
        schedule_impact_ko: ["Step 13 결정을 유지합니다."],
        failure_impact_ko: ["성능 부족이면 기능을 비활성화해야 합니다."],
        reversibility_ko: "즉시 철회 가능 · 전환 비용 3 person_day",
        required_evidence_ko: ["Step 15 DDR 실측"],
        safety_conditions_ko: ["feature flag 격리"],
        residual_risks_ko: ["장시간 thermal 거동"],
        recommended: true,
        recommendation_reason_ko: "다수 Role이 안전 조건부 진행을 권고했습니다.",
      },
      {
        option_id: "OPT-DEFER",
        title: "측정까지 연기",
        description: "실측 후 판단합니다.",
        reversible: true,
        switching_cost: { mode: "exact", unit: "step", value: 3 },
        expected_effect_ko: "실측을 반영한 뒤 구현 여부를 결정합니다.",
        schedule_impact_ko: ["Architecture Freeze 확정이 늦어집니다."],
        failure_impact_ko: ["후속 HW 검토가 함께 밀릴 수 있습니다."],
        reversibility_ko: "결정 전에는 가역적 · 일정 비용 3 step",
        required_evidence_ko: ["Step 15 DDR 실측"],
        safety_conditions_ko: [],
        residual_risks_ko: ["결정 window 상실"],
        recommended: false,
        recommendation_reason_ko: null,
      },
    ],
  },
  deliberation: {
    agreement_ko: ["Architecture와 SW는 안전 조건부 진행에 동의합니다."],
    dissent_ko: ["HW는 실측 전 진행을 반대합니다."],
    needs_confirmation_ko: ["Step 15 DDR 실측 bandwidth"],
    changed_after_challenge_ko: ["SW가 rollback 조건을 권고에 추가했습니다."],
    key_assumptions_ko: ["feature flag로 영향 범위를 격리할 수 있습니다."],
    key_unknowns_ko: ["장시간 thermal 거동"],
    alignment_available: true,
    agreement_groups: [{ recommendation: "PROCEED_WITH_SAFEGUARDS", recommendation_ko: "안전 조건부 진행", role_labels_ko: ["Architecture", "SW/FW/HAL"], summary_ko: "격리와 rollback을 전제로 진행합니다." }],
    dissent_items: [{ role_label_ko: "HW", recommendation: "DEFER", recommendation_ko: "보류", rationale_ko: "실측 없이 power margin을 확정할 수 없습니다." }],
    challenge_changes: [{ role_label_ko: "SW/FW/HAL", before_recommendation_ko: "진행", after_recommendation_ko: "안전 조건부 진행", summary_ko: "rollback 기준을 명시했습니다." }],
    role_reviews: [{ role_label_ko: "Architecture", recommendation: "PROCEED_WITH_SAFEGUARDS", recommendation_ko: "안전 조건부 진행", recommended_option_title: "SW feature flag로 제한 진행", rationale_ko: "Freeze 전 가역 경로를 확보할 수 있습니다.", risks_ko: ["장시간 thermal"], information_gaps_ko: ["Step 15 실측"], unique_concern_ko: "commitment window", confidence_ko: "중간", revision: { recommendation_ko: "안전 조건부 진행", rationale_ko: "철회 조건을 추가했습니다." } }],
    epistemic_items: [
      { epistemic_status: "fact", statement_ko: "DDR 실측은 Step 15로 예정되어 있습니다.", source_titles_ko: ["측정 일정 변경"], observed_at_step: 10, inference_basis_ko: [], owner_ko: null, expires_at_step: null, unknown_reason_ko: null, expected_confirmation_step: null },
      { epistemic_status: "inference", statement_ko: "결정 지연은 Architecture Freeze에 영향을 줍니다.", source_titles_ko: ["측정 일정 변경"], observed_at_step: 10, inference_basis_ko: ["등록된 영향 규칙 1개를 적용했습니다."], owner_ko: null, expires_at_step: null, unknown_reason_ko: null, expected_confirmation_step: null },
      { epistemic_status: "assumption", statement_ko: "feature flag로 영향 범위를 격리할 수 있습니다.", source_titles_ko: [], observed_at_step: null, inference_basis_ko: [], owner_ko: "SW/FW/HAL", expires_at_step: 13, unknown_reason_ko: null, expected_confirmation_step: null },
      { epistemic_status: "unknown", statement_ko: "장시간 thermal 거동은 아직 모릅니다.", source_titles_ko: [], observed_at_step: null, inference_basis_ko: [], owner_ko: null, expires_at_step: null, unknown_reason_ko: "현재 관찰 범위에 장시간 측정이 없습니다.", expected_confirmation_step: 15 },
    ],
  },
  controls: { safeguards: [], action_plan: null },
  outcome_and_evaluation: { outcome_state: "not_available", hidden_until_step_advance: true, expectation_vs_actual_ko: [], process_evaluation_ko: null, outcome_evaluation_ko: null, lessons_ko: [] },
  workflow: { primary_action: "RUN_VIRTUAL_REVIEW", allowed_actions: ["RUN_VIRTUAL_REVIEW"], running_operation_ko: null },
  details: { evidence_available: true, timeline_available: true, impact_path_available: true, role_originals_available: true },
};

const historicalCaseItem = {
  ...caseItem,
  time_context: { ...caseItem.time_context, selected_step: 9, mode: "historical", commands_allowed_at_selected_step: false },
  header: { ...caseItem.header, workspace_phase: null, case_status: null },
  current_brief: { ...caseItem.current_brief, state_or_recommendation_ko: "선택한 Step의 당시 개발 상태", one_line_reason_ko: "이후에 알려진 검토·판단·결과는 포함하지 않습니다." },
  development_twin: { ...caseItem.development_twin, state_at_selected_step: { ...caseItem.development_twin.state_at_selected_step, reconstructed_at_step: 9 }, causal_chains: [], commitment_windows: [] },
  expected_option_transitions: caseItem.expected_option_transitions.map((item) => ({ ...item, state_changes: [], model_basis: [], unknown_impacts_ko: ["선택한 Step에서 검증된 상태 전이 모델이 없습니다."] })),
  deliberation: {
    ...caseItem.deliberation,
    agreement_ko: [],
    dissent_ko: [],
    needs_confirmation_ko: [],
    changed_after_challenge_ko: [],
    key_assumptions_ko: [],
    key_unknowns_ko: [],
    alignment_available: false,
    agreement_groups: [],
    dissent_items: [],
    challenge_changes: [],
    role_reviews: [],
    epistemic_items: caseItem.deliberation.epistemic_items.filter((item) => ["fact", "inference"].includes(item.epistemic_status)),
  },
  workflow: { primary_action: null, allowed_actions: [], running_operation_ko: null },
  details: { ...caseItem.details, role_originals_available: false },
};

const actioningCaseItem = {
  ...caseItem,
  header: { ...caseItem.header, workspace_phase: "OUTCOME_RUNNING", case_status: "OUTCOME_RUNNING" },
  current_brief: {
    ...caseItem.current_brief,
    state_or_recommendation_ko: "안전 조건부 진행",
    one_line_reason_ko: "가역 경로를 열고 Step 15 실측으로 위험을 제한합니다.",
  },
  observed_decision_transitions: {
    available: true,
    decision_id: "DECISION-1",
    state_changes: [{ provenance: "observed_event", entity_type: "action", entity_id: "ACTION-1", entity_title: "UHD60 제한 구현", from_state: "PLANNED", to_state: "IN_PROGRESS", basis_refs: ["DECISION-1"] }],
    guardrail_events_ko: [],
  },
  controls: {
    safeguards: [{
      safeguard_id: "SAFE-1",
      cause_ko: "실측 전 power margin은 불확실합니다.",
      metric_id: "ddr_bandwidth",
      metric_label_ko: "DDR 대역폭",
      operator: "gte",
      operator_ko: "≥",
      threshold_ko: "20 GB/s",
      check_at_step: 15,
      expires_at_step: 16,
      condition_ko: "UHD60 EIS 활성화 시",
      rollback_trigger_ko: "DDR bandwidth가 20 GB/s 미만이면 즉시 비활성화",
      owner: "Verification/Measurement",
      verification_ko: "Step 15 DDR 실측",
      violation_action_ko: "rollback 실행",
    }],
    action_plan: {
      action_type: "execute",
      decision_type_ko: "안전 조건부 진행",
      selected_option_title: "SW feature flag로 제한 진행",
      decision_rationale_ko: "Architecture Freeze 전 가역 경로를 확보하되 실측으로 중단 조건을 확인합니다.",
      owner: "SW/FW/HAL",
      action_ko: "UHD60 제한 구현",
      due_at_step: 13,
      trigger_ko: "가상 판단 기록 완료",
      verification_ko: "feature flag와 DDR 실측 확인",
      fallback_action_ko: "feature flag를 끄고 UHD60 EIS를 비활성화",
      status: "in_progress",
      status_ko: "진행 중",
      evidence_required_ko: ["Step 15 DDR 실측"],
      escalation_target_ko: "Architecture",
      questions_to_resolve_ko: ["장시간 thermal 거동"],
      reopen_condition_ko: "DDR bandwidth가 기준 미달일 때",
    },
  },
  outcome_and_evaluation: {
    outcome_state: "running",
    hidden_until_step_advance: true,
    expectation_vs_actual_ko: [],
    expected_ko: [],
    actual_ko: [],
    guardrail_results_ko: [],
    process_evaluation_ko: null,
    outcome_evaluation_ko: null,
    lessons_ko: [],
  },
  workflow: { primary_action: "ADVANCE_SIMULATION", allowed_actions: ["ADVANCE_SIMULATION"], running_operation_ko: null, dossier_run_id: "RUN-1" },
};

const closedCaseItem = {
  ...actioningCaseItem,
  header: { ...actioningCaseItem.header, workspace_phase: "CLOSED", case_status: "EVALUATED" },
  controls: {
    ...actioningCaseItem.controls,
    action_plan: { ...actioningCaseItem.controls.action_plan, status: "cancelled", status_ko: "Rollback 완료" },
  },
  observed_decision_transitions: {
    ...actioningCaseItem.observed_decision_transitions,
    state_changes: [
      { provenance: "observed_event", entity_type: "action", entity_id: "ACTION-1", entity_title: "UHD60 제한 구현", from_state: "IN_PROGRESS", to_state: "CANCELLED", basis_refs: ["OUTCOME-1"] },
      { provenance: "observed_event", entity_type: "work_item", entity_id: "WORK-ARCH", entity_title: "EIS 구현 option 결정", from_state: "BLOCKED", to_state: "IN_PROGRESS", basis_refs: ["OUTCOME-1"] },
    ],
  },
  outcome_and_evaluation: {
    outcome_state: "available",
    hidden_until_step_advance: false,
    expectation_vs_actual_ko: [],
    expected_ko: ["UHD60 제한 적용: PLANNED → IN_PROGRESS"],
    actual_ko: ["측정: ddr_bandwidth 18 GB/s", "실행된 보호 조치: rollback"],
    guardrail_results_ko: ["Guardrail 위반 감지 · 보호 조치 rollback 실행"],
    process_evaluation_ko: "당시 이용 가능한 근거에서 안전 조건과 다음 행동을 모두 갖췄습니다.",
    outcome_evaluation_ko: "공개된 위험 신호에 필요한 보호 조치가 실행되어 위험을 제한했습니다.",
    lessons_ko: ["DDR 실측을 다음 유사 결정에서는 decision window 전에 확인합니다."],
  },
  workflow: { primary_action: "VIEW_LEARNING_SUMMARY", allowed_actions: ["VIEW_LEARNING_SUMMARY"], running_operation_ko: null, dossier_run_id: "RUN-1" },
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

function workspaceFixtureResponse(payload: unknown, input: RequestInfo | URL) {
  return Promise.resolve(new Response(JSON.stringify(String(input).includes("/timeline") ? timelineItem : payload), { status: 200 }));
}

function renderApp(path = "/decisions") {
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

  it("replaces a raw workspace network error with a Korean recovery path", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    renderApp("/decisions/CASE-VR-001");

    expect(
      await screen.findByRole("heading", { name: "결정 검토를 불러오지 못했습니다" }),
    ).toBeInTheDocument();
    expect(screen.getByText("의사결정 트윈 서비스에 연결할 수 없습니다.")).toBeInTheDocument();
    expect(screen.getByText(/새 검토 정보는 표시하지 않았습니다/)).toBeInTheDocument();
    expect(screen.queryByText("Failed to fetch")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "결정 목록으로 돌아가기" })).toBeInTheDocument();
  });

  it("shows a decision workspace without raw ontology", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(workspaceResponse);
    renderApp("/decisions/CASE-VR-001");
    expect(await screen.findByRole("heading", { name: caseItem.header.decision_question })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "선택한 시점의 개발 상태와 변화 원인" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "가장 가까운 선택 가능 기한(Commitment Window)" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "선택지별 예상 상태 변화" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "같은 기준으로 선택지를 비교합니다" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "의견 일치" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "핵심 이견" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "확인 필요" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "확인된 사실" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "근거 기반 추론" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "검토할 가정" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "아직 모름" })).toBeInTheDocument();
    expect(screen.getByText("역할별 원문 보기")).toBeInTheDocument();
    expect(screen.getAllByText("예상").length).toBeGreaterThan(0);
    expect(screen.getAllByText("관측").length).toBeGreaterThan(0);
    expect(screen.queryByText("ontology_relations")).not.toBeInTheDocument();
    expect(screen.queryByText("CASE-VR-001")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "가상 역할 검토 실행" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "역할 검토 시작" })).not.toBeInTheDocument();
  });

  it("returns from a linked Decision to the originating historical Risk", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(workspaceResponse);
    renderApp("/decisions/CASE-VR-001?from_project=PROJECT-V&from_risk=RISK-V-WRONG-COMMIT&from_project_step=20");

    expect(await screen.findByRole("heading", { name: caseItem.header.decision_question })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "← Risk 상세" })).toHaveAttribute(
      "href",
      "/projects/PROJECT-V/risks/RISK-V-WRONG-COMMIT?at_step=20",
    );
    expect(screen.getByTestId("test-location")).toHaveTextContent(
      "?from_project=PROJECT-V&from_risk=RISK-V-WRONG-COMMIT&from_project_step=20",
    );
  });

  it("shows one linked action, safeguard, rollback, and observed-progress flow after decision", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => workspaceFixtureResponse(actioningCaseItem, input));
    const { container } = renderApp("/decisions/CASE-VR-001");

    expect(await screen.findByRole("heading", { name: "판단에서 실행과 확인까지 한 흐름으로 봅니다" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "안전 조건과 되돌리기(Rollback)" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "DDR 대역폭 ≥ 20 GB/s" })).toBeInTheDocument();
    expect(screen.getAllByText("SW/FW/HAL").length).toBeGreaterThan(0);
    expect(screen.getByText("feature flag와 DDR 실측 확인")).toBeInTheDocument();
    expect(screen.getAllByText("feature flag를 끄고 UHD60 EIS를 비활성화").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "결정이 만든 실제 상태 변화" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "아직 남는 위험" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "결과는 다음 Simulation Step 전까지 숨겨집니다" })).toBeInTheDocument();
    expect(container.querySelectorAll(".primary-button")).toHaveLength(1);
    expect(screen.getByText("결정 당시 검토 내용 보기")).toBeInTheDocument();
  });

  it("separates expectation, actual outcome, process, outcome, and learning after evaluation", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => workspaceFixtureResponse(closedCaseItem, input));
    renderApp("/decisions/CASE-VR-001");

    expect(await screen.findByRole("heading", { name: "예상과 실제를 분리해서 비교합니다" })).toBeInTheDocument();
    expect(screen.getByText("측정: ddr_bandwidth 18 GB/s")).toBeInTheDocument();
    expect(screen.getByText("Guardrail 위반 감지 · 보호 조치 rollback 실행")).toBeInTheDocument();
    expect(screen.getByText("당시 판단은 적절했는가")).toBeInTheDocument();
    expect(screen.getByText("위험을 실제로 제한했는가")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "다음 판단에 남길 학습" })).toBeInTheDocument();
  });

  it("moves between comparison cards on a narrow viewport", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(workspaceResponse);
    const { container } = renderApp("/decisions/CASE-VR-001");
    const user = userEvent.setup();

    await screen.findByRole("heading", { name: "같은 기준으로 선택지를 비교합니다" });
    const mobileCard = container.querySelector(".mobile-option-card");
    expect(mobileCard).toHaveTextContent("SW feature flag로 제한 진행");
    await user.click(screen.getByRole("button", { name: "다음 선택지" }));
    expect(mobileCard).toHaveTextContent("측정까지 연기");
    expect(screen.getByTestId("test-location")).toHaveTextContent("?option=2");
  });

  it("restores the selected step and mobile option from a deep link", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(workspaceResponse);
    const { container } = renderApp("/decisions/CASE-VR-001?at_step=9&option=2");

    expect(await screen.findByText("선택한 Step의 당시 개발 상태")).toBeInTheDocument();
    expect(container.querySelector(".mobile-option-card")).toHaveTextContent("측정까지 연기");
    expect(screen.getByTestId("test-location")).toHaveTextContent("?at_step=9&option=2");
  });

  it("recovers an unavailable historical step by returning to the current view", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => (
      String(input).includes("at_step=99")
        ? Promise.resolve(new Response(JSON.stringify({ detail: {} }), { status: 422 }))
        : workspaceResponse(input)
    ));
    renderApp("/decisions/CASE-VR-001?at_step=99");
    const user = userEvent.setup();

    expect(await screen.findByText("선택한 Step 99의 개발 상태를 재구성할 수 없습니다.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "현재 시점 보기" }));
    expect(await screen.findByRole("heading", { name: caseItem.header.decision_question })).toBeInTheDocument();
    expect(screen.getByTestId("test-location")).toHaveTextContent("/decisions/CASE-VR-001");
  });

  it("switches to a historical observable step and disables commands", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(workspaceResponse);
    renderApp("/decisions/CASE-VR-001");
    const user = userEvent.setup();

    await user.selectOptions(await screen.findByLabelText("관찰 시점"), "9");

    expect(await screen.findByText("선택한 Step의 당시 개발 상태")).toBeInTheDocument();
    expect(screen.getByTestId("test-location")).toHaveTextContent("?at_step=9");
    expect(screen.getByText("과거 Step에서는 실행할 수 없습니다.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "가상 역할 검토 실행" })).not.toBeInTheDocument();
    expect(screen.getByText("이 Step에서 확인 가능한 commitment window가 없습니다.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "아직 역할별 의견 종합이 없습니다" })).toBeInTheDocument();
    expect(screen.queryByText("역할별 원문 보기")).not.toBeInTheDocument();
    expect(screen.queryByText("feature flag로 영향 범위를 격리할 수 있습니다.")).not.toBeInTheDocument();
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

    await user.click(await screen.findByRole("button", { name: "가상 역할 검토 실행" }));

    expect(await screen.findByRole("heading", { name: "개발 상태가 변경되었습니다" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "최신 상태 불러오기" })).toBeInTheDocument();
  });
});
