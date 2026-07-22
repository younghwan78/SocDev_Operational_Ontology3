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
  }[state] ?? state.replaceAll("_", " ").toLocaleLowerCase("ko-KR");
}

export function stepDistance(targetStep: number, currentStep: number) {
  const remaining = targetStep - currentStep;
  if (remaining < 0) return `${Math.abs(remaining)} Step 지남`;
  if (remaining === 0) return "현재 Step";
  return `${remaining} Step 남음`;
}
