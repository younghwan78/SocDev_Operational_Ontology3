import hashlib
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal

import yaml
from pydantic import Field, model_validator

from soc_ot.application.enterprise_ingestion import RequiredText, Sha256Hex
from soc_ot.application.enterprise_mapping import StructuredCandidateKind
from soc_ot.domain.models import StrictModel


class HandoffSourceKind(StrEnum):
    WORK_TRACKER = "WORK_TRACKER"
    KNOWLEDGE_BASE = "KNOWLEDGE_BASE"


class HandoffValueOwnership(StrEnum):
    EXTERNALLY_VERIFIED = "EXTERNALLY_VERIFIED"
    INTERNAL_REQUIRED = "INTERNAL_REQUIRED"


class HandoffCheckStatus(StrEnum):
    VERIFIED_EXTERNALLY = "VERIFIED_EXTERNALLY"
    UNCONFIRMED_INTERNAL = "UNCONFIRMED_INTERNAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_EVALUATED = "NOT_EVALUATED"


class HandoffRunbookStage(StrEnum):
    VALIDATE = "VALIDATE"
    DRY_RUN = "DRY_RUN"
    REVIEW = "REVIEW"
    IMPORT = "IMPORT"
    RECONCILE = "RECONCILE"


class HandoffStageAuthority(StrEnum):
    EXTERNAL_EXECUTABLE = "EXTERNAL_EXECUTABLE"
    COMPANY_APPROVAL_REQUIRED = "COMPANY_APPROVAL_REQUIRED"


class HandoffGateDecision(StrEnum):
    CONTINUE = "CONTINUE"
    STOP = "STOP"
    NOT_EVALUATED = "NOT_EVALUATED"


class HandoffMappingRow(StrictModel):
    target_field: RequiredText
    source_field_placeholder: Literal["INTERNAL_REQUIRED"]
    ownership: Literal[HandoffValueOwnership.INTERNAL_REQUIRED]


class HandoffStatusMappingRow(StrictModel):
    canonical_status: RequiredText
    source_status_placeholder: Literal["INTERNAL_REQUIRED"]
    ownership: Literal[HandoffValueOwnership.INTERNAL_REQUIRED]


class HandoffObjectMappingTemplate(StrictModel):
    object_type: RequiredText
    target_kind: StructuredCandidateKind
    field_mappings: list[HandoffMappingRow] = Field(min_length=1)
    status_mappings: list[HandoffStatusMappingRow] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_unique_targets(self) -> "HandoffObjectMappingTemplate":
        fields = [item.target_field for item in self.field_mappings]
        statuses = [item.canonical_status for item in self.status_mappings]
        if len(fields) != len(set(fields)):
            raise ValueError("handoff target field must be unique within an object")
        if len(statuses) != len(set(statuses)):
            raise ValueError("handoff canonical status must be unique within an object")
        return self


class EnterpriseHandoffMappingTemplate(StrictModel):
    schema_version: Literal["enterprise-handoff-mapping-template.v1"]
    template_version: RequiredText
    source_kind: HandoffSourceKind
    source_system_placeholder: Literal["INTERNAL_REQUIRED"]
    mapping_version_placeholder: Literal["INTERNAL_REQUIRED"]
    object_mappings: list[HandoffObjectMappingTemplate] = Field(min_length=1)
    company_data_included: Literal[False]

    @model_validator(mode="after")
    def require_unique_objects(self) -> "EnterpriseHandoffMappingTemplate":
        object_types = [item.object_type for item in self.object_mappings]
        target_kinds = [item.target_kind for item in self.object_mappings]
        if len(object_types) != len(set(object_types)):
            raise ValueError("handoff object_type must be unique")
        if len(target_kinds) != len(set(target_kinds)):
            raise ValueError("handoff target_kind must be unique")
        return self


class HandoffWorksheetItem(StrictModel):
    item_id: RequiredText
    topic: RequiredText
    ownership: HandoffValueOwnership
    status: HandoffCheckStatus
    value: str | None = None
    evidence_ref: str | None = None
    must_not_commit_value: bool = False

    @model_validator(mode="after")
    def align_ownership_and_status(self) -> "HandoffWorksheetItem":
        if self.ownership is HandoffValueOwnership.INTERNAL_REQUIRED:
            if self.status is not HandoffCheckStatus.UNCONFIRMED_INTERNAL:
                raise ValueError("internal worksheet item must remain unconfirmed")
            if self.value is not None or self.evidence_ref is not None:
                raise ValueError("internal worksheet value/evidence must be filled inside company")
        elif self.status is not HandoffCheckStatus.VERIFIED_EXTERNALLY:
            raise ValueError("external worksheet item must be verified externally")
        return self


