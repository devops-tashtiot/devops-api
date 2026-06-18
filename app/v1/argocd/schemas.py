from pydantic import BaseModel, Field
from typing import Annotated, Optional
from enum import Enum

from app.global_conf import global_config
from app.v1.argocd.conf import config as argocd_config

# g lines: exactly 3 fields (2 commas) — g, <subject>, <role>
# p lines: exactly 6 fields (5 commas) — p, <subject>, <resource>, <action>, <object>, allow|deny
# Each field is either a quoted string ("...") or a non-whitespace token (role:name, *, URL, etc.)
_FIELD = r'(?:"[^"]+"|\S+)'
RoleLine = Annotated[
    str,
    Field(pattern=rf'^(?:g,\s*{_FIELD},\s*{_FIELD}|p(?:,\s*{_FIELD}){{4}},\s*(?:allow|deny))$'),
]

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


class ApplicationCluster(BaseModel):
    name: str = Field(
        default="openshift",
        description="Logical name for the cluster",
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_\-]+$",
    )
    namespace: str = Field(
        ...,
        description="Namespace(s) in OpenShift to deploy into (comma-separated for multiple)",
        min_length=1,
        max_length=1000,
    )
    address: str = Field(
        ...,
        description="Kubernetes cluster API URL (e.g. https://api.oacp-dev.example.com:6443)",
        min_length=1,
        max_length=2048,
    )
    token: str = Field(
        ...,
        description="Service account token for this cluster",
        min_length=1,
    )


class ClusterSecretSpec(BaseModel):
    username: str = Field(..., description="ArgoCD username", min_length=1)
    password: str = Field(..., description="ArgoCD password", min_length=1)
    chosen_name: str = Field(
        ...,
        description="Prefix for the ArgoCD app name — final name will be {chosen_name}-cluster-secret",
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_\-]+$",
    )
    app_name: str = Field(
        ...,
        description="Consumer name (e.g. insight, insight-prod) — used as the ArgoCD instance name",
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_\-]+$",
    )
    application_clusters: list[ApplicationCluster] = Field(
        ...,
        description="One or more clusters to register as ArgoCD cluster secrets",
        min_length=1,
    )


class ClusterSecretUpdateSpec(BaseModel):
    username: str = Field(..., description="ArgoCD username", min_length=1)
    password: str = Field(..., description="ArgoCD password", min_length=1)
    application_clusters: list[ApplicationCluster] = Field(
        ...,
        description="Updated list of clusters for the cluster secret",
        min_length=1,
    )


class ClusterSecretIdentifier(BaseModel):
    username: str = Field(..., description="ArgoCD username", min_length=1)
    password: str = Field(..., description="ArgoCD password", min_length=1)
    app_name: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_\-]+$")
    chosen_name: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_\-]+$")


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
    extra_roles: Optional[list[RoleLine]] = Field(
        default=None,
        description="Additional ArgoCD RBAC policy lines (g/p entries) to append to the consumer config",
    )
