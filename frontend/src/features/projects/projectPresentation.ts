import type { ProjectListItem, ProjectRiskSummary } from "../../api/generated";

export function attentionLabel(attention: ProjectListItem["attention"]) {
  return {
    BLOCKED: "진행 막힘",
    AT_RISK: "위험",
    WATCH: "관찰 필요",
    ON_TRACK: "계획대로",
  }[attention];
}

export function lifecycleLabel(stage: string) {
  return {
    MASS_PRODUCTION: "양산 품질 대응",
    PRE_SILICON_CLOSURE: "Pre-silicon 설계 확정",
    SPEC_DEFINITION: "요구사항·Architecture 정의",
  }[stage] ?? stage.replaceAll("_", " ");
}

export function riskLevelLabel(level: ProjectRiskSummary["risk_level"]) {
  return {
    CRITICAL: "치명적",
    HIGH: "높음",
    MEDIUM: "중간",
    LOW: "낮음",
  }[level];
}

export function riskStatusLabel(status: ProjectRiskSummary["status"]) {
  return {
    OPEN: "열림",
    TREATING: "대응 중",
    ACCEPTED: "수용",
    REALIZED: "현실화",
    CLOSED: "종료",
  }[status];
}

export function rankingReasonLabel(reason: string) {
  return {
    RISK_REALIZED: "이미 문제로 현실화됨",
    DOWNSIDE_SEVERE: "실패 영향이 큼",
    DOWNSIDE_MATERIAL: "무시하기 어려운 영향",
    URGENCY_IMMEDIATE: "즉시 대응 필요",
    URGENCY_BEFORE_MILESTONE: "다음 기준점 전에 판단 필요",
    IRREVERSIBLE_COMMITMENT: "확정 후 되돌리기 어려움",
    CROSS_PROJECT_BLAST_RADIUS: "다른 과제까지 영향 가능",
  }[reason] ?? reason.replaceAll("_", " ").toLocaleLowerCase("ko-KR");
}

export function stateLabel(state: string) {
  return {
    BLOCKED: "막힘",
    IN_PROGRESS: "진행 중",
    PLANNED: "예정",
    READY: "준비됨",
    REWORK: "재작업",
    DONE: "완료",
    COMPLETED: "완료",
    VERIFIED: "검증 완료",
    OPEN: "열림",
    MITIGATING: "대응 중",
    RESOLVED: "해결",
    AT_RISK: "위험",
    RECEIVED: "확보",
    REQUESTED: "요청됨",
    LATE: "지연",
    NOT_REQUESTED: "미요청",
    DECISION_REQUIRED: "결정 필요",
    REVIEW_READY: "검토 준비",
    OUTCOME_RUNNING: "결과 관찰 중",
    EVALUATED: "평가 완료",
  }[state] ?? state.replaceAll("_", " ").toLocaleLowerCase("ko-KR");
}

export function stepDistance(targetStep: number, currentStep: number) {
  const remaining = targetStep - currentStep;
  if (remaining < 0) return `${Math.abs(remaining)} Step 지남`;
  if (remaining === 0) return "현재 Step";
  return `${remaining} Step 남음`;
}

export function epistemicStatusLabel(status: string) {
  return {
    FACT: "관측 사실",
    INFERENCE: "근거 기반 추론",
    ASSUMPTION: "검토할 가정",
    UNKNOWN: "아직 모름",
    fact: "관측 사실",
    inference: "근거 기반 추론",
    assumption: "검토할 가정",
    unknown: "아직 모름",
  }[status] ?? stateLabel(status);
}

export function postureDimensionLabel(value: string) {
  return {
    CATASTROPHIC: "치명적",
    SEVERE: "매우 큼",
    MATERIAL: "무시하기 어려움",
    LIMITED: "제한적",
    LOCAL: "국소 영향",
    TRACK: "개발 Track 영향",
    PROJECT: "과제 전체 영향",
    CROSS_PROJECT: "다른 과제까지 영향",
    IMMEDIATE: "즉시 판단 필요",
    BEFORE_MILESTONE: "다음 기준점 전 판단",
    MONITOR: "관찰하며 판단",
    REVERSIBLE: "되돌릴 수 있음",
    PARTIALLY_REVERSIBLE: "일부만 되돌릴 수 있음",
    IRREVERSIBLE: "되돌리기 어려움",
    catastrophic: "치명적",
    severe: "매우 큼",
    material: "무시하기 어려움",
    limited: "제한적",
    local: "국소 영향",
    track: "개발 Track 영향",
    project: "과제 전체 영향",
    cross_project: "다른 과제까지 영향",
    immediate: "즉시 판단 필요",
    before_milestone: "다음 기준점 전 판단",
    monitor: "관찰하며 판단",
    reversible: "되돌릴 수 있음",
    partially_reversible: "일부만 되돌릴 수 있음",
    irreversible: "되돌리기 어려움",
  }[value] ?? stateLabel(value);
}

export function inferenceBasisLabel(basis: string) {
  return {
    "RULE-FIELD-LESSON-PROPAGATION": "양산에서 확인한 학습을 차기 과제 조건에 맞게 전파",
    "RULE-GUARDRAIL-KPI-TRADEOFF": "보호 기준과 성능 지표 사이의 trade-off",
    "RULE-FIELD-RECURRENCE": "현장 조건이 유지될 때 동일 문제가 반복될 가능성",
    "RULE-COMMITMENT-WINDOW": "되돌리기 어려운 확정 시점 전 판단 필요",
    "RULE-PRESI-CORRELATION-GAP": "Pre-silicon 예측과 silicon 실측 사이의 불확실성",
    "RULE-SHARED-RESOURCE-CRITICAL-PATH": "공유 검증 자원의 충돌이 critical path에 미치는 영향",
    "RULE-LESSON-CONTEXT-TRANSFER": "다른 과제의 학습을 현재 조건 차이와 함께 적용",
    "RULE-SPEC-ROBUSTNESS": "불완전한 요구에서도 변경을 흡수할 수 있는 Spec 여유",
    "RULE-LATE-REQUIREMENT-REWORK": "늦은 요구사항이 확정 이후 재작업으로 이어지는 경로",
    "MODEL-V-POWER-R2": "Pre-silicon power model 두 번째 revision",
    "MODEL-W-AREA-PERF-R1": "Area·성능 architecture model 첫 번째 revision",
  }[basis] ?? basis;
}

export function evidenceLimitationLabel(limitation: string) {
  return {
    field_correlation_not_available: "현장 조건과의 상관관계 미확인",
    model_error_band_wide: "Model 오차 범위가 큼",
    firmware_owner_review_pending: "Firmware 담당 검토 대기",
    silicon_not_available: "Silicon 미확보",
    limited_device_sample: "Device 표본 수가 제한적",
    single_ambient_condition: "단일 주변 환경에서만 확인",
    not_yet_available: "아직 확보되지 않음",
    previous_generation: "이전 세대 결과",
    workload_mix_changed: "현재 workload 구성과 차이가 있음",
    early_model: "초기 단계 model",
    memory_traffic_assumption: "Memory traffic 가정에 의존",
    detailed_workload_missing: "상세 workload 미확보",
  }[limitation] ?? limitation;
}
