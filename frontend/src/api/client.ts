import type { AblationResult, CaseEvaluation, DecisionListItem, DecisionWorkspace, DevelopmentTimeline, OutcomeSnapshot, ReviewRun } from "./generated";

const API_BASE = import.meta.env.VITE_SOC_OT_API_BASE_URL ?? "http://127.0.0.1:18080";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetchApi(path);
  if (!response.ok) {
    throw await toApiError(response);
  }
  return response.json() as Promise<T>;
}

async function postJson<T>(path: string, headers: Record<string, string> = {}, body?: string): Promise<T> {
  const response = await fetchApi(path, { method: "POST", headers, body });
  if (!response.ok) {
    throw await toApiError(response);
  }
  return response.json() as Promise<T>;
}

async function fetchApi(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError(
      "의사결정 트윈 서비스에 연결할 수 없습니다. 연결 상태를 확인한 뒤 다시 시도하세요.",
      0,
      "CONNECTION_FAILED",
    );
  }
}

export function getDecisionCases(): Promise<DecisionListItem[]> {
  return getJson("/api/v1/decision-cases");
}

export function getDecisionWorkspace(caseId: string, atStep?: number): Promise<DecisionWorkspace> {
  const query = atStep === undefined ? "" : `?${new URLSearchParams({ at_step: String(atStep) })}`;
  return getJson(`/api/v1/decision-cases/${encodeURIComponent(caseId)}/workspace${query}`);
}

export function getDecisionTimeline(caseId: string, atStep?: number): Promise<DevelopmentTimeline> {
  const query = atStep === undefined ? "" : `?${new URLSearchParams({ at_step: String(atStep) })}`;
  return getJson(`/api/v1/decision-cases/${encodeURIComponent(caseId)}/timeline${query}`);
}

function commandHeaders(aggregateVersion: number): Record<string, string> {
  return {
    "Idempotency-Key": crypto.randomUUID(),
    "If-Match": `"${aggregateVersion}"`,
  };
}

export function createReviewRun(caseId: string, aggregateVersion: number): Promise<ReviewRun> {
  return postJson(
    `/api/v1/decision-cases/${encodeURIComponent(caseId)}/review-runs`,
    { ...commandHeaders(aggregateVersion), "Content-Type": "application/json" },
    JSON.stringify({ command_schema_version: "review-run-command.v1", scope: "role_review" }),
  );
}

export function createDossierRun(caseId: string, aggregateVersion: number): Promise<ReviewRun> {
  return postJson(
    `/api/v1/decision-cases/${encodeURIComponent(caseId)}/review-runs`,
    { ...commandHeaders(aggregateVersion), "Content-Type": "application/json" },
    JSON.stringify({ command_schema_version: "review-run-command.v1", scope: "dossier" }),
  );
}

export function getReviewRun(runId: string): Promise<ReviewRun> {
  return getJson(`/api/v1/runs/${encodeURIComponent(runId)}`);
}

export function cancelReviewRun(runId: string, aggregateVersion: number): Promise<ReviewRun> {
  return postJson(`/api/v1/runs/${encodeURIComponent(runId)}/cancel`, commandHeaders(aggregateVersion));
}

export function retryReviewRun(runId: string, aggregateVersion: number): Promise<ReviewRun> {
  return postJson(`/api/v1/runs/${encodeURIComponent(runId)}/retry`, commandHeaders(aggregateVersion));
}

export function createSimulatedDecision(
  caseId: string,
  aggregateVersion: number,
  reviewRunId: string,
): Promise<AblationResult> {
  const query = new URLSearchParams({ review_run_id: reviewRunId });
  return postJson(
    `/api/v1/decision-cases/${encodeURIComponent(caseId)}/simulated-decisions?${query}`,
    commandHeaders(aggregateVersion),
  );
}

export function advanceOutcome(
  caseId: string,
  aggregateVersion: number,
  fromStep: number,
  toStep: number,
): Promise<OutcomeSnapshot> {
  const path = `/api/v1/decision-cases/${encodeURIComponent(caseId)}/outcome-advances`;
  const body = JSON.stringify({
    command_schema_version: "outcome-advance-command.v1",
    from_step: fromStep,
    to_step: toStep,
  });
  return postJson(path, { ...commandHeaders(aggregateVersion), "Content-Type": "application/json" }, body);
}

export function evaluateOutcome(caseId: string, aggregateVersion: number): Promise<CaseEvaluation> {
  return postJson(`/api/v1/decision-cases/${encodeURIComponent(caseId)}/evaluations`, commandHeaders(aggregateVersion));
}

export function isCaseVersionConflict(error: unknown): boolean {
  return error instanceof ApiError && error.code === "CASE_VERSION_CONFLICT";
}

async function toApiError(response: Response): Promise<ApiError> {
  let code: string | undefined;
  try {
    const payload = await response.json() as { detail?: { code?: unknown } };
    if (typeof payload.detail?.code === "string") code = payload.detail.code;
  } catch {
    // A non-JSON error response still gets a safe Korean fallback below.
  }
  const message = code === "CASE_VERSION_CONFLICT"
    ? "다른 변경으로 개발 상태가 갱신되었습니다. 최신 상태를 불러오세요."
    : `요청을 완료하지 못했습니다 (${response.status}). 다시 시도하세요.`;
  return new ApiError(message, response.status, code);
}
