from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from maxinator_bot.app.config import Settings
from maxinator_bot.app.database.errors import is_constraint_violation
from maxinator_bot.app.database.models import Patient
from maxinator_bot.app.database.repositories import PatientRepository
from maxinator_bot.app.domain.models import Page
from maxinator_bot.app.services.code_generator import CodeGenerator


class PatientCodeGenerationError(RuntimeError):
    pass


class PatientService:
    CODE_CONSTRAINT = "ix_patients_public_code"

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        code_generator: CodeGenerator,
        *,
        max_code_attempts: int = 10,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.code_generator = code_generator
        self.max_code_attempts = max_code_attempts

    async def create_patient(
        self,
        *,
        display_name: str | None = None,
        admin_comment: str | None = None,
    ) -> Patient:
        for _ in range(self.max_code_attempts):
            code = self.code_generator.patient_code(
                self.settings.patient_code_length,
            )
            try:
                async with self.session_factory() as session:
                    async with session.begin():
                        patient = Patient(
                            public_code=code,
                            display_name=display_name,
                            admin_comment=admin_comment,
                        )
                        await PatientRepository(session).add(patient)
                    return patient
            except IntegrityError as exc:
                if not is_constraint_violation(exc, self.CODE_CONSTRAINT):
                    raise

        raise PatientCodeGenerationError(
            "Could not generate a unique patient code",
        )

    async def get_active_by_id(self, patient_id: UUID) -> Patient | None:
        async with self.session_factory() as session:
            return await PatientRepository(session).get_active_by_id(
                patient_id,
            )

    async def get_active_by_code(self, public_code: str) -> Patient | None:
        async with self.session_factory() as session:
            return await PatientRepository(session).get_active_by_code(
                public_code,
            )

    async def list_active(
        self,
        page: int,
        page_size: int = 10,
    ) -> Page[Patient]:
        async with self.session_factory() as session:
            return await PatientRepository(session).list_active(
                page,
                page_size,
            )
