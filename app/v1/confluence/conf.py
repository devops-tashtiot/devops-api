from pydantic_settings import BaseSettings
from pydantic import Field


class ConfluenceConfig(BaseSettings):

    API_PREFIX: str = Field(
        default="/api/devops/v1/confluence",
        description="API prefix for api exposure",
    )

    API_TAGS: list[str] = Field(
        default=["v1 - Confluence Operations"],
        description="Tags used for OpenAPI documentation grouping.",
    )
    
    CONFLUENCE_ENDPOINT: str = Field(
        default="/rest/api/latest",
        description="Base REST API path for Confluence Server",
    )

    CONFLUENCE_UPM_ENDPOINT: str = Field(
        default="/rest/plugins/1.0",
        description="Universal Plugin Manager REST API base path",
    )

    CONFLUENCE_CROWD_ENDPOINT: str = Field(
        default="/rest/crowd/latest",
        description="Crowd REST API base path — used for user directory listing and sync",
    )

    CONFLUENCE_BACKUP_RESTORE_ENDPOINT: str = Field(
        default="/rest/api/backup-restore",
        description="Confluence backup-restore REST API base path",
    )

    CONFLUENCE_JOB_POLL_INTERVAL: float = Field(
        default=2.0,
        description="Seconds between restore job status polls",
    )

    CONFLUENCE_JOB_MAX_POLLS: int = Field(
        default=60,
        description="Maximum poll attempts before timeout",
    )




config = ConfluenceConfig()
