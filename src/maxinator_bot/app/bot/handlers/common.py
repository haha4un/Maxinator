from __future__ import annotations

from maxapi import Dispatcher
from maxapi.filters.command import CommandStart
from maxapi.types import BotStarted, MessageCreated

from maxinator_bot.app.bot.handlers.utils import get_max_user_id
from maxinator_bot.app.bot.formatters import format_question
from maxinator_bot.app.bot.keyboards import (
    build_admin_menu_keyboard,
    build_patient_menu_keyboard,
)
from maxinator_bot.app.bot.question_media import build_question_attachments
from maxinator_bot.app.domain.enums import BotState
from maxinator_bot.app.services import ServiceContainer


ADMIN_GREETING = "Панель администратора."
PATIENT_GREETING = (
    "Привет! Здесь можно пройти назначенное тестирование."
)


def register_common_handlers(
    dispatcher: Dispatcher,
    services: ServiceContainer,
) -> None:
    @dispatcher.bot_started()
    async def handle_bot_started(event: BotStarted) -> None:
        await _show_home(event, services)

    @dispatcher.message_created(CommandStart())
    async def handle_start(event: MessageCreated) -> None:
        await _show_home(event, services)


async def _show_home(
    event: BotStarted | MessageCreated,
    services: ServiceContainer,
) -> None:
    max_user_id = get_max_user_id(event)
    if max_user_id is None:
        return

    if services.admin.is_admin(max_user_id):
        await services.bot_sessions.show_admin_menu(max_user_id)
        await event.send(
            ADMIN_GREETING,
            attachments=[build_admin_menu_keyboard()],
        )
        return

    bot_session = await services.bot_sessions.get(max_user_id)
    if (
        bot_session.state == BotState.TAKING_QUESTIONNAIRE
        and bot_session.active_attempt_id is not None
    ):
        progress = await services.attempts.resume_active(
            bot_session.active_attempt_id,
            max_user_id,
        )
        if progress is not None:
            await event.send(
                format_question(progress),
                attachments=await build_question_attachments(progress),
            )
            return

    await services.bot_sessions.show_patient_menu(max_user_id)
    await event.send(
        PATIENT_GREETING,
        attachments=[build_patient_menu_keyboard()],
    )
