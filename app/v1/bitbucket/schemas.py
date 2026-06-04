from pydantic import BaseModel, Field

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
    
    admin_user: str = Field(
        description="user with admin privileges for this project",
        min_length=1,
        max_length=15,
        pattern=r"^[a-z0-9]+$"
    )