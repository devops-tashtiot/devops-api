from pydantic_settings import BaseSettings
from pydantic import Field

class ArtifactoryConfig(BaseSettings):
    
    API_PREFIX: str = Field(
        default="/api/devops/v1/artifactory",
        description="API prefix for api exposure",
    )
    
    ARTIFACTORY_ENDPOINT: str = Field(
        default="/access/api/v1",
        description="API endpoint for artifactory",
    )
    
    API_TAGS: list[str] = Field(
        default=["v1 - Artifactory Operations"],
        description="Tags used for OpenAPI documentation grouping.",
    )

config = ArtifactoryConfig()