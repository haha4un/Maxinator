from maxinator_bot.app.domain.models import AttemptResultView


def format_attempt_result(result: AttemptResultView) -> str:
    lines = [
        f"Пациент: {result.patient_code}",
        f"Опросник: {result.questionnaire_title}",
        (
            "Назначено: "
            f"{result.assigned_at.astimezone():%d.%m.%Y %H:%M}"
        ),
        (
            "Начато: "
            f"{result.started_at.astimezone():%d.%m.%Y %H:%M}"
        ),
        (
            "Завершено: "
            f"{result.completed_at.astimezone():%d.%m.%Y %H:%M}"
        ),
        "",
    ]

    if result.categories:
        lines.append("Результаты категорий:")
        for category in result.categories:
            attention = (
                " [ТРЕБУЕТ ВНИМАНИЯ]"
                if category.requires_attention
                else ""
            )
            lines.extend(
                [
                    "",
                    f"{category.category_name}{attention}",
                    f"Балл: {category.raw_score:g}",
                    f"Уровень: {category.level_title}",
                    category.interpretation,
                ],
            )
    else:
        lines.extend(
            [
                "Тематические результаты: правило direct/reverse "
                "не настроено.",
            ],
        )

    lines.append("")
    if result.lie_result.scoring_configured:
        lines.extend(
            [
                "Шкала достоверности:",
                f"Балл: {result.lie_result.score}",
                result.lie_result.interpretation or "",
            ],
        )
    else:
        lines.append(
            "Шкала достоверности: правило расчёта не настроено",
        )
    lines.extend(
        [
            "",
            "Результат не является медицинским диагнозом.",
        ],
    )
    return "\n".join(lines)
