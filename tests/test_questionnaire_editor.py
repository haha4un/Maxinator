from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from maxinator_bot.app.services.questionnaire_editor_service import (
    QuestionnaireEditorService,
)
from maxinator_bot.web.schemas import QuestionnairePayload


def questionnaire_payload(*, active: bool = False) -> QuestionnairePayload:
    return QuestionnairePayload.model_validate(
        {
            "code": "stress_test",
            "title": "Стресс",
            "version": 1,
            "is_active": active,
            "categories": [
                {
                    "code": "stress",
                    "name": "Стресс",
                    "questions": [
                        {
                            "text": "Испытываете напряжение?",
                            "weight": 1.5,
                            "scoring_direction": "direct",
                        },
                        {
                            "text": "Вы всегда спокойны?",
                            "is_lie_question": True,
                            "answer_scores": {
                                "1": 0,
                                "2": 0,
                                "3": 1,
                                "4": 1,
                                "5": 2,
                            },
                        },
                    ],
                    "interpretations": [
                        {
                            "min_score": 1.5,
                            "max_score": 7.5,
                            "level_code": "normal",
                            "title": "Обычный",
                            "description": "Допустимый уровень",
                        },
                    ],
                },
            ],
        },
    )


def test_published_questionnaire_requires_ranges() -> None:
    raw = questionnaire_payload().model_dump()
    raw["is_active"] = True
    raw["categories"][0]["interpretations"] = []

    with pytest.raises(ValidationError, match="не заданы диапазоны"):
        QuestionnairePayload.model_validate(raw)


def test_lie_question_is_normalized() -> None:
    question = questionnaire_payload().categories[0].questions[1]

    assert question.weight == Decimal("0")
    assert question.scoring_direction.value == "none"


@pytest.mark.asyncio
async def test_editor_round_trip(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = QuestionnaireEditorService(session_factory)
    payload = questionnaire_payload(active=True)

    questionnaire_id = await service.create_questionnaire(payload)
    stored = await service.get_questionnaire(questionnaire_id)
    summaries = await service.list_questionnaires()

    assert stored.title == "Стресс"
    assert stored.categories[0].questions[0].weight == Decimal("1.5000")
    assert stored.categories[0].questions[1].answer_scores[5] == 2
    assert summaries[0].category_count == 1
    assert summaries[0].question_count == 2
    assert summaries[0].editable is True

    stored.title = "Обновлённый стресс"
    await service.update_questionnaire(questionnaire_id, stored)

    updated = await service.get_questionnaire(questionnaire_id)
    assert updated.title == "Обновлённый стресс"


@pytest.mark.asyncio
async def test_editor_clone_is_draft(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = QuestionnaireEditorService(session_factory)
    questionnaire_id = await service.create_questionnaire(
        questionnaire_payload(active=True),
    )

    clone_id = await service.clone_questionnaire(questionnaire_id)
    clone = await service.get_questionnaire(clone_id)

    assert clone.version == 2
    assert clone.is_active is False
    assert clone.code != "stress_test"
