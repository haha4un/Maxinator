from __future__ import annotations

from uuid import UUID

from maxapi import Dispatcher, F
from maxapi.types import MessageCallback, MessageCreated

from maxinator_bot.app.bot.callbacks import (
    ADMIN_ASSIGN,
    ADMIN_BACK,
    ADMIN_ENTER_PATIENT_CODE,
    ADMIN_NEW_PATIENT,
    ADMIN_PATIENT_PAGE_PREFIX,
    ADMIN_PATIENT_PREFIX,
    ADMIN_PREFIX,
    ADMIN_QUESTIONNAIRE_PREFIX,
    ADMIN_RESULTS,
    ADMIN_RESULT_PREFIX,
    ADMIN_RESULTS_SEARCH,
)
from maxinator_bot.app.bot.formatters import (
    format_assignment_created,
    format_patient_created,
    format_patient_selection,
    format_attempt_result,
)
from maxinator_bot.app.bot.handlers.utils import (
    get_max_user_id,
    get_message_text,
)
from maxinator_bot.app.bot.keyboards import (
    build_admin_menu_keyboard,
    build_patient_selection_keyboard,
    build_questionnaire_selection_keyboard,
    build_result_back_keyboard,
    build_results_keyboard,
)
from maxinator_bot.app.bot.keyboards.admin import build_admin_back_keyboard
from maxinator_bot.app.domain.enums import BotState
from maxinator_bot.app.services import ServiceContainer
from maxinator_bot.app.services.assignment_service import (
    AssignmentNotAvailableError,
)


def register_admin_handlers(
    dispatcher: Dispatcher,
    services: ServiceContainer,
) -> None:
    @dispatcher.message_callback(
        F.callback.payload.startswith(ADMIN_PREFIX),
    )
    async def handle_admin_callback(callback: MessageCallback) -> None:
        max_user_id = get_max_user_id(callback)
        if max_user_id is None:
            await callback.ack()
            return
        if not services.admin.is_admin(max_user_id):
            await callback.ack("Действие недоступно")
            return

        payload = callback.callback.payload or ""
        if payload == ADMIN_NEW_PATIENT:
            await _create_patient(callback, max_user_id, services)
        elif payload == ADMIN_ASSIGN:
            await _show_patients(callback, max_user_id, services, page=0)
        elif payload.startswith(ADMIN_PATIENT_PAGE_PREFIX):
            page = _parse_page(payload)
            await _show_patients(
                callback,
                max_user_id,
                services,
                page=page,
            )
        elif payload == ADMIN_ENTER_PATIENT_CODE:
            await services.bot_sessions.enter_patient_code(max_user_id)
            await callback.answer(
                new_text="Введите шестизначный код пациента.",
                attachments=[build_admin_back_keyboard()],
            )
        elif payload.startswith(ADMIN_PATIENT_PREFIX):
            await _select_patient(
                callback,
                max_user_id,
                services,
                payload,
            )
        elif payload.startswith(ADMIN_QUESTIONNAIRE_PREFIX):
            await _create_assignment(
                callback,
                max_user_id,
                services,
                payload,
            )
        elif payload == ADMIN_RESULTS:
            await _show_recent_results(
                callback,
                max_user_id,
                services,
            )
        elif payload == ADMIN_RESULTS_SEARCH:
            await services.bot_sessions.search_results(max_user_id)
            await callback.answer(
                new_text="Введите шестизначный код пациента.",
                attachments=[build_admin_back_keyboard()],
            )
        elif payload.startswith(ADMIN_RESULT_PREFIX):
            await _show_attempt_result(
                callback,
                services,
                payload,
            )
        elif payload == ADMIN_BACK:
            await _show_admin_menu(callback, max_user_id, services)
        else:
            await callback.ack("Неизвестное действие")

async def _create_patient(
    callback: MessageCallback,
    max_user_id: str,
    services: ServiceContainer,
) -> None:
    patient = await services.patients.create_patient()
    await services.bot_sessions.show_admin_menu(max_user_id)
    await callback.answer(
        new_text=format_patient_created(patient),
        attachments=[build_admin_menu_keyboard()],
    )


async def handle_admin_message(
    event: MessageCreated,
    services: ServiceContainer,
) -> bool:
    max_user_id = get_max_user_id(event)
    if (
        max_user_id is None
        or not services.admin.is_admin(max_user_id)
    ):
        return False

    bot_session = await services.bot_sessions.get(max_user_id)
    if (
        bot_session.state == BotState.VIEWING_RESULTS
        and bot_session.context
        and bot_session.context.get("mode") == "patient_code_search"
    ):
        await _handle_result_search_message(
            event,
            max_user_id,
            services,
        )
        return True

    if bot_session.state != BotState.ENTERING_PATIENT_CODE:
        return False

    public_code = get_message_text(event).replace(" ", "")
    if not services.code_generator.is_valid(
        public_code,
        services.settings.patient_code_length,
    ):
        await event.send(
            "Код пациента должен состоять из шести цифр.",
            attachments=[build_admin_back_keyboard()],
        )
        return True

    patient = await services.patients.get_active_by_code(public_code)
    if patient is None:
        await event.send(
            "Активный пациент с таким кодом не найден.",
            attachments=[build_admin_back_keyboard()],
        )
        return True

    await services.bot_sessions.choose_questionnaire(
        max_user_id,
        patient.id,
    )
    questionnaires = (
        await services.assignments.list_active_questionnaires()
    )
    await event.send(
        _questionnaire_prompt(questionnaires),
        attachments=[
            build_questionnaire_selection_keyboard(questionnaires),
        ],
    )
    return True


