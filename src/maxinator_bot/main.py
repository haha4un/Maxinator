import asyncio
from os import getenv

from dotenv import load_dotenv
from maxapi import Bot, Dispatcher, F
from maxapi.filters.command import CommandStart
from maxapi.types import BotStarted, CallbackButton, MessageCallback, MessageCreated
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder


START_TEST_PAYLOAD = "start_test"

dp = Dispatcher()
awaiting_test_code: set[tuple[int | None, int]] = set()


def build_start_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.add(CallbackButton(text="Пройти тест", payload=START_TEST_PAYLOAD))
    return builder


def user_state_key(event: MessageCreated | MessageCallback) -> tuple[int | None, int] | None:
    ids = event.get_ids()
    if ids.user_id is None:
        return None
    return ids.chat_id, ids.user_id


@dp.bot_started()
async def handle_bot_started(event: BotStarted) -> None:
    await event.answer(
        text="Привет! Я помогу пройти тест. Нажмите кнопку ниже, когда будете готовы.",
        attachments=[build_start_keyboard()],
    )


@dp.message_created(CommandStart())
async def handle_start_command(message: MessageCreated) -> None:
    await message.answer(
        text="Привет! Я помогу пройти тест. Нажмите кнопку ниже, когда будете готовы.",
        attachments=[build_start_keyboard()],
    )


@dp.message_callback(F.callback.payload == START_TEST_PAYLOAD)
async def handle_start_test(callback: MessageCallback) -> None:
    key = user_state_key(callback)
    if key is not None:
        awaiting_test_code.add(key)

    await callback.answer(
        new_text="Отправьте код теста следующим сообщением.",
        attachments=[],
    )


@dp.message_created()
async def handle_message(message: MessageCreated) -> None:
    key = user_state_key(message)
    if key not in awaiting_test_code:
        return

    awaiting_test_code.remove(key)
    await message.answer("Код теста получен. Дальнейшая логика пока не реализована.")


async def run_bot() -> None:
    load_dotenv()
    token = getenv("MAX_BOT_TOKEN")
    if not token:
        raise RuntimeError("Set MAX_BOT_TOKEN in environment or .env file")

    bot = Bot(token=token)
    await dp.start_polling(bot)


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
