from .schemas import ChatMessage, MessageStatus
from typing import Any
from .operations import send_message_operation
from fastapi import APIRouter
from .conf import config

def get_v1_chat_router(chat_client: Any):

    router = APIRouter(prefix=config.API_PREFIX, tags = config.API_TAGS)

    @router.post("/", name="Send message", status_code=201)
    async def send_message(payload: ChatMessage) -> MessageStatus:
        return await send_message_operation(chat_client, payload)

    return router