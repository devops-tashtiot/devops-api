from pydantic import BaseModel, Field, model_validator
from tashtiot_apis_library import OperationRequest

from app.global_conf import global_config


class ProjectSpec(BaseModel):
    key: str = Field(
        ...,
        description="project key",
        min_length=2,
        max_length=10,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    )

    name: str = Field(
        ...,
        description="project name",
        min_length=1,
        max_length=80,
        pattern=r"^[a-zA-Z0-9_\-\s]+$",
    )

    description: str = Field(
        ..., description="project description", min_length=1, max_length=1000
    )

    public: bool = Field(default=False, description="project visibility")

    admin_user: str | None = Field(
        default=None,
        description="Username to receive PROJECT_ADMIN permission",
        min_length=1,
        max_length=20,
        pattern=r"^[a-z][a-z0-9\-]*$",
    )

    admin_group: str | None = Field(
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


class MirrorProjectSpec(ProjectSpec):
    # Injected into the spec itself (defaults from global_config, but a caller can override
    # it per-request) rather than a fixed module-level Enum — mirrored_env_destination is
    # validated against this field's value, not directly against global_config, so the
    # allowed list is always visible right here on the request/response model.
    mirror_suffix_project_names: list[str] = Field(
        default_factory=lambda: list(
            global_config.BITBUCKET_MIRROR_SUFFIX_PROJECT_NAMES
        ),
        min_length=1,
        description="Valid mirrored_env_destination values for this request — display-name "
        "suffixes only, NOT Bitbucket Smart Mirrors server names. Defaults to "
        "BITBUCKET_MIRROR_SUFFIX_PROJECT_NAMES; override to allow a different set of "
        "naming suffixes for this request.",
    )

    mirrored_env_destination: list[str] = Field(
        ...,
        min_length=1,
        description="Naming suffix(es) for this project — must each appear in "
        "mirror_suffix_project_names. Appended to the end of the project name, joined "
        "by '+' (e.g. ' - Nati+Kat'). Does NOT name or select a mirror server: the "
        "actual physical Smart Mirrors server is discovered live (this deployment "
        "registers exactly one), and the project is registered with it exactly once "
        "regardless of how many suffixes are listed here.",
    )

    @model_validator(mode="after")
    def validate_mirrored_env_destination(self) -> "MirrorProjectSpec":
        chosen = self.mirrored_env_destination
        if len(set(chosen)) != len(chosen):
            raise ValueError("mirrored_env_destination must not contain duplicates")
        allowed = set(self.mirror_suffix_project_names)
        invalid = [d for d in chosen if d not in allowed]
        if invalid:
            raise ValueError(
                f"mirrored_env_destination contains values not in "
                f"mirror_suffix_project_names: {invalid}"
            )
        return self


class BitbucketProjectRequest(OperationRequest):
    spec: ProjectSpec


class BitbucketMirrorProjectRequest(OperationRequest):
    spec: MirrorProjectSpec
