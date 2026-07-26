from maxapi.types import CallbackButton
from maxapi.types.attachments.buttons.attachment_button import AttachmentButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

from uuid import UUID

from maxinator_bot.app.bot.callbacks import ANSWER_PREFIX, PATIENT_START_TEST
from maxinator_bot.app.domain.constants import ANSWER_OPTIONS


def build_patient_menu_keyboard() -> AttachmentButton:
    builder = InlineKeyboardBuilder()
    builder.add(
        CallbackButton(
            text="Пройти тестирование",
            payload=PATIENT_START_TEST,
        ),
    )
    return builder.as_markup()


def build_answer_keyboard(
    attempt_question_id: UUID,
) -> AttachmentButton:
    builder = InlineKeyboardBuilder()
    for value, title in ANSWER_OPTIONS.items():
        builder.row(
            CallbackButton(
                text=f"{value} — {title}",
                payload=f"{ANSWER_PREFIX}{attempt_question_id}:{value}",
            ),
        )
    return builder.as_markup()
