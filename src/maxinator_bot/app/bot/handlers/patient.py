from __future__ import annotations

import logging
from uuid import UUID

from maxapi import Dispatcher, F
from maxapi.filters.command import Command
from maxapi.types import MessageCallback, MessageCreated

from maxinator_bot.app.bot.callbacks import (
    ANSWER_PREFIX,
    PATIENT_START_TEST,
)
from maxinator_bot.app.bot.formatters import format_question
from maxinator_bot.app.bot.handlers.utils import (
    get_max_user_id,
    get_message_text,
)
from maxinator_bot.app.bot.keyboards import (
    build_admin_menu_keyboard,
    build_patient_menu_keyboard,
)
from maxinator_bot.app.bot.question_media import build_question_attachments
from maxinator_bot.app.domain.enums import BotState
from maxinator_bot.app.services import ServiceContainer
from maxinator_bot.app.services.attempt_service import (
    AssignmentAccessDeniedError,
    AttemptAnswerDeniedError,
    EmptyQuestionnaireError,
)


ACCESS_DENIED_MESSAGE = (
    "Код недействителен или тестирование недоступно."
)
logger = logging.getLogger(__name__)


def register_patient_handlers(
    dispatcher: Dispatcher,
    services: ServiceContainer,
) -> None:
    @dispatcher.message_created(Command("test"))
    async def handle_test_command(event: MessageCreated, args: list[str]) -> None:
        max_user_id = get_max_user_id(event)
        if max_user_id is None or not args:
            await event.send("Использование: /test КОД")
            return

        try:
            progress = await services.attempts.start_or_resume(
                args[0],
                max_user_id,
            )
        except (AssignmentAccessDeniedError, EmptyQuestionnaireError):
            await event.send(ACCESS_DENIED_MESSAGE)
            return

        await event.send(
            format_question(progress),
            attachments=await build_question_attachments(progress),
        )

    @dispatcher.message_callback(
        F.callback.payload == PATIENT_START_TEST,
    )
    async def handle_start_test(callback: MessageCallback) -> None:
        max_user_id = get_max_user_id(callback)
        if max_user_id is None:
            await callback.ack()
            return

        await services.bot_sessions.enter_assignment_code(max_user_id)
        await callback.answer(
            new_text="Введите восьмизначный код тестирования.",
            attachments=[],
        )

    @dispatcher.message_callback(
        F.callback.payload.startswith(ANSWER_PREFIX),
    )
    async def handle_answer(callback: MessageCallback) -> None:
        max_user_id = get_max_user_id(callback)
        parsed = _parse_answer_payload(callback.callback.payload or "")
        if max_user_id is None or parsed is None:
            await callback.ack("Ответ недоступен")
            return

        attempt_question_id, selected_value = parsed
        try:
            outcome = await services.attempts.answer_question(
                attempt_question_id,
                selected_value,
                max_user_id,
            )
        except (AttemptAnswerDeniedError, ValueError):
            await callback.ack("Ответ недоступен")
            return

        if outcome.next_question is not None:
            await callback.answer(
                new_text=format_question(outcome.next_question),
                attachments=await build_question_attachments(outcome.next_question),
            )
            return

        if outcome.completed:
            if callback.bot is not None:
                try:
                    await services.notifications.notify_attempt(
                        outcome.attempt_id,
                        callback.bot,
                        exclude_max_user_id=max_user_id,
                    )
                except Exception:
                    logger.exception(
                        "Failed to notify admins for attempt %s",
                        outcome.attempt_id,
                    )
            if services.admin.is_admin(max_user_id):
                await services.bot_sessions.show_admin_menu(max_user_id)
                completion_keyboard = build_admin_menu_keyboard()
            else:
                completion_keyboard = build_patient_menu_keyboard()
            await callback.answer(
                new_text="Спасибо за тестирование.",
                attachments=[completion_keyboard],
            )
            return

        await callback.ack("Результаты рассчитываются")


async def handle_patient_message(
    event: MessageCreated,
    services: ServiceContainer,
) -> bool:
    max_user_id = get_max_user_id(event)
    if max_user_id is None:
        return False

    bot_session = await services.bot_sessions.get(max_user_id)
    if bot_session.state != BotState.ENTERING_ASSIGNMENT_CODE:
        return False

    try:
        progress = await services.attempts.start_or_resume(
            get_message_text(event),
            max_user_id,
        )
    except (AssignmentAccessDeniedError, EmptyQuestionnaireError):
        await event.send(ACCESS_DENIED_MESSAGE)
        return True

    await event.send(
        format_question(progress),
        attachments=await build_question_attachments(progress),
    )
    return True


def _parse_answer_payload(payload: str) -> tuple[UUID, int] | None:
    raw = payload.removeprefix(ANSWER_PREFIX)
    parts = raw.split(":")
    if len(parts) != 2:
        return None
    try:
        return UUID(parts[0]), int(parts[1])
    except (ValueError, TypeError):
        return None
