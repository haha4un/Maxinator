from __future__ import annotations

from dataclasses import dataclass

from maxinator_bot.app.config import Settings
from maxinator_bot.app.database import Database
from maxinator_bot.app.services.admin_service import AdminService
from maxinator_bot.app.services.admin_notification_service import (
    AdminNotificationService,
)
from maxinator_bot.app.services.assignment_service import AssignmentService
from maxinator_bot.app.services.attempt_service import AttemptService
from maxinator_bot.app.services.bot_session_service import BotSessionService
from maxinator_bot.app.services.code_generator import CodeGenerator
from maxinator_bot.app.services.patient_service import PatientService
from maxinator_bot.app.services.result_service import ResultService
from maxinator_bot.app.services.scoring_service import ScoringService


@dataclass(slots=True)
class ServiceContainer:
    settings: Settings
    database: Database
    admin: AdminService
    notifications: AdminNotificationService
    code_generator: CodeGenerator
    patients: PatientService
    assignments: AssignmentService
    attempts: AttemptService
    results: ResultService
    bot_sessions: BotSessionService

    @classmethod
    def build(
        cls,
        settings: Settings,
        database: Database,
    ) -> ServiceContainer:
        code_generator = CodeGenerator()
        scoring_service = ScoringService()
        result_service = ResultService(
            database.session_factory,
            scoring_service,
        )
        return cls(
            settings=settings,
            database=database,
            admin=AdminService(settings),
            notifications=AdminNotificationService(
                database.session_factory,
                settings,
            ),
            code_generator=code_generator,
            patients=PatientService(
                database.session_factory,
                settings,
                code_generator,
            ),
            assignments=AssignmentService(
                database.session_factory,
                settings,
                code_generator,
            ),
            attempts=AttemptService(
                database.session_factory,
                settings,
                code_generator,
                scoring_service,
                result_service,
            ),
            results=result_service,
            bot_sessions=BotSessionService(database.session_factory),
        )