async def _handle_result_search_message(
    event: MessageCreated,
    max_user_id: str,
    services: ServiceContainer,
) -> None:
    public_code = get_message_text(event).replace(" ", "")
    if not services.code_generator.is_valid(
        public_code,
        services.settings.patient_code_length,
    ):
        await event.send(
            "Код пациента должен состоять из шести цифр.",
            attachments=[build_admin_back_keyboard()],
        )
        return

    attempts = await services.results.list_patient_attempts(public_code)
    await services.bot_sessions.view_results(max_user_id)
    text = (
        f"Завершённые тестирования пациента {public_code}."
        if attempts
        else "Завершённые тестирования не найдены."
    )
    await event.send(
        text,
        attachments=[build_results_keyboard(attempts)],
    )


async def _show_patients(
    callback: MessageCallback,
    max_user_id: str,
    services: ServiceContainer,
    *,
    page: int,
) -> None:
    patients = await services.patients.list_active(page, page_size=10)
    await services.bot_sessions.choose_patient(
        max_user_id,
        page=patients.page,
    )
    await callback.answer(
        new_text=format_patient_selection(patients),
        attachments=[build_patient_selection_keyboard(patients)],
    )


async def _select_patient(
    callback: MessageCallback,
    max_user_id: str,
    services: ServiceContainer,
    payload: str,
) -> None:
    patient_id = _parse_uuid(payload.removeprefix(ADMIN_PATIENT_PREFIX))
    if patient_id is None:
        await callback.ack("Некорректный пациент")
        return

    patient = await services.patients.get_active_by_id(patient_id)
    if patient is None:
        await callback.ack("Пациент недоступен")
        return

    await services.bot_sessions.choose_questionnaire(
        max_user_id,
        patient.id,
    )
    questionnaires = await services.assignments.list_active_questionnaires()
    await callback.answer(
        new_text=_questionnaire_prompt(questionnaires),
        attachments=[
            build_questionnaire_selection_keyboard(questionnaires),
        ],
    )


async def _create_assignment(
    callback: MessageCallback,
    max_user_id: str,
    services: ServiceContainer,
    payload: str,
) -> None:
    questionnaire_id = _parse_uuid(
        payload.removeprefix(ADMIN_QUESTIONNAIRE_PREFIX),
    )
    bot_session = await services.bot_sessions.get(max_user_id)
    if (
        questionnaire_id is None
        or bot_session.state != BotState.CHOOSING_QUESTIONNAIRE
        or bot_session.selected_patient_id is None
    ):
        await callback.ack("Сначала выберите пациента")
        return

    try:
        assignment, patient, questionnaire = (
            await services.assignments.create_assignment(
                patient_id=bot_session.selected_patient_id,
                questionnaire_id=questionnaire_id,
                admin_max_user_id=max_user_id,
            )
        )
    except AssignmentNotAvailableError:
        await callback.ack("Пациент или опросник недоступен")
        return

    await services.bot_sessions.show_admin_menu(max_user_id)
    await callback.answer(
        new_text=format_assignment_created(
            assignment,
            patient,
            questionnaire,
        ),
        attachments=[build_admin_menu_keyboard()],
    )


async def _show_admin_menu(
    callback: MessageCallback,
    max_user_id: str,
    services: ServiceContainer,
) -> None:
    await services.bot_sessions.show_admin_menu(max_user_id)
    await callback.answer(
        new_text="Панель администратора.",
        attachments=[build_admin_menu_keyboard()],
    )


async def _show_recent_results(
    callback: MessageCallback,
    max_user_id: str,
    services: ServiceContainer,
) -> None:
    attempts = await services.results.list_recent_completed(limit=10)
    await services.bot_sessions.view_results(max_user_id)
    text = (
        "Последние завершённые тестирования."
        if attempts
        else "Завершённых тестирований пока нет."
    )
    await callback.answer(
        new_text=text,
        attachments=[build_results_keyboard(attempts)],
    )


async def _show_attempt_result(
    callback: MessageCallback,
    services: ServiceContainer,
    payload: str,
) -> None:
    attempt_id = _parse_uuid(
        payload.removeprefix(ADMIN_RESULT_PREFIX),
    )
    if attempt_id is None:
        await callback.ack("Некорректный результат")
        return
    result = await services.results.get_attempt_result(attempt_id)
    if result is None:
        await callback.ack("Результат недоступен")
        return
    await callback.answer(
        new_text=format_attempt_result(result),
        attachments=[build_result_back_keyboard()],
    )


def _questionnaire_prompt(questionnaires: list[object]) -> str:
    if not questionnaires:
        return "Нет активных опросников."
    return "Выберите опросник."


def _parse_page(payload: str) -> int:
    raw_page = payload.removeprefix(ADMIN_PATIENT_PAGE_PREFIX)
    try:
        return max(0, int(raw_page))
    except ValueError:
        return 0


def _parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        return None
