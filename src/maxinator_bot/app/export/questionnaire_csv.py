from __future__ import annotations

import asyncio
import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from maxinator_bot.app.config import get_settings
from maxinator_bot.app.database import Database
from maxinator_bot.app.database.models import (
    Category,
    CategoryInterpretationRange,
    LieQuestionAnswerScore,
    Question,
    Questionnaire,
)


EXPORTS: tuple[tuple[str, type[Any], tuple[str, ...]], ...] = (
    (
        "questionnaires.csv",
        Questionnaire,
        (
            "id",
            "code",
            "title",
            "description",
            "version",
            "is_active",
            "created_at",
        ),
    ),
    (
        "categories.csv",
        Category,
        (
            "id",
            "questionnaire_id",
            "code",
            "name",
            "description",
            "position",
        ),
    ),
    (
        "questions.csv",
        Question,
        (
            "id",
            "questionnaire_id",
            "category_id",
            "text",
            "position",
            "weight",
            "scoring_direction",
            "is_lie_question",
            "is_active",
        ),
    ),
    (
        "interpretation_ranges.csv",
        CategoryInterpretationRange,
        (
            "id",
            "category_id",
            "min_score",
            "max_score",
            "level_code",
            "title",
            "description",
            "requires_attention",
        ),
    ),
    (
        "lie_answer_scores.csv",
        LieQuestionAnswerScore,
        (
            "id",
            "question_id",
            "answer_value",
            "points",
        ),
    ),
)


def csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    return value


async def export_questionnaires(output_dir: Path | None = None) -> Path:
    output_dir = output_dir or Path("exports") / "questionnaires"
    output_dir.mkdir(parents=True, exist_ok=True)

    database = Database(get_settings())
    try:
        async with database.session_factory() as session:
            for filename, model, fields in EXPORTS:
                rows = list((await session.scalars(select(model))).all())
                path = output_dir / filename
                with path.open("w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(
                        {
                            field: csv_value(getattr(row, field))
                            for field in fields
                        }
                        for row in rows
                    )
                print(f"{filename}: {len(rows)} rows")
    finally:
        await database.dispose()

    return output_dir.resolve()


def main() -> None:
    output_dir = asyncio.run(export_questionnaires())
    print(f"CSV export: {output_dir}")


if __name__ == "__main__":
    main()
