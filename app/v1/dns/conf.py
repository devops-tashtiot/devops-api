# ─────────────────────────────────────────────────────────────────────────────
#   Imports
from typing import List

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DnsV1StaticSettings(BaseSettings):
    """Settings for the DNS v1 API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    API_DESCRIPTION: str = Field(
        description="Human‑readable description of the FastAPI application",
        default="An example template for building FastAPI applications",
    )

    API_PREFIX: str = Field(
        description="Root path under which the API is served",
        default="/api/example/v1/dns",
    )

    API_TAGS: List[str] = Field(
        description="Tags used for OpenAPI documentation grouping",
        default_factory=lambda: ["v1 - DNS Operations"],
    )

    AWX_CREATE_DNS_TEMPLATE_ID: int = Field(
        description="The id of the AWX *create DNS* template",
        default=2178,
    )

    AWX_DELETE_DNS_TEMPLATE_ID: int = Field(
        description="The id of the AWX *delete DNS* template",
        default=2179,
    )


config = DnsV1StaticSettings()