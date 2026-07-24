from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, HttpUrl, JsonValue, StringConstraints, field_validator, model_validator

from soc_ot.domain.models import StrictModel

RequiredText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1024),
]
Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class SourceDataClassification(StrEnum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class SourceDeletionState(StrEnum):
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"
    RESTRICTED = "RESTRICTED"


class EnterpriseSourceIdentity(StrictModel):
    source_system: RequiredText
    source_tenant: RequiredText
    source_object_type: RequiredText
    external_id: RequiredText


class EnterpriseSourceRecord(StrictModel):
    schema_version: Literal["enterprise-source-record.v1"]
    source_system: RequiredText
    source_tenant: RequiredText
    source_object_type: RequiredText
    external_id: RequiredText
    external_version: RequiredText
    effective_at: datetime
    observed_at: datetime
    source_updated_at: datetime
    ingested_at: datetime
    content_hash: Sha256Hex
    source_url: HttpUrl
    deletion_state: SourceDeletionState
    source_acl_ref: RequiredText
    classification: SourceDataClassification
    payload: dict[str, JsonValue] | None

    @field_validator(
        "effective_at",
        "observed_at",
        "source_updated_at",
        "ingested_at",
    )
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("enterprise source time must include a timezone")
        return value

    @field_validator("source_url")
    @classmethod
    def reject_embedded_credentials(cls, value: HttpUrl) -> HttpUrl:
        if value.username is not None or value.password is not None:
            raise ValueError("source_url cannot contain embedded credentials")
        return value

    @model_validator(mode="after")
    def protect_inactive_content(self) -> "EnterpriseSourceRecord":
        if self.deletion_state is SourceDeletionState.ACTIVE and self.payload is None:
            raise ValueError("active source record requires payload")
        if self.deletion_state is not SourceDeletionState.ACTIVE and self.payload is not None:
            raise ValueError("deleted or restricted source record cannot carry payload")
        return self

    @property
    def identity(self) -> EnterpriseSourceIdentity:
        return EnterpriseSourceIdentity(
            source_system=self.source_system,
            source_tenant=self.source_tenant,
            source_object_type=self.source_object_type,
            external_id=self.external_id,
        )
