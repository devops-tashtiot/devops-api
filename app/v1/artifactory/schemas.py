from pydantic import BaseModel, Field, model_validator
from typing import Optional
from enum import Enum
from tashtiot_apis_library import OperationRequest


class MemberType(str, Enum):
    USER = "user"
    GROUP = "group"


class ProjectPermissionSpec(BaseModel):
    project_key: str = Field(
        ...,
        description="Artifactory project key",
        min_length=2,
        max_length=32,
        pattern=r"^[a-z0-9\-]+$",
    )
    member_name: str = Field(
        ...,
        description="Username or group name to grant the role to",
        min_length=1,
        max_length=255,
    )
    member_type: MemberType = Field(
        ...,
        description="Whether the member is a 'user' or 'group'",
    )
    roles: list[str] = Field(
        ...,
        description="List of roles to assign — use GET /permissions/roles/{project_key} to list available roles",
        min_length=1,
    )



class StorageQuotaBytes(BaseModel):
    name: str = Field(
        ...,
        description="project or repo name",
    )

    storage_quota_giga_bytes: int = Field(
        description="storage quota giga bytes",
        gt=0,
        le=10,
    )


class ProjectSpec(BaseModel):
    name: str = Field(
        ...,
        description="Project display name — project key is derived from this (lowercase, spaces become hyphens)",
        min_length=2,
        max_length=32,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9 _\-]+$",
    )

    storage_quota_giga_bytes: int = Field(
        ...,
        description="Storage quota for the project in GB",
        gt=0,
        le=10,
    )

    admin_user: Optional[str] = Field(
        default=None,
        description="Username to receive PROJECT_ADMIN role",
        min_length=1,
        max_length=50,
        pattern=r"^[a-z0-9_\-]+$",
    )

    admin_group: Optional[str] = Field(
        default=None,
        description="Group name to receive PROJECT_ADMIN role",
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_\-]+$",
    )

    @model_validator(mode="after")
    def require_at_least_one_admin(self) -> "ProjectSpec":
        if not self.admin_user and not self.admin_group:
            raise ValueError("Provide at least one of admin_user or admin_group")
        return self

    @property
    def project_key(self) -> str:
        return self.name.lower().replace(" ", "-").replace("_", "-")


class ArtifactoryProjectRequest(OperationRequest):
    spec: ProjectSpec


class ArtifactoryStorageQuotaRequest(OperationRequest):
    spec: StorageQuotaBytes


class ArtifactoryPermissionRequest(OperationRequest):
    spec: ProjectPermissionSpec


class XrayVulnUpdateSpec(BaseModel):
    file_name: str = Field(
        ...,
        description="Name of the vulnerability update archive in the S3 bucket",
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_\-\.]+$",
    )


class ArtifactoryXrayUpdateRequest(OperationRequest):
    spec: XrayVulnUpdateSpec