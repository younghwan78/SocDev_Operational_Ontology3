// Aliases over OpenAPI-generated schema.d.ts. Business rules do not belong here.
import type { components } from "./schema";

export type DecisionListItem = components["schemas"]["DecisionListItemProjection"];
export type DecisionWorkspace = components["schemas"]["DecisionWorkspaceProjectionV2"];
export type DevelopmentTimeline = components["schemas"]["DevelopmentTimelineProjection"];
export type RoleReview = components["schemas"]["RoleReview"];
export type ReviewRun = components["schemas"]["ReviewRunView"];
export type AblationResult = components["schemas"]["AblationResult"];
export type CaseEvaluation = components["schemas"]["CaseEvaluation"];
export type RunTelemetry = components["schemas"]["RunTelemetryView"];
export type OutcomeSnapshot = components["schemas"]["OutcomeSnapshot"];
export type ProjectListItem = components["schemas"]["ProjectListItemProjection"];
export type ProjectSituation = components["schemas"]["ProjectSituationProjection"];
export type ProjectRiskSummary = components["schemas"]["ProjectRiskSummary"];
export type ProjectRiskDetail = components["schemas"]["ProjectRiskDetailProjection"];
export type ProjectTimeline = components["schemas"]["ProjectTimelineProjection"];
export type DecisionEvaluationResponse = components["schemas"]["DecisionEvaluationResponseState"];
export type DecisionInitialResponseCommand = components["schemas"]["DecisionInitialResponseCommand"];
export type DecisionFinalResponseCommand = components["schemas"]["DecisionFinalResponseCommand"];
