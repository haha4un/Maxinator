from maxapi import Dispatcher
from maxapi.types import MessageCreated

from maxinator_bot.app.bot.handlers.admin import (
    handle_admin_message,
    register_admin_handlers,
)
from maxinator_bot.app.bot.handlers.common import register_common_handlers
from maxinator_bot.app.bot.handlers.patient import (
    handle_patient_message,
    register_patient_handlers,
)
from maxinator_bot.app.services import ServiceContainer


def register_handlers(
    dispatcher: Dispatcher,
    services: ServiceContainer,
) -> None:
    register_common_handlers(dispatcher, services)
    register_admin_handlers(dispatcher, services)
    register_patient_handlers(dispatcher, services)

    @dispatcher.message_created()
    async def handle_stateful_message(event: MessageCreated) -> None:
        if await handle_admin_message(event, services):
            return
        await handle_patient_message(event, services)


__all__ = ["register_handlers"]
