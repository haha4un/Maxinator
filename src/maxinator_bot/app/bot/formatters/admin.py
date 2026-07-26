from maxinator_bot.app.database.models import (
    Patient,
    Questionnaire,
    TestAssignment,
)
from maxinator_bot.app.domain.models import Page


def format_patient_created(patient: Patient) -> str:
    return (
        "Пациент создан.\n\n"
        f"Код пациента: {patient.public_code}"
    )


def format_patient_selection(patients: Page[Patient]) -> str:
    if patients.total == 0:
        return "Активных пациентов пока нет."
    return (
        "Выберите пациента.\n\n"
        f"Страница {patients.page + 1} из {patients.page_count}"
    )


def format_assignment_created(
    assignment: TestAssignment,
    patient: Patient,
    questionnaire: Questionnaire,
) -> str:
    return (
        "Тестирование назначено.\n\n"
        f"Пациент: {patient.public_code}\n"
        f"Опросник: {questionnaire.title}\n"
        f"Код тестирования: {assignment.access_code}"
    )
