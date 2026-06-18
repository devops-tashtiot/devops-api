from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class ArgocdConfig(BaseSettings):

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    API_PREFIX: str = Field(
        default="/api/devops/v1/argocd",
        description="API prefix for api exposure",
    )

    API_TAGS: list[str] = Field(
        default=["v1 - ArgoCD Operations"],
        description="Tags used for OpenAPI documentation grouping.",
    )

    ARGOCD_AAS_REPO_SLUG: str = Field(
        default="argocd",
        description="Bitbucket repo slug where ArgoCD consumer configs are stored",
    )

    ARGOCD_GITOPS_DEFAULT_BRANCH: str = Field(
        description="Default branch to commit consumer configs to",
        default="master",
    )

    ARGOCD_ALLOWED_SIZES: list[str] = Field(
        default=["extraLarge", "large", "medium", "small"],
        description="ArgoCD instance sizes available in this deployment",
    )

    ARGOCD_ALLOWED_RESOURCES: list[str] = Field(
        default=["ExternalSecret", "ConfigMap", "Deployment"],
        description="Kubernetes resource kinds allowed in include_resources",
    )

    ARGOCD_CLUSTER_SECRET_CHART_PATH: str = Field(
        default="charts/cluster-secret",
        description="Path within the repo to the cluster-secret Helm chart",
    )

    ARGOCD_CLUSTER_SECRET_DEST_SERVER: str = Field(
        default="https://kubernetes.default.svc",
        description="Kubernetes API server URL for the cluster-secret app destination",
    )

    ARGOCD_APP_NAMESPACE: str = Field(
        default="argocd",
        description="Namespace where ArgoCD Application CRDs are stored (metadata.namespace)",
    )

    ARGOCD_APPLICATION_SET_TIMEOUT: int = Field(
        default=300,
        description="Max seconds to wait for an ArgoCD application operation to complete",
    )

    ARGOCD_SCHEME: str = Field(
        default="https",
        description="URL scheme for consumer ArgoCD instances (use 'http' for local dev)",
    )

    ARGOCD_PORT: str = Field(
        default="",
        description="Port for consumer ArgoCD instances — empty means default for the scheme (use '9000' for local dev)",
    )


config = ArgocdConfig()