class HandoffWorksheetSection(StrictModel):
    section_id: RequiredText
    items: list[HandoffWorksheetItem] = Field(min_length=1)


class EnterpriseEnvironmentWorksheet(StrictModel):
    schema_version: Literal["enterprise-environment-worksheet.v1"]
    worksheet_version: RequiredText
    company_data_included: Literal[False]
    credential_value_included: Literal[False]
    sections: list[HandoffWorksheetSection] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_items(self) -> "EnterpriseEnvironmentWorksheet":
        section_ids = [item.section_id for item in self.sections]
        items = [item for section in self.sections for item in section.items]
        item_ids = [item.item_id for item in items]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("worksheet section_id must be unique")
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("worksheet item_id must be unique")
        required_topics = {
            "DEPLOYMENT_VERSION",
            "NETWORK_PROXY_CERTIFICATE",
            "IDENTITY_ACCESS_METHOD",
            "SECRET_MANAGER_REFERENCE",
            "ACL_CLASSIFICATION",
            "RETENTION_DELETION",
            "RATE_LIMIT",
            "DATA_OWNER",
            "SECURITY_OWNER",
            "HUMAN_DECISION_AUTHORITY",
            "MODEL_PROVIDER_POLICY",
        }
        if not required_topics <= {item.topic for item in items}:
            raise ValueError("environment worksheet is missing a required topic")
        return self


class HandoffPilotScope(StrictModel):
    max_project_count: Literal[1]
    allowed_project_refs: list[RequiredText] = Field(max_length=1)
    read_only: Literal[True]
    write_back_enabled: Literal[False]
    canonical_import_authorized: Literal[False]


class HandoffRollbackPlan(StrictModel):
    triggers: list[RequiredText] = Field(min_length=1)
    actions: list[RequiredText] = Field(min_length=1)
    recovery_owner_placeholder: Literal["INTERNAL_REQUIRED"]


class HandoffRunbookStep(StrictModel):
    sequence: int = Field(ge=1)
    stage: HandoffRunbookStage
    authority: HandoffStageAuthority
    command: str | None = None
    entry_criteria: list[RequiredText] = Field(min_length=1)
    pass_criteria: list[RequiredText] = Field(min_length=1)
    stop_criteria: list[RequiredText] = Field(min_length=1)

    @model_validator(mode="after")
    def protect_company_gate(self) -> "HandoffRunbookStep":
        if self.authority is HandoffStageAuthority.EXTERNAL_EXECUTABLE:
            if not self.command:
                raise ValueError("externally executable stage requires a command")
        elif self.command is not None:
            raise ValueError("company approval stage cannot ship an execution command")
        return self


class HandoffExpectedMetric(StrictModel):
    metric_id: RequiredText
    expected_value: int = Field(ge=0)
    status: Literal[HandoffCheckStatus.NOT_EVALUATED]


class EnterprisePilotRunbook(StrictModel):
    schema_version: Literal["enterprise-pilot-runbook.v1"]
    runbook_version: RequiredText
    live_use_authorized: Literal[False]
    pilot_scope: HandoffPilotScope
    rollback: HandoffRollbackPlan
    steps: list[HandoffRunbookStep] = Field(min_length=5, max_length=5)
    expected_metrics: list[HandoffExpectedMetric] = Field(min_length=1)
    current_gate_decision: Literal[HandoffGateDecision.NOT_EVALUATED]

    @model_validator(mode="after")
    def require_fixed_stage_order(self) -> "EnterprisePilotRunbook":
        expected = list(HandoffRunbookStage)
        if [item.sequence for item in self.steps] != list(range(1, 6)):
            raise ValueError("handoff runbook sequence must be 1..5")
        if [item.stage for item in self.steps] != expected:
            raise ValueError("handoff runbook stage order is fixed")
        if any(
            item.authority is not HandoffStageAuthority.EXTERNAL_EXECUTABLE
            for item in self.steps[:3]
        ):
            raise ValueError("validate/dry-run/review must be externally executable")
        if any(
            item.authority is not HandoffStageAuthority.COMPANY_APPROVAL_REQUIRED
            for item in self.steps[3:]
        ):
            raise ValueError("import/reconcile require company approval")
        metric_ids = [item.metric_id for item in self.expected_metrics]
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("expected metric_id must be unique")
        return self


