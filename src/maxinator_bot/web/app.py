from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import DBAPIError, OperationalError

from maxinator_bot.app.config import get_settings
from maxinator_bot.app.database import Database
from maxinator_bot.app.services.questionnaire_editor_service import (
    QuestionnaireCodeConflictError,
    QuestionnaireEditorService,
    QuestionnaireLockedError,
    QuestionnaireNotFoundError,
)
from maxinator_bot.web.schemas import (
    QuestionnairePayload,
    QuestionnaireSummary,
)


STATIC_DIR = Path(__file__).with_name("static")


def create_app(database: Database | None = None) -> FastAPI:
    owns_database = database is None
    database = database or Database(get_settings())
    editor = QuestionnaireEditorService(database.session_factory)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        if owns_database:
            await database.dispose()

    app = FastAPI(
        title="Maxinator Questionnaire Editor",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.exception_handler(OperationalError)
    @app.exception_handler(DBAPIError)
    async def database_error_handler(_request, _exc) -> Response:
        return Response(
            content=(
                '{"detail":"База данных недоступна. Запустите PostgreSQL '
                'и примените миграции."}'
            ),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json",
        )

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/questionnaires", response_model=list[QuestionnaireSummary])
    async def list_questionnaires() -> list[QuestionnaireSummary]:
        return await editor.list_questionnaires()

    @app.get(
        "/api/questionnaires/{questionnaire_id}",
        response_model=QuestionnairePayload,
    )
    async def get_questionnaire(
        questionnaire_id: UUID,
    ) -> QuestionnairePayload:
        try:
            return await editor.get_questionnaire(questionnaire_id)
        except QuestionnaireNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Опросник не найден") from exc

    @app.post(
        "/api/questionnaires",
        status_code=status.HTTP_201_CREATED,
    )
    async def create_questionnaire(
        payload: QuestionnairePayload,
    ) -> dict[str, UUID]:
        try:
            questionnaire_id = await editor.create_questionnaire(payload)
            return {"id": questionnaire_id}
        except QuestionnaireCodeConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail="Опросник с таким кодом уже существует",
            ) from exc

    @app.put(
        "/api/questionnaires/{questionnaire_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def update_questionnaire(
        questionnaire_id: UUID,
        payload: QuestionnairePayload,
    ) -> Response:
        try:
            await editor.update_questionnaire(questionnaire_id, payload)
        except QuestionnaireNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Опросник не найден") from exc
        except QuestionnaireLockedError as exc:
            raise HTTPException(
                status_code=409,
                detail=(
                    "По опроснику уже есть назначения. "
                    "Создайте новую версию через «Клонировать»."
                ),
            ) from exc
        except QuestionnaireCodeConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail="Опросник с таким кодом уже существует",
            ) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post(
        "/api/questionnaires/{questionnaire_id}/clone",
        status_code=status.HTTP_201_CREATED,
    )
    async def clone_questionnaire(
        questionnaire_id: UUID,
    ) -> dict[str, UUID]:
        try:
            clone_id = await editor.clone_questionnaire(questionnaire_id)
            return {"id": clone_id}
        except QuestionnaireNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Опросник не найден") from exc
        except QuestionnaireCodeConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail="Не удалось подобрать код новой версии",
            ) from exc

    @app.delete(
        "/api/questionnaires/{questionnaire_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def delete_questionnaire(questionnaire_id: UUID) -> Response:
        try:
            await editor.delete_questionnaire(questionnaire_id)
        except QuestionnaireNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Опросник не найден") from exc
        except QuestionnaireLockedError as exc:
            raise HTTPException(
                status_code=409,
                detail="Нельзя удалить опросник, по которому есть назначения",
            ) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return app


app = create_app()
