from .schemas import ChatMessage, MessageStatus
from typing import Any
from .conf import config
from loguru import logger

async def send_message_operation(chat_client: Any, payload: ChatMessage) -> MessageStatus:
    recipients = payload.recipients
    message = payload.message

    logger.info(f"sending message: {message} to {recipients}")

    body = \
        {
           "channels": ["chat"],
           "message": message,
           "recipients": recipients
        }

    response = await chat_client.post(config.SEND_MESSAGE_ENDPOINT, json=body)

    if response.status_code == 200:
        return MessageStatus(status="sent")

    logger.error(f"Failed to send message: {message} to {recipients}. status_code: {response.status_code}")
    return MessageStatus(status="failed")
