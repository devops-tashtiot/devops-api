from pydantic_settings import BaseSettings
from pydantic import Field


class ConfluenceConfig(BaseSettings):

    API_PREFIX: str = Field(
        default="/api/devops/latest/confluence",
        description="API prefix for api exposure",
    )

    CONFLUENCE_ENDPOINT: str = Field(
        default="/rest/api/latest",
        description="Base REST API path for Confluence Server",
    )

    CONFLUENCE_UPM_ENDPOINT: str = Field(
        default="/rest/plugins/1.0",
        description="Universal Plugin Manager REST API base path",
    )

    S3_PLUGINS_BASE_URL: str = Field(
        default="http://localhost:9100/confluence-plugins",
        description=(
            "Public base URL to the S3 plugins directory (no trailing slash). "
            "Example: http://localhost:9100/confluence-plugins for local MinIO, "
            "or https://my-bucket.s3.amazonaws.com for AWS."
        ),
    )

    CONFLUENCE_BACKUP_RESTORE_ENDPOINT: str = Field(
        default="/rest/api/backup-restore",
        description="Confluence backup-restore REST API base path",
    )

    S3_IMPORTS_BASE_URL: str = Field(
        default="http://localhost:9100/confluence-space-imports",
        description="Public base URL to the S3 space-imports directory (no trailing slash)",
    )

    JOB_POLL_INTERVAL: float = Field(
        default=2.0,
        description="Seconds between restore job status polls",
    )

    JOB_MAX_POLLS: int = Field(
        default=60,
        description="Maximum poll attempts before timeout",
    )

    API_TAGS: list[str] = Field(
        default=["v1 - Confluence Operations"],
        description="Tags used for OpenAPI documentation grouping.",
    )


config = ConfluenceConfig()
