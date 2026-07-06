from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class DevopsStaticSettings(BaseSettings):
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
#======================================================artifactory=============================================    
    ARTIFACTORY_ENABLE_API: bool = Field(
        description="enable or disable artifactory api",
        default=True,
    )
    
    ARTIFACTORY_PASSWORD: str = Field(
        description="ARTIFACTORY username's password",
        default="sheker",
    )

    ARTIFACTORY_USERNAME: str = Field(
        description="ARTIFACTORY username",
        default="svc-lcl-artifactory-api",
    )

    ARTIFACTORY_LDAP_SETTING_NAME: str = Field(
        default="ldap-ad",
        description="Name of the LDAP setting configured in JFrog Platform (Admin > Security > LDAP)",
    )
    
    ARTIFACTORY_API_URL: str = Field(
        description="ARTIFACTORY api url",
        default="https://private-artifactory.org",
    )
    ARTIFACTORY_S3_XRAY_UPDATES_BASE_URL: str = Field(
        default="http://localhost:9100/platform-devops-team/xray-vulnerability-updates",
        description="Base URL to the xray-vulnerability-updates subfolder inside the platform-devops-team bucket (no trailing slash)",
    )

#======================================================bitbucket=============================================    

    BITBUCKET_ENABLE_API: bool = Field(
        description="enable or disable bitbucket api",
        default=True,
    )

    BITBUCKET_API_URL: str = Field(
        description="BITBUCKET api url",
        default="https://private-bitbucket.org",
    )

    BITBUCKET_PASSWORD: str = Field(
        description="BITBUCKET username's password",
        default="sheker",
    )

    BITBUCKET_USERNAME: str = Field(
        description="BITBUCKET username",
        default="svc-lcl-bb-api",
    )

#======================================================confluence=============================================    

    CONFLUENCE_ENABLE_API: bool = Field(
        description="enable or disable confluence api",
        default=True,
    )

    CONFLUENCE_API_URL: str = Field(
        description="CONFLUENCE api url",
        default="https://private-confluence.org",
    )

    CONFLUENCE_PASSWORD: str = Field(
        description="CONFLUENCE username's password",
        default="sheker",
    )

    CONFLUENCE_USERNAME: str = Field(
        description="CONFLUENCE username",
        default="svc-lcl-confluence-api",
    )
    CONFLUENCE_S3_PLUGINS_BASE_URL: str = Field(
        default="http://localhost:9100/platform-clients/confluence-plugins",
        description="Base URL to the confluence-plugins subfolder inside the public platform-clients bucket (no trailing slash)",
    )
    CONFLUENCE_S3_IMPORTS_BASE_URL: str = Field(
        default="http://localhost:9100/platform-clients/confluence-space-imports",
        description="Base URL to the confluence-space-imports subfolder inside the public platform-clients bucket (no trailing slash)",
    )
#======================================================jira=============================================    


    JIRA_ENABLE_API: bool = Field(
        description="enable or disable jira api",
        default=True,
    )

    JIRA_API_URL: str = Field(
        description="Jira api url",
        default="https://private-jira.org",
    )

    JIRA_USERNAME: str = Field(
        description="Jira username",
        default="svc-lcl-jira-api",
    )

    JIRA_PASSWORD: str = Field(
        description="Jira username's password",
        default="sheker",
    )

#======================================================sonarqube=============================================    

    SONARQUBE_ENABLE_API: bool = Field(
        description="enable or disable sonarqube api",
        default=True,
    )

    SONARQUBE_USERNAME: str = Field(
        description="SonarQube admin username",
        default="admin",
    )

    SONARQUBE_ALLOWED_SIZES: list[str] = Field(
        default=["default", "medium", "big"],
        description="SonarQube instance sizes available in this deployment",
    )
    SONARQUBE_PASSWORD: str = Field(
        description="SonarQube admin password",
        default="sheker",
    )

    SONARQUBE_AAS_REPO_SLUG: str = Field(
        default="sonarqube-as-a-service",
        description="Bitbucket repo slug for the SonarQube GitOps consumer configs",
    )

#======================================================argocd=============================================    

    ARGOCD_ENABLE_API: bool = Field(
        description="enable or disable argocd consumer config api",
        default=True,
    )

# from argocd repo url the networks there
    ARGOCD_ALLOWED_ENVS: list[str] = Field(
        default=["prod", "dr", "int"],
        description="Environments allowed in this network deployment",
    )
    ARGOCD_CLUSTER_SECRET_REPO_URL: str = Field(
        description="Full Git URL of the repo containing the cluster-secret Helm chart",
        default="https://private-bitbucket.org/scm/DEVOPS/argocd-configs.git",
    )

    ARGOCD_AAS_REPO_SLUG: str = Field(
        default="argocd",
        description="Bitbucket repo slug where ArgoCD consumer configs are stored",
    )

    ARGOCD_ALLOWED_SIZES: list[str] = Field(
        default=["extraLarge", "large", "medium", "small"],
        description="ArgoCD instance sizes available in this deployment",
    )

    ARGOCD_ALLOWED_RESOURCES: list[str] = Field(
        default=["ExternalSecret", "ConfigMap", "Deployment"],
        description="Kubernetes resource kinds allowed in include_resources",
    )

#=========================================================gitops-connector=======================================
# for working against gitops repos
    GIT_API_URL: str = Field(
        description="Git (Bitbucket) server URL",
        default="https://private-bitbucket.org",
    )

    GIT_TOKEN: str = Field(
        description="Git personal access token",
        default="sheker",
    )

    GIT_USERNAME: str = Field(
        description="Git username",
        default="svc-lcl-git-api",
    )

    GIT_PROJECT_KEY: str = Field(
        description="Bitbucket project key containing the target repo",
        default="DEVOPS",
    )
#should be mounted to the deployment
    GIT_SSH_KEY_PATH: str = Field(
        description="Path to the SSH private key used by the Git connector",
        default="/etc/.ssh/private_key",
    )
    GIT_SSH_PORT: str = Field(
        description="SSH Port used by the Git connector",
        default="7999",
    )

#======================================================general=============================================    

    DOMAIN_SUFFIX: str = Field(
        default="app.iaf",
        description="Shared domain suffix used across services — e.g. ArgoCD: https://{name}-argocd.{DOMAIN_SUFFIX}, SonarQube: https://{consumer}.sonarqube.{DOMAIN_SUFFIX}",
    )




global_config = DevopsStaticSettings()