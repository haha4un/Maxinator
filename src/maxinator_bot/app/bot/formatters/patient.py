from maxinator_bot.app.domain.models import QuestionProgress


def format_question(progress: QuestionProgress) -> str:
    return (
        f"Вопрос {progress.current_number} из {progress.total}\n\n"
        f"{progress.question_text}"
    )
