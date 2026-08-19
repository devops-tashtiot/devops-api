from pydantic import Field
from pydantic_settings import BaseSettings


class BitbucketConfig(BaseSettings):
    API_PREFIX: str = Field(
        default="/api/v1/devops/bitbucket",
        description="API prefix for api exposure",
    )
    API_TAGS: list[str] = Field(
        default=["v1 - Bitbucket Operations"],
        description="Tags used for OpenAPI documentation grouping.",
    )
    BITBUCKET_ENDPOINT: str = Field(
        default="/rest/api/latest",
        description="API endpoint for bitbucket",
    )
    BITBUCKET_CROWD_ENDPOINT: str = Field(
        default="/rest/crowd/latest",
        description="Crowd REST API base path — used for user directory listing and sync",
    )
    BITBUCKET_MIRRORING_ENDPOINT: str = Field(
        default="/rest/mirroring/1.0",
        description="Smart Mirrors REST API base path — used to discover a registered "
        "physical mirror server (by name) and register a project with it",
    )


config = BitbucketConfig()
