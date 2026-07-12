from pydantic_settings import BaseSettings
from pydantic import Field

class BitbucketConfig(BaseSettings):
    
    API_PREFIX: str = Field(
        default="/api/devops/v1/bitbucket",
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

config = BitbucketConfig()