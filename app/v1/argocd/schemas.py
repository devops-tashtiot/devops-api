from enum import Enum
from typing import Annotated, Any, Literal

import yaml as _yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from tashtiot_apis_library import OperationRequest

from app.global_conf import global_config

# Identifier pattern shared by role/name/group fields (alphanumerics, underscore, hyphen).
_IDENTIFIER_PATTERN = r"^[a-zA-Z0-9_\-]+$"

# RFC 1123 DNS label pattern — required for fields that become part of a Kubernetes/ArgoCD
# resource name (chosen_name/app_name/consumer name): lowercase alphanumerics and hyphens,
# must start and end with an alphanumeric.
_DNS_LABEL_PATTERN = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"

# g lines: g, <subject>, <role>
# p lines: p, <subject>, <resource>, <action>, <object>, allow|deny
# Resources and actions are locked to the ArgoCD RBAC spec:
#   https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/
_FIELD = r'(?:"[^"]+"|\S+)'
_RESOURCE = r"(?:applications|applicationsets|clusters|projects|repositories|accounts|certificates|gpgkeys|logs|exec|extensions|\*)"
_ACTION = r"(?:get|create|update|delete|sync|action|override|invoke|\*)"
RoleLine = Annotated[
    str,
    Field(
        pattern=rf"^(?:g,\s*{_FIELD},\s*{_FIELD}|p,\s*{_FIELD},\s*{_RESOURCE},\s*{_ACTION},\s*{_FIELD},\s*(?:allow|deny))$"
    ),
]


class RbacResourceEnum(str, Enum):
    applications = "applications"
    applicationsets = "applicationsets"
    clusters = "clusters"
    projects = "projects"
    repositories = "repositories"
    accounts = "accounts"
    certificates = "certificates"
    gpgkeys = "gpgkeys"
    logs = "logs"
    exec = "exec"
    extensions = "extensions"
    wildcard = "*"


class RbacActionEnum(str, Enum):
    get = "get"
    create = "create"
    update = "update"
    delete = "delete"
    sync = "sync"
    action = "action"
    override = "override"
    invoke = "invoke"
    wildcard = "*"


class GLine(BaseModel):
    ad_group: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., min_length=1, max_length=255, pattern=_IDENTIFIER_PATTERN)

    def to_rbac(self) -> str:
        return f'g, "{self.ad_group}", role:{self.role}'


class PLine(BaseModel):
    role: str = Field(..., min_length=1, max_length=255, pattern=_IDENTIFIER_PATTERN)
    resource: RbacResourceEnum
    action: RbacActionEnum
    object: str = Field(..., min_length=1, max_length=1024)
    effect: Literal["allow", "deny"] = "allow"

    def to_rbac(self) -> str:
        return f"p, role:{self.role}, {self.resource.value}, {self.action.value}, {self.object}, {self.effect}"


EnvironmentEnum = Enum(
    "EnvironmentEnum",
    {e: e for e in global_config.ARGOCD_ALLOWED_ENVS},
    type=str,
)

SizeEnum = Enum(
    "SizeEnum",
    {s: s for s in global_config.ARGOCD_ALLOWED_SIZES},
    type=str,
)

IncludeResourceEnum = Enum(
    "IncludeResourceEnum",
    {r: r for r in global_config.ARGOCD_ALLOWED_RESOURCES},
    type=str,
)


class ApplicationCluster(BaseModel):
    name: str = Field(
        default="openshift",
        description="Logical name for the cluster",
        min_length=1,
        max_length=255,
        pattern=_IDENTIFIER_PATTERN,
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
    chosen_name: str = Field(
        ...,
        description="Prefix for the ArgoCD app name — final name will be {chosen_name}-cluster-secret",
        min_length=1,
        max_length=48,
        pattern=_DNS_LABEL_PATTERN,
    )
    app_name: str = Field(
        ...,
        description="Consumer name (e.g. insight, insight-prod) — used as the ArgoCD instance name",
        min_length=1,
        max_length=63,
        pattern=_DNS_LABEL_PATTERN,
    )
    application_clusters: list[ApplicationCluster] = Field(
        ...,
        description="One or more clusters to register as ArgoCD cluster secrets",
        min_length=1,
    )


class ClusterSecretUpdateSpec(BaseModel):
    application_clusters: list[ApplicationCluster] = Field(
        ...,
        description="Updated list of clusters for the cluster secret",
        min_length=1,
    )


class ClusterSecretIdentifier(BaseModel):
    app_name: str = Field(..., min_length=1, max_length=63, pattern=_DNS_LABEL_PATTERN)
    chosen_name: str = Field(
        ..., min_length=1, max_length=63, pattern=_DNS_LABEL_PATTERN
    )


_ArgoCDValue = str | bool | int | float


class ConsumerExtraConfig(BaseModel):
    extra_argocd_cm_args: dict[str, _ArgoCDValue] | None = None
    extra_argocd_params: dict[str, _ArgoCDValue] | None = None

    @field_validator("extra_argocd_cm_args", "extra_argocd_params", mode="before")
    @classmethod
    def _coerce_list_to_dict(cls, v: Any) -> Any:
        if isinstance(v, list):
            return {item["key"]: item["value"] for item in v if item.get("key")}
        return v

    @model_validator(mode="after")
    def validate_yaml(self) -> "ConsumerExtraConfig":
        if self.extra_argocd_cm_args:
            for key, value in self.extra_argocd_cm_args.items():
                if isinstance(value, str) and "\n" in value:
                    try:
                        _yaml.safe_load(value)
                    except _yaml.YAMLError as exc:
                        raise ValueError(
                            f"Value for '{key}' is not valid YAML: {exc}"
                        ) from exc

        return self


class ConsumerConfigSpec(BaseModel):
    name: str = Field(
        ...,
        description="Consumer name — also used as the directory name under consumers/",
        min_length=1,
        max_length=63,
        pattern=_DNS_LABEL_PATTERN,
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
    )
    g_lines: list[GLine] | None = Field(
        default=None,
        description='Structured group binding lines — each becomes a g, "<ad_group>", role:<role> entry',
    )
    p_lines: list[PLine] | None = Field(
        default=None,
        description="Structured permission lines — each becomes a p, role:<role>, <resource>, <action>, <object>, <effect> entry",
    )
    extra_roles: list[RoleLine] | None = Field(
        default=None,
        description="Raw ArgoCD RBAC policy lines (g/p entries) appended verbatim — for advanced use",
    )
    config: ConsumerExtraConfig | None = Field(
        default=None,
        description="Optional ArgoCD configuration overrides (argocd-cm and argocd-cmd-params-cm) injected into the consumer's config.yaml",
    )


class ConsumerConfigRequest(OperationRequest):
    spec: ConsumerConfigSpec


class ClusterSecretRequest(OperationRequest):
    spec: ClusterSecretSpec


class ClusterSecretUpdateRequest(OperationRequest):
    spec: ClusterSecretUpdateSpec
