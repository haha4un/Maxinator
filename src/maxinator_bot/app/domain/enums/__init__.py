from enum import Enum


class AssignmentStatus(str, Enum):
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class AttemptStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ScoringDirection(str, Enum):
    DIRECT = "direct"
    REVERSE = "reverse"
    NONE = "none"


class BotState(str, Enum):
    IDLE = "idle"
    ADMIN_MENU = "admin_menu"
    CHOOSING_PATIENT = "choosing_patient"
    ENTERING_PATIENT_CODE = "entering_patient_code"
    CHOOSING_QUESTIONNAIRE = "choosing_questionnaire"
    ENTERING_ASSIGNMENT_CODE = "entering_assignment_code"
    TAKING_QUESTIONNAIRE = "taking_questionnaire"
    VIEWING_RESULTS = "viewing_results"


__all__ = [
    "AssignmentStatus",
    "AttemptStatus",
    "BotState",
    "ScoringDirection",
]
