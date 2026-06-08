from pydantic_settings import BaseSettings
from pydantic import Field


class JiraConfig(BaseSettings):

    API_PREFIX: str = Field(
        default="/api/devops/latest/jira",
        description="API prefix for api exposure",
    )

    JIRA_ENDPOINT: str = Field(
        default="/rest/api/latest",
        description="API endpoint for Jira",
    )

    API_TAGS: list[str] = Field(
        default=["v1 - Jira Operations"],
        description="Tags used for OpenAPI documentation grouping.",
    )


config = JiraConfig()
