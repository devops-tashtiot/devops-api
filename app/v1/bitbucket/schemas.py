from pydantic import BaseModel, Field, model_validator
from typing import Optional
from tashtiot_apis_library import OperationRequest



class ProjectSpec(BaseModel):
    key: str = Field(
        ...,
        description="project key",
        min_length=1,
        max_length=10,
        pattern=r"^[A-Z][A-Z0-9_]*$"
    )
    
    name: str = Field(
        ...,
        description="project name",
        min_length=1,
        max_length=80,
        pattern=r"^[a-zA-Z0-9_\-\s]+$"
    )
    
    description: str = Field(
        ...,
        description="project description",
        min_length=1,
        max_length=1000
    )

    public: bool = Field(
        default=False,
        description="project visibility"
    )

    admin_user: Optional[str] = Field(
        default=None,
        description="Username to receive PROJECT_ADMIN permission",
        min_length=1,
        max_length=14,
        pattern=r"^[a-z][a-z0-9\-]*$",
    )

    admin_group: Optional[str] = Field(
        default=None,
        description="Group name to receive PROJECT_ADMIN permission",
        min_length=1,
        max_length=255,
    )

    @model_validator(mode="after")
    def require_at_least_one_admin(self) -> "ProjectSpec":
        if not self.admin_user and not self.admin_group:
            raise ValueError("Provide at least one of admin_user or admin_group")
        return self


class BitbucketProjectRequest(OperationRequest):
    spec: ProjectSpec
