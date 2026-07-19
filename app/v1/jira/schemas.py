from pydantic import BaseModel, Field
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

    # Required, not Optional — Jira's project-creation API unconditionally requires a lead
    # (a user, never a group): confirmed live that omitting it, and setting lead to a group
    # name, both get an identical 400 "You must specify a valid project lead." Unlike
    # Bitbucket/Confluence, a group can never substitute for this, so admin_group alone is
    # not a valid way to create a Jira project.
    admin_user: str = Field(
        ...,
        description="Username to set as project lead and administrator",
        min_length=1,
        max_length=50,
        pattern=r"^[a-z0-9_\-]+$",
    )

    admin_group: Optional[str] = Field(
        default=None,
        description="Group name to additionally receive project administrator role",
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_\-]+$",
    )


class JiraProjectRequest(OperationRequest):
    spec: ProjectSpec
