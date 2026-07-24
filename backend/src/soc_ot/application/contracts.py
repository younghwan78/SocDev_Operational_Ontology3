import json
from pathlib import Path

from pydantic import BaseModel

from soc_ot.agents.contracts import RoleReview
from soc_ot.agents.multi_role import DecisionActionPlan, DecisionDossier, SimulatedDecision
from soc_ot.application.decision_evaluation_responses import (
    DecisionAdviceRevealCommand,
    DecisionEvaluationResponseState,
    DecisionFinalResponseCommand,
    DecisionInitialResponseCommand,
)
from soc_ot.application.development_twin import DevelopmentTimelineProjection
from soc_ot.application.enterprise_ingestion import EnterpriseSourceRecord
from soc_ot.application.evaluation import CaseEvaluation, EvaluationSummary
from soc_ot.application.evaluation_manifest import EvaluationManifest
from soc_ot.application.outcomes import OutcomeSnapshot
from soc_ot.application.packets import ObservableCasePacket
from soc_ot.application.project_fixture_contracts import DevelopmentProject
from soc_ot.application.project_operations import (
    ProjectListItemProjection,
    ProjectRiskDetailProjection,
    ProjectRiskSummary,
    ProjectSituationProjection,
    ProjectTimelineProjection,
)
from soc_ot.application.projections import DecisionListItemProjection
from soc_ot.application.usability_study import (
    ProjectUsabilityBaselinePack,
    ProjectUsabilityStudyProtocol,
    UsabilityBaselinePack,
    UsabilityReviewerRubric,
    UsabilitySession,
    UsabilityStudyProtocol,
    UsabilityStudyRelease,
    UsabilityStudySummary,
)
from soc_ot.application.workspace_contracts import (
    DecisionWorkspaceProjectionV2,
    WorkspaceUxFixture,
)
from soc_ot.domain.models import DevelopmentEvent, ExpectedResult, HiddenCase, ObservableCase

CONTRACT_MODELS: dict[str, type[BaseModel]] = {
    "observable-case.v1": ObservableCase,
    "development-event.v1": DevelopmentEvent,
    "development-project.v1": DevelopmentProject,
    "enterprise-source-record.v1": EnterpriseSourceRecord,
    "project-list-item.v1": ProjectListItemProjection,
    "project-situation.v1": ProjectSituationProjection,
    "project-risk-summary.v1": ProjectRiskSummary,
    "project-risk-detail.v1": ProjectRiskDetailProjection,
    "project-timeline.v1": ProjectTimelineProjection,
    "development-timeline.v1": DevelopmentTimelineProjection,
    "decision-evaluation-response.v1": DecisionEvaluationResponseState,
    "decision-initial-response-command.v1": DecisionInitialResponseCommand,
    "decision-final-response-command.v1": DecisionFinalResponseCommand,
    "decision-advice-reveal-command.v1": DecisionAdviceRevealCommand,
    "evaluation-manifest.v2": EvaluationManifest,
    "case-evaluation.v2": CaseEvaluation,
    "evaluation-summary.v2": EvaluationSummary,
    "hidden-case.v1": HiddenCase,
    "expected-result.v1": ExpectedResult,
    "observable-case-packet.v1": ObservableCasePacket,
    "role-review.v1": RoleReview,
    "decision-dossier.v1": DecisionDossier,
    "decision-action-plan.v1": DecisionActionPlan,
    "simulated-decision.v2": SimulatedDecision,
    "outcome-snapshot.v1": OutcomeSnapshot,
    "decision-workspace.v2": DecisionWorkspaceProjectionV2,
    "workspace-ux-fixture.v1": WorkspaceUxFixture,
    "decision-list-item.v1": DecisionListItemProjection,
    "usability-baseline-pack.v1": UsabilityBaselinePack,
    "usability-study-protocol.v1": UsabilityStudyProtocol,
    "usability-project-baseline-pack.v2": ProjectUsabilityBaselinePack,
    "usability-study-protocol.v2": ProjectUsabilityStudyProtocol,
    "usability-study-release.v1": UsabilityStudyRelease,
    "usability-reviewer-rubric.v1": UsabilityReviewerRubric,
    "usability-session.v1": UsabilitySession,
    "usability-study-summary.v1": UsabilityStudySummary,
}


def export_contracts(output_dir: Path, *, check: bool = False) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    changed: list[Path] = []
    for name, model in CONTRACT_MODELS.items():
        path = output_dir / f"{name}.schema.json"
        rendered = json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + "\n"
        if not path.exists() or path.read_text(encoding="utf-8") != rendered:
            changed.append(path)
            if not check:
                path.write_text(rendered, encoding="utf-8")
    if check and changed:
        names = ", ".join(path.name for path in changed)
        raise ValueError(f"generated contracts are stale: {names}")
    return changed
