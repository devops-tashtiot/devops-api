from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator
from tashtiot_apis_library import OperationRequest

from app.global_conf import global_config

SonarQubeSizeEnum = Enum(
    "SonarQubeSizeEnum",
    {s: s for s in global_config.SONARQUBE_ALLOWED_SIZES},
    type=str,
)


class SonarQubeConsumerSpec(BaseModel):
    name: str = Field(
        ...,
        description="Consumer name — used as the directory name under consumers/",
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_\-]+$",
    )
    plugins_list: Optional[list[str]] = Field(
        default=None,
        description=(
            "SonarQube plugin keys to install for this consumer. "
            "Serialized as a comma-separated string in config.yaml "
            "for the ApplicationSet template (.plugins_list | quote | split \", \")."
        ),
    )

    @model_validator(mode="after")
    def validate_plugin_entries(self) -> "SonarQubeConsumerSpec":
        if self.plugins_list:
            bad = [p for p in self.plugins_list if "," in p or '"' in p]
            if bad:
                raise ValueError(
                    f"Plugin entries must not contain commas or quotes (they break the ApplicationSet split): {bad}"
                )
        return self
    size: SonarQubeSizeEnum = Field(
        default=SonarQubeSizeEnum.default,
        description="Instance size — 'default' omits the key from config.yaml; 'medium' and 'big' are written explicitly",
    )


class SonarQubeConsumerUpdateSpec(BaseModel):
    plugins_list: Optional[list[str]] = Field(
        default=None,
        description=(
            "Updated list of SonarQube plugin keys. "
            "Serialized as a comma-separated string for the ApplicationSet template."
        ),
    )
    size: SonarQubeSizeEnum = Field(
        default=SonarQubeSizeEnum.default,
        description="Instance size — 'default' omits the key from config.yaml; 'medium' and 'big' are written explicitly",
    )

    @model_validator(mode="after")
    def validate_plugin_entries(self) -> "SonarQubeConsumerUpdateSpec":
        if self.plugins_list:
            bad = [p for p in self.plugins_list if "," in p or '"' in p]
            if bad:
                raise ValueError(
                    f"Plugin entries must not contain commas or quotes (they break the ApplicationSet split): {bad}"
                )
        return self


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


class SonarQubeGroupRequest(OperationRequest):
    spec: GroupSpec


class SonarQubeConsumerRequest(OperationRequest):
    spec: SonarQubeConsumerSpec


class SonarQubeConsumerUpdateRequest(OperationRequest):
    spec: SonarQubeConsumerUpdateSpec
