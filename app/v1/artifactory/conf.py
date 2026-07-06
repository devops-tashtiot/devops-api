from pydantic_settings import BaseSettings
from pydantic import Field

class ArtifactoryConfig(BaseSettings):

    API_PREFIX: str = Field(
        default="/api/devops/v1/artifactory",
        description="API prefix for api exposure",
    )
    API_TAGS: list[str] = Field(
        default=["v1 - Artifactory Operations"],
        description="Tags used for OpenAPI documentation grouping.",
    )

    ARTIFACTORY_ENDPOINT: str = Field(
        default="/access/api/v1",
        description="API endpoint for artifactory",
    )

    ARTIFACTORY_XRAY_ENDPOINT: str = Field(
        default="/xray/api/v1",
        description="Xray REST API base path",
    )


config = ArtifactoryConfig()