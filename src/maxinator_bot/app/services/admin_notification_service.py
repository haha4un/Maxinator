from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from maxapi import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from maxinator_bot.app.config import Settings
from maxinator_bot.app.database.repositories import ResultRepository


class AdminNotificationService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self.session_factory = session_factory
        self.admin_max_ids = settings.admin_max_ids

    async def notify_attempt(
        self,
        attempt_id: UUID,
        bot: Bot,
        exclude_max_user_id: str | None = None,
    ) -> None:
        if not self.admin_max_ids:
            return

        async with self.session_factory() as session:
            async with session.begin():
                rows = await ResultRepository(
                    session,
                ).lock_pending_alert_rows(attempt_id)
                for (
                    alert,
                    patient_code,
                    questionnaire_title,
                    category_name,
                    level_title,
                ) in rows:
                    text = (
                        "Результат опросника требует внимания.\n\n"
                        f"Пациент: {patient_code}\n"
                        f"Опросник: {questionnaire_title}\n"
                        f"Категория: {category_name}\n"
                        f"Уровень: {level_title}\n\n"
                        "Результат не является медицинским диагнозом."
                    )
                    sent = False
                    for admin_id in self.admin_max_ids:
                        if admin_id == exclude_max_user_id:
                            continue
                        if not admin_id.isascii() or not admin_id.isdigit():
                            continue
                        await bot.send_message(
                            user_id=int(admin_id),
                            text=text,
                        )
                        sent = True
                    if sent:
                        alert.notified_at = datetime.now(timezone.utc)