class HandoffChecklistItem(StrictModel):
    check_id: RequiredText
    description: RequiredText
    ownership: HandoffValueOwnership
    status: HandoffCheckStatus
    evidence_ref: str | None = None

    @model_validator(mode="after")
    def align_checklist_status(self) -> "HandoffChecklistItem":
        if self.ownership is HandoffValueOwnership.EXTERNALLY_VERIFIED:
            if self.status is not HandoffCheckStatus.VERIFIED_EXTERNALLY:
                raise ValueError("externally verified checklist item has invalid status")
            if not self.evidence_ref:
                raise ValueError("externally verified checklist item needs evidence")
        else:
            if self.status is not HandoffCheckStatus.UNCONFIRMED_INTERNAL:
                raise ValueError("internal checklist item must remain unconfirmed")
            if self.evidence_ref is not None:
                raise ValueError("internal checklist evidence must be filled inside company")
        return self


class HandoffArtifact(StrictModel):
    path: RequiredText
    sha256: Sha256Hex

    @model_validator(mode="after")
    def require_safe_relative_path(self) -> "HandoffArtifact":
        path = PurePosixPath(self.path)
        if path.is_absolute() or ".." in path.parts or "\\" in self.path:
            raise ValueError("handoff artifact path must be a safe POSIX relative path")
        return self


class EnterpriseHandoffPackage(StrictModel):
    schema_version: Literal["enterprise-handoff-package.v1"]
    package_version: RequiredText
    package_status: Literal["READY_FOR_INTERNAL_DISCOVERY"]
    live_use_authorized: Literal[False]
    company_data_included: Literal[False]
    credential_value_included: Literal[False]
    write_back_implemented: Literal[False]
    artifacts: list[HandoffArtifact] = Field(min_length=4)
    checklist: list[HandoffChecklistItem] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_artifacts_and_checklist(self) -> "EnterpriseHandoffPackage":
        paths = [item.path for item in self.artifacts]
        checks = [item.check_id for item in self.checklist]
        if len(paths) != len(set(paths)):
            raise ValueError("handoff artifact path must be unique")
        if len(checks) != len(set(checks)):
            raise ValueError("handoff checklist check_id must be unique")
        required = {
            "work-tracker-mapping-template.v1.yaml",
            "knowledge-base-mapping-template.v1.yaml",
            "environment-worksheet.v1.yaml",
            "pilot-runbook.v1.yaml",
        }
        if not required <= set(paths):
            raise ValueError("handoff package is missing a required artifact")
        ownership = {item.ownership for item in self.checklist}
        if ownership != set(HandoffValueOwnership):
            raise ValueError("handoff checklist must separate external and internal ownership")
        return self


class ValidatedEnterpriseHandoff(StrictModel):
    package: EnterpriseHandoffPackage
    mapping_templates: list[EnterpriseHandoffMappingTemplate]
    worksheet: EnterpriseEnvironmentWorksheet
    runbook: EnterprisePilotRunbook


def load_and_validate_handoff_package(package_root: Path) -> ValidatedEnterpriseHandoff:
    package_path = package_root / "handoff-package.v1.yaml"
    package = EnterpriseHandoffPackage.model_validate(_load_yaml(package_path))
    for artifact in package.artifacts:
        path = package_root / artifact.path
        if not path.is_file():
            raise ValueError(f"handoff artifact does not exist: {artifact.path}")
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != artifact.sha256:
            raise ValueError(f"handoff artifact hash mismatch: {artifact.path}")

    mappings = [
        EnterpriseHandoffMappingTemplate.model_validate(
            _load_yaml(package_root / artifact.path)
        )
        for artifact in package.artifacts
        if artifact.path.endswith("mapping-template.v1.yaml")
    ]
    if {item.source_kind for item in mappings} != set(HandoffSourceKind):
        raise ValueError("handoff package must cover both source kinds")
    worksheet = EnterpriseEnvironmentWorksheet.model_validate(
        _load_yaml(package_root / "environment-worksheet.v1.yaml")
    )
    runbook = EnterprisePilotRunbook.model_validate(
        _load_yaml(package_root / "pilot-runbook.v1.yaml")
    )
    return ValidatedEnterpriseHandoff(
        package=package,
        mapping_templates=mappings,
        worksheet=worksheet,
        runbook=runbook,
    )


def _load_yaml(path: Path) -> object:
    return yaml.safe_load(path.read_text(encoding="utf-8"))
