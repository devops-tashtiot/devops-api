from pydantic_settings import BaseSettings
from pydantic import Field

class BitbucketConfig(BaseSettings):
    
    API_PREFIX: str = Field(
        default="/api/devops/latest/bitbucket",
        description="API prefix for api exposure",
    )
    
    BITBUCKET_ENDPOINT: str = Field(
        default="/rest/api/latest",
        description="API endpoint for bitbucket",
    )
    
    API_TAGS: list[str] = Field(
        default=["v1 - Bitbucket Operations"],
        description="Tags used for OpenAPI documentation grouping.",
    )

config = BitbucketConfig()