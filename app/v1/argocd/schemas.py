from pydantic import BaseModel, Field
from enum import Enum

from app.global_conf import global_config
from app.v1.argocd.conf import config as argocd_config

EnvironmentEnum = Enum(
    "EnvironmentEnum",
    {e: e for e in global_config.ARGOCD_ALLOWED_ENVS},
    type=str,
)

SizeEnum = Enum(
    "SizeEnum",
    {s: s for s in argocd_config.ARGOCD_ALLOWED_SIZES},
    type=str,
)

IncludeResourceEnum = Enum(
    "IncludeResourceEnum",
    {r: r for r in argocd_config.ARGOCD_ALLOWED_RESOURCES},
    type=str,
)


class ConsumerConfigSpec(BaseModel):
    name: str = Field(
        ...,
        description="Consumer name — also used as the directory name under consumers/",
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_\-]+$",
    )
    environment: EnvironmentEnum = Field(
        ...,
        description="Target environment (limited to what this network deployment allows)",
    )
    size: SizeEnum = Field(..., description="ArgoCD instance size")
    include_resources: list[IncludeResourceEnum] = Field(
        ...,
        description="Kubernetes resource kinds to include",
        min_length=1,
    )
    ad_admin_group: str = Field(
        ...,
        description="Active Directory group to grant admin access",
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_\-]+$",
    )
