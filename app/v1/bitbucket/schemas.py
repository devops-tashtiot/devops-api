from pydantic import BaseModel, Field, model_validator
from typing import Optional


class ProjectMirrorSpec(BaseModel):
    name: str = Field(
        ...,
        description="name of the mirror project to create",
        min_length=1,
        max_length=255,
    )

    admin_user: str = Field(
        ...,
        description="user granted PROJECT_ADMIN on the mirror project",
        min_length=1,
        max_length=15,
        pattern=r"^[a-z0-9]+$",
    )


class ProjectSpec(BaseModel):
    key: str = Field(
        ...,
        description="project key",
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_\-]+$"
    )
    
    name: str = Field(
        ...,
        description="project name",
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_\-]+$"
    )
    
    description: str = Field(
        ...,
        description="project description",
        min_length=1,
        max_length=1000
    )
    
    public: bool = Field(
        False,
        description="project visibility"
    )
    
    admin_user: Optional[str] = Field(
        default=None,
        description="Username to receive PROJECT_ADMIN permission",
        min_length=1,
        max_length=15,
        pattern=r"^[a-z0-9]+$",
    )

    admin_group: Optional[str] = Field(
        default=None,
        description="Group name to receive PROJECT_ADMIN permission",
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_\-]+$",
    )

    @model_validator(mode="after")
    def require_at_least_one_admin(self) -> "ProjectSpec":
        if not self.admin_user and not self.admin_group:
            raise ValueError("Provide at least one of admin_user or admin_group")
        return self