from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from tashtiot_apis_library import OperationRequest


class SpaceSpec(BaseModel):
    key: str = Field(
        ...,
        description="Space key — uppercase letters and digits only",
        min_length=1,
        max_length=255,
        pattern=r"^[A-Z0-9]+$",
    )

    name: str = Field(
        ...,
        description="Space display name",
        min_length=1,
        max_length=255,
    )

    description: str = Field(
        ...,
        description="Space description",
        min_length=1,
        max_length=1000,
    )

    admin_user: Optional[str] = Field(
        default=None,
        description="Username to receive ADMIN permission on the space",
        min_length=1,
        max_length=50,
        pattern=r"^[a-z0-9_\-]+$",
    )

    admin_group: Optional[str] = Field(
        default=None,
        description="Group name to receive ADMIN permission on the space",
        min_length=1,
        max_length=255,
        pattern=r"^[a-z0-9_\-]+$",
    )

    @model_validator(mode="after")
    def require_at_least_one_admin(self) -> "SpaceSpec":
        if not self.admin_user and not self.admin_group:
            raise ValueError("Provide at least one of admin_user or admin_group")
        return self


class PluginInstallSpec(BaseModel):
    plugin_name: str = Field(
        ...,
        description="Filename of the .jar already uploaded to the shared S3 plugins bucket",
        min_length=5,
        max_length=255,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9\-\._]*$",
    )

    @field_validator("plugin_name")
    @classmethod
    def must_be_jar(cls, v: str) -> str:
        if not v.lower().endswith(".jar"):
            raise ValueError("plugin_name must end with .jar")
        return v


class SpaceImportSpec(BaseModel):
    archive_name: str = Field(
        ...,
        description="Filename of the .zip archive already uploaded to the S3 imports bucket",
        min_length=5,
        max_length=255,
    )

    @model_validator(mode="after")
    def archive_must_be_zip(self) -> "SpaceImportSpec":
        if not self.archive_name.lower().endswith(".zip"):
            raise ValueError("archive_name must end with .zip")
        return self


class SpaceExportSpec(BaseModel):
    space_key: str = Field(
        ...,
        description="Key of the space to export",
        min_length=1,
        max_length=50,
        pattern=r"^[A-Z][A-Z0-9]*$",
    )


class PluginUploadSpec(BaseModel):
    plugin_name: str = Field(
        ...,
        description="Filename to store in S3 (must end with .jar)",
        min_length=5,
        max_length=255,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9\-\._]*$",
    )
    file_content: str = Field(
        ...,
        description="Base64-encoded .jar file (data-URL format accepted)",
        min_length=1,
    )

    @field_validator("plugin_name")
    @classmethod
    def must_be_jar(cls, v: str) -> str:
        if not v.lower().endswith(".jar"):
            raise ValueError("plugin_name must end with .jar")
        return v


class ConfluenceSpaceRequest(OperationRequest):
    spec: SpaceSpec


class ConfluencePluginInstallRequest(OperationRequest):
    spec: PluginInstallSpec


class ConfluencePluginUploadRequest(OperationRequest):
    spec: PluginUploadSpec


class ConfluenceSpaceExportRequest(OperationRequest):
    spec: SpaceExportSpec


class ConfluenceSpaceImportRequest(OperationRequest):
    spec: SpaceImportSpec
