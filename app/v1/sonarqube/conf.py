from pydantic_settings import BaseSettings
from pydantic import Field


class SonarqubeConfig(BaseSettings):

    API_PREFIX: str = Field(
        default="/api/devops/latest/sonarqube",
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
