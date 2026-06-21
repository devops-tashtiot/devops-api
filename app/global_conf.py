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

global_config = DevopsStaticSettings()
