from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class SonarqubeConfig(BaseSettings):

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    API_PREFIX: str = Field(
        default="/api/devops/v1/sonarqube",
        description="API prefix for api exposure",
    )

    SONARQUBE_ENDPOINT: str = Field(
        default="/api",
        description="SonarQube Web API base path",
    )

    SONARQUBE_ADMIN_TEMPLATE_NAME: str = Field(
        default="Default template",
        description="SonarQube permission template to assign admin permissions from",
    )

    SONARQUBE_SCHEME: str = Field(
        default="https",
        description="URL scheme for consumer SonarQube instances (use 'http' for local dev)",
    )

    SONARQUBE_PORT: str = Field(
        default="",
        description="Port for consumer SonarQube instances — empty means default for the scheme (use '9000' for local dev)",
    )

    SONARQUBE_GLOBAL_PERMISSIONS: list[str] = Field(
        default=["admin", "gateadmin", "profileadmin", "provisioning", "scan"],
        description="Global permissions granted to new admin groups",
    )

    SONARQUBE_TEMPLATE_PERMISSIONS: list[str] = Field(
        default=["user", "codeviewer", "issueadmin", "securityhotspotadmin", "admin", "scan"],
        description="Per-project template permissions granted to new admin groups",
    )

    API_TAGS: list[str] = Field(
        default=["v1 - SonarQube Operations"],
        description="Tags used for OpenAPI documentation grouping.",
    )


config = SonarqubeConfig()
