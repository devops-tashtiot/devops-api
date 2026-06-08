from pydantic_settings import BaseSettings
from pydantic import Field


class ArgocdConfig(BaseSettings):

    API_PREFIX: str = Field(
        default="/api/devops/latest/argocd",
        description="API prefix for api exposure",
    )

    API_TAGS: list[str] = Field(
        default=["v1 - ArgoCD Operations"],
        description="Tags used for OpenAPI documentation grouping.",
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



config = ArgocdConfig()
