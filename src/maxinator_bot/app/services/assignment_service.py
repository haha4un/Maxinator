from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from maxinator_bot.app.config import Settings
from maxinator_bot.app.database.errors import is_constraint_violation
from maxinator_bot.app.database.models import (
    Patient,
    Questionnaire,
    TestAssignment,
)
from maxinator_bot.app.database.repositories import (
    AssignmentRepository,
    PatientRepository,
    QuestionnaireRepository,
)
from maxinator_bot.app.services.code_generator import CodeGenerator


class AssignmentNotAvailableError(RuntimeError):
    pass


class AssignmentCodeGenerationError(RuntimeError):
    pass


class AssignmentService:
    CODE_CONSTRAINT = "ix_test_assignments_access_code"

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

    async def list_active_questionnaires(self) -> list[Questionnaire]:
        async with self.session_factory() as session:
            return await QuestionnaireRepository(session).list_active()

    async def create_assignment(
        self,
        *,
        patient_id: UUID,
        questionnaire_id: UUID,
        admin_max_user_id: str,
    ) -> tuple[TestAssignment, Patient, Questionnaire]:
        for _ in range(self.max_code_attempts):
            code = self.code_generator.assignment_code(
                self.settings.assignment_code_length,
            )
            try:
                async with self.session_factory() as session:
                    async with session.begin():
                        patients = PatientRepository(session)
                        questionnaires = QuestionnaireRepository(session)
                        patient = await patients.get_active_by_id(patient_id)
                        questionnaire = (
                            await questionnaires.get_active_by_id(
                                questionnaire_id,
                            )
                        )
                        if patient is None or questionnaire is None:
                            raise AssignmentNotAvailableError(
                                "Patient or questionnaire is unavailable",
                            )

                        expires_at = self._calculate_expiration()
                        assignment = TestAssignment(
                            patient_id=patient.id,
                            questionnaire_id=questionnaire.id,
                            access_code=code,
                            created_by_admin_max_user_id=str(
                                admin_max_user_id,
                            ),
                            expires_at=expires_at,
                        )
                        await AssignmentRepository(session).add(assignment)
                    return assignment, patient, questionnaire
            except IntegrityError as exc:
                if not is_constraint_violation(exc, self.CODE_CONSTRAINT):
                    raise

        raise AssignmentCodeGenerationError(
            "Could not generate a unique assignment code",
        )

    def _calculate_expiration(self) -> datetime | None:
        hours = self.settings.assignment_expiration_hours
        if hours is None:
            return None
        return datetime.now(timezone.utc) + timedelta(hours=hours)
