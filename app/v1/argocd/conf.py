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

    ARGOCD_GITOPS_DEFAULT_BRANCH: str = Field(
        default="master",
        description="Default branch to commit consumer configs to",
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


config = ArgocdConfig()
