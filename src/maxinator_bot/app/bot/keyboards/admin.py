from __future__ import annotations

from maxapi.types import CallbackButton
from maxapi.types.attachments.buttons.attachment_button import AttachmentButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

from maxinator_bot.app.bot.callbacks import (
    ADMIN_ASSIGN,
    ADMIN_START_TEST,
    ADMIN_BACK,
    ADMIN_ENTER_PATIENT_CODE,
    ADMIN_NEW_PATIENT,
    ADMIN_PATIENT_PAGE_PREFIX,
    ADMIN_PATIENT_PREFIX,
    ADMIN_QUESTIONNAIRE_PREFIX,
    ADMIN_RESULTS,
    ADMIN_RESULT_PREFIX,
    ADMIN_RESULTS_SEARCH,
)
from maxinator_bot.app.database.models import Patient, Questionnaire
from maxinator_bot.app.domain.models import Page
from maxinator_bot.app.domain.models import CompletedAttemptSummary


def callback_button(text: str, payload: str) -> CallbackButton:
    return CallbackButton(text=text, payload=payload)


def build_admin_menu_keyboard() -> AttachmentButton:
    builder = InlineKeyboardBuilder()
    builder.row(callback_button("Новый пациент", ADMIN_NEW_PATIENT))
    builder.row(callback_button("Назначить тестирование", ADMIN_ASSIGN))
    builder.row(callback_button("Начать тестирование", ADMIN_START_TEST))
    builder.row(callback_button("Результаты", ADMIN_RESULTS))
    return builder.as_markup()


def build_patient_selection_keyboard(
    patients: Page[Patient],
) -> AttachmentButton:
    builder = InlineKeyboardBuilder()
    for patient in patients.items:
        label = patient.public_code
        if patient.display_name:
            label = f"{label} - {patient.display_name}"
        builder.row(
            callback_button(
                label,
                f"{ADMIN_PATIENT_PREFIX}{patient.id}",
            ),
        )

    pagination: list[CallbackButton] = []
    if patients.has_previous:
        pagination.append(
            callback_button(
                "Назад",
                f"{ADMIN_PATIENT_PAGE_PREFIX}{patients.page - 1}",
            ),
        )
    if patients.has_next:
        pagination.append(
            callback_button(
                "Далее",
                f"{ADMIN_PATIENT_PAGE_PREFIX}{patients.page + 1}",
            ),
        )
    if pagination:
        builder.row(*pagination)

    builder.row(
        callback_button(
            "Ввести код пациента",
            ADMIN_ENTER_PATIENT_CODE,
        ),
    )
    builder.row(callback_button("Назад", ADMIN_BACK))
    return builder.as_markup()


def build_questionnaire_selection_keyboard(
    questionnaires: list[Questionnaire],
) -> AttachmentButton:
    builder = InlineKeyboardBuilder()
    for questionnaire in questionnaires:
        builder.row(
            callback_button(
                f"{questionnaire.title} (v{questionnaire.version})",
                f"{ADMIN_QUESTIONNAIRE_PREFIX}{questionnaire.id}",
            ),
        )
    builder.row(callback_button("Назад", ADMIN_BACK))
    return builder.as_markup()


def build_admin_back_keyboard() -> AttachmentButton:
    builder = InlineKeyboardBuilder()
    builder.add(callback_button("Назад", ADMIN_BACK))
    return builder.as_markup()


def build_results_keyboard(
    attempts: list[CompletedAttemptSummary],
) -> AttachmentButton:
    builder = InlineKeyboardBuilder()
    for attempt in attempts:
        date_text = attempt.completed_at.astimezone().strftime(
            "%d.%m.%Y %H:%M",
        )
        title = attempt.questionnaire_title
        if len(title) > 40:
            title = f"{title[:37]}..."
        builder.row(
            callback_button(
                f"{attempt.patient_code} - {title} - {date_text}",
                f"{ADMIN_RESULT_PREFIX}{attempt.attempt_id}",
            ),
        )
    builder.row(
        callback_button(
            "Поиск по коду пациента",
            ADMIN_RESULTS_SEARCH,
        ),
    )
    builder.row(callback_button("Назад", ADMIN_BACK))
    return builder.as_markup()


def build_result_back_keyboard() -> AttachmentButton:
    builder = InlineKeyboardBuilder()
    builder.add(callback_button("Назад", ADMIN_RESULTS))
    return builder.as_markup()
