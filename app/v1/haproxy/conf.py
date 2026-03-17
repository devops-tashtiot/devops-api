from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, StrictStr

class HaProxyConfig(BaseSettings):

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Resource-specific
    HAPROXY_VALUES_REPO_URL: str = Field(
        ..., description="HaProxy values repo URL"
    )

    HAPROXY_VALUES_REPO_ACCESS_TOKEN: str = Field(
        ..., description="HaProxy values repo token"
    )

    HAPROXY_VALUES_REPO_SLUG: str = Field(..., description="HaProxy values repo slug")
    HAPROXY_REPO_PROJECT_KEY: str = Field(..., description="HaProxy values repo project key")
    HAPROXY_VALUES_REPO_EMAIL: str = Field(..., description="HaProxy values repo email")

    HAPROXY_VALUES_REPO_SSH_KEY_PATH: str = Field(..., description="Path to ssh key, used to connect to type-rage values bb repo.")

    CLUSTERS: list[str] = Field(description="A list of clusters where resources could be created.") 

    API_PREFIX: StrictStr = Field(default="/api/example/v1/haproxy", description="HaProxy error ")

    API_TAGS: list[str] = Field(default=["v1 - HaProxy Operations"] ,descriptin="Tags used for OpenAPI documentation grouping.")

config = HaProxyConfig()