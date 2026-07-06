from pydantic import BaseModel, Field, model_validator
from typing import Optional
from tashtiot_apis_library import OperationRequest


class ProjectSpec(BaseModel):
    key: str = Field(
        ...,
        description="Project key — uppercase letters and digits only",
        min_length=1,
        max_length=10,
        pattern=r"^[A-Z][A-Z0-9]+$",
    )

    name: str = Field(
        ...,
        description="Project display name",
        min_length=1,
        max_length=255,
    )

    description: str = Field(
        ...,
        description="Project description",
        min_length=1,
        max_length=1000,
    )

    admin_user: Optional[str] = Field(
        default=None,
        description="Username to set as project lead and administrator",
        min_length=1,
        max_length=50,
        pattern=r"^[a-z0-9_\-]+$",
    )

    admin_group: Optional[str] = Field(
        default=None,
        description="Group name to receive project administrator role",
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_\-]+$",
    )

    @model_validator(mode="after")
    def require_at_least_one_admin(self) -> "ProjectSpec":
        if not self.admin_user and not self.admin_group:
            raise ValueError("Provide at least one of admin_user or admin_group")
        return self


class JiraProjectRequest(OperationRequest):
    spec: ProjectSpec
