from pydantic import BaseModel, Field


class GroupSpec(BaseModel):
    consumer_name: str = Field(
        ...,
        description="Consumer name — SonarQube URL is built as https://{consumer_name}.sonarqube.{DOMAIN_SUFFIX}",
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_\-]+$",
    )

    name: str = Field(
        ...,
        description="Group name — will be created in SonarQube and granted global admin rights",
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_\-]+$",
    )
