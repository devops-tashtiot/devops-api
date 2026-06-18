from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class DevopsStaticSettings(BaseSettings):
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    ENABLE_ARTIFACTORY_API: bool = Field(
        description="enable or disable artifactory api",
        default=True,
    )
    
    ARTIFACTORY_API_TOKEN: str = Field(
        description="ARTIFACTORY API token",
        default="sheker_token",
    )

    ARTIFACTORY_LDAP_SETTING_NAME: str = Field(
        default="ldap-ad",
        description="Name of the LDAP setting configured in JFrog Platform (Admin > Security > LDAP)",
    )
    
    ARTIFACTORY_API_URL: str = Field(
        description="ARTIFACTORY api url",
        default="https://private-artifactory.org",
    )
    
    ENABLE_BITBUCKET_API: bool = Field(
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

    ENABLE_CONFLUENCE_API: bool = Field(
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

    ENABLE_JIRA_API: bool = Field(
        description="enable or disable jira api",
        default=True,
    )

    JIRA_API_URL: str = Field(
        description="Jira api url",
        default="https://private-jira.org",
    )

    JIRA_PASSWORD: str = Field(
        description="Jira username's password",
        default="sheker",
    )

    JIRA_USERNAME: str = Field(
        description="Jira username",
        default="svc-lcl-jira-api",
    )

    ENABLE_SONARQUBE_API: bool = Field(
        description="enable or disable sonarqube api",
        default=True,
    )

    SONARQUBE_PASSWORD: str = Field(
        description="SonarQube admin password",
        default="sheker",
    )

    SONARQUBE_USERNAME: str = Field(
        description="SonarQube admin username",
        default="admin",
    )

    ENABLE_ARGOCD_API: bool = Field(
        description="enable or disable argocd consumer config api",
        default=True,
    )

# from argocd repo url the networks there
    ARGOCD_ALLOWED_ENVS: list[str] = Field(
        default=["prod", "dr", "int"],
        description="Environments allowed in this network deployment",
    )

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

    ARGOCD_CLUSTER_SECRET_REPO_URL: str = Field(
        description="Full Git URL of the repo containing the cluster-secret Helm chart",
        default="https://private-bitbucket.org/scm/DEVOPS/argocd-configs.git",
    )

    DOMAIN_SUFFIX: str = Field(
        default="app.iaf",
        description="Shared domain suffix used across services — e.g. ArgoCD: https://{name}-argocd.{DOMAIN_SUFFIX}, SonarQube: https://{consumer}.sonarqube.{DOMAIN_SUFFIX}",
    )

    GIT_SSH_KEY_PATH: str = Field(
        description="Path to the SSH private key used by the Git connector",
        default="/etc/.ssh/private_key",
    )

    S3_IMPORTS_BASE_URL: str = Field(
        default="http://localhost:9100/confluence-space-imports",
        description="Public base URL to the S3 space-imports directory (no trailing slash)",
    )

    ENABLE_CONFLUENCE_PLUGIN_API: bool = Field(
        description="enable or disable confluence plugin api",
        default=True,
    )

    S3_PLUGINS_BASE_URL: str = Field(
        default="http://localhost:9100/confluence-plugins",
        description="Public base URL to the S3 plugins directory (no trailing slash)",
    )


global_config = DevopsStaticSettings()