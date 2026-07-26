from __future__ import annotations

from maxapi.types import BotStarted, MessageCallback, MessageCreated


BotEvent = BotStarted | MessageCallback | MessageCreated


def get_max_user_id(event: BotEvent) -> str | None:
    _chat_id, user_id = event.get_ids()
    if user_id is None:
        return None
    return str(user_id)


def get_message_text(event: MessageCreated) -> str:
    if event.message.body is None or event.message.body.text is None:
        return ""
    return event.message.body.text.strip()
