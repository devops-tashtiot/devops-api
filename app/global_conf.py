from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class ExampleStaticSettings(BaseSettings):

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    API_TITLE: str = Field(
        description="API title for the swagger", 
        default="Domain Services API - Example API",
    )

    AWX_URL: str = Field(
        description="AWX base URL",
        default="https://web.awx.app.com/",
    )

    AWX_TOKEN: str = Field(
        description="AWX token for the AWX client",
        default="sheker123",
    )

    CHAT_API_URL: str = Field(
        description="CHAT api url",
        default="https://sendman.com",
    )

    CHAT_API_TOKEN: str = Field(
        description="CHAT API token",
        default="sheker_token",
    )
    
    # Shared service config
    ARGOCD_URL: str = Field(description="The service owner's ArgoCD URL.")
    ARGOCD_TOKEN: str = Field(description="The service owner's ArgoCD token.")
    APPLICATION_SET_TIMEOUT: Optional[int] = Field(default=60, description="Seconds to wait for appset operations.")

    VAULT_URL: str = Field(description="Base URL for HashiCorp Vault")
    VAULT_TOKEN: str = Field(description="Token used to authenticate to Vault.")

    TEAM_NAME: str = Field(description="Team name used as Vault mount path prefix.")

global_config = ExampleStaticSettings()