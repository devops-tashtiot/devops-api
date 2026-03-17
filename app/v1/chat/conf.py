from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, StrictStr

class ChatConfig(BaseSettings):

    SEND_MESSAGE_ENDPOINT: str = Field(
        default="/api",
        description="API endpoint for chat",
    )

    API_PREFIX: str = Field(
        default="/api/example/v1/chat",
        description="API prefix for api exosure",
    )

    API_TAGS: list[str] = Field(
        default=["v1 - Chat Operations"],
        descriptin="Tags used for OpenAPI documentation grouping.",
    )

config = ChatConfig()