from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from maxinator_bot.app.database.models import BotSession
from maxinator_bot.app.database.repositories import BotSessionRepository
from maxinator_bot.app.domain.enums import BotState


class BotSessionService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.session_factory = session_factory

    async def get(self, max_user_id: str) -> BotSession:
        async with self.session_factory() as session:
            async with session.begin():
                return await BotSessionRepository(session).get_or_create(
                    max_user_id,
                )

    async def show_admin_menu(self, max_user_id: str) -> BotSession:
        return await self._update(
            max_user_id,
            state=BotState.ADMIN_MENU,
            selected_patient_id=None,
            selected_questionnaire_id=None,
            active_attempt_id=None,
            page=None,
            context=None,
        )

    async def show_patient_menu(self, max_user_id: str) -> BotSession:
        return await self._update(
            max_user_id,
            state=BotState.IDLE,
            selected_patient_id=None,
            selected_questionnaire_id=None,
            page=None,
            context=None,
        )

    async def choose_patient(
        self,
        max_user_id: str,
        *,
        page: int = 0,
    ) -> BotSession:
        return await self._update(
            max_user_id,
            state=BotState.CHOOSING_PATIENT,
            selected_patient_id=None,
            selected_questionnaire_id=None,
            page=max(0, page),
            context=None,
        )

    async def enter_patient_code(self, max_user_id: str) -> BotSession:
        return await self._update(
            max_user_id,
            state=BotState.ENTERING_PATIENT_CODE,
            selected_patient_id=None,
            selected_questionnaire_id=None,
            page=None,
            context=None,
        )

    async def enter_assignment_code(self, max_user_id: str) -> BotSession:
        return await self._update(
            max_user_id,
            state=BotState.ENTERING_ASSIGNMENT_CODE,
            selected_patient_id=None,
            selected_questionnaire_id=None,
            active_attempt_id=None,
            page=None,
            context=None,
        )

    async def choose_questionnaire(
        self,
        max_user_id: str,
        patient_id: UUID,
    ) -> BotSession:
        return await self._update(
            max_user_id,
            state=BotState.CHOOSING_QUESTIONNAIRE,
            selected_patient_id=patient_id,
            selected_questionnaire_id=None,
            page=None,
            context=None,
        )

    async def view_results(self, max_user_id: str) -> BotSession:
        return await self._update(
            max_user_id,
            state=BotState.VIEWING_RESULTS,
            selected_patient_id=None,
            selected_questionnaire_id=None,
            page=0,
            context=None,
        )

    async def search_results(self, max_user_id: str) -> BotSession:
        return await self._update(
            max_user_id,
            state=BotState.VIEWING_RESULTS,
            selected_patient_id=None,
            selected_questionnaire_id=None,
            page=None,
            context={"mode": "patient_code_search"},
        )

    async def _update(
        self,
        max_user_id: str,
        **values: object,
    ) -> BotSession:
        async with self.session_factory() as session:
            async with session.begin():
                return await BotSessionRepository(session).update(
                    max_user_id,
                    **values,
                )
