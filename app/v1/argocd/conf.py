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

    # Outbound SSO — devops-api authenticates its own calls to ArgoCD's API via a
    # client_credentials token instead of a caller-supplied static ArgoCD API token. See
    # clusters-provision/clusters/rhbk (argocdServiceClient + devops-api-argocd-audience
    # client scope) and devtools-definition/devtools/argocd's policy.csv (devops-api-argocd-svc
    # RBAC role) for the Keycloak/ArgoCD-side half of this.
    ARGOCD_SSO_TOKEN_URL: str = Field(
        default="https://rhbk.devopstashtiot.page/realms/devtools/protocol/openid-connect/token",
        description="Keycloak token endpoint for minting devops-api's outbound ArgoCD service-account token",
    )

    ARGOCD_SSO_CLIENT_ID: str = Field(
        default="devops-api-argocd",
        description="Keycloak client ID for devops-api's outbound ArgoCD service account",
    )

    ARGOCD_SSO_CLIENT_SECRET: str = Field(
        default="",
        description="Keycloak client secret for devops-api's outbound ArgoCD service account",
    )

    ARGOCD_SSO_SCOPE: str = Field(
        default="devops-api-argocd-audience",
        description="Client scope requested when minting the ArgoCD service-account token (stamps aud=argocd and the devops-api-argocd-svc RBAC group)",
    )


config = ArgocdConfig()
