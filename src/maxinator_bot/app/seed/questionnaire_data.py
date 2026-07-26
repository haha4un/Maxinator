from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from maxinator_bot.app.domain.enums import ScoringDirection


QUESTIONNAIRE_CODE = "psychological_profile_v1"
QUESTIONNAIRE_TITLE = "Психологический опросник"
QUESTIONNAIRE_VERSION = 1
QUESTIONNAIRE_IS_ACTIVE = False


@dataclass(frozen=True, slots=True)
class QuestionSeed:
    text: str
    is_lie_question: bool = False
    weight: Decimal = Decimal("1")
    scoring_direction: ScoringDirection | None = None


@dataclass(frozen=True, slots=True)
class InterpretationSeed:
    min_score: Decimal
    max_score: Decimal
    level_code: str
    title: str
    description: str
    requires_attention: bool = False


@dataclass(frozen=True, slots=True)
class CategorySeed:
    code: str
    name: str
    questions: tuple[QuestionSeed, ...]
    interpretations: tuple[InterpretationSeed, ...]


def regular(text: str) -> QuestionSeed:
    # The source document does not specify direct/reverse directions.
    return QuestionSeed(text=text)


def lie(text: str) -> QuestionSeed:
    return QuestionSeed(
        text=text,
        is_lie_question=True,
        weight=Decimal("0"),
        scoring_direction=ScoringDirection.NONE,
    )


def interpretation(
    min_score: int,
    max_score: int,
    level_code: str,
    title: str,
    *details: str,
    requires_attention: bool = False,
) -> InterpretationSeed:
    return InterpretationSeed(
        min_score=Decimal(min_score),
        max_score=Decimal(max_score),
        level_code=level_code,
        title=title,
        description="\n".join(details),
        requires_attention=requires_attention,
    )


CATEGORIES: tuple[CategorySeed, ...] = (
    CategorySeed(
        code="family",
        name="Схема оценки семьи",
        questions=(
            regular(
                "Члены вашей семьи часто поддерживают друг друга "
                "в трудных ситуациях.",
            ),
            regular("Вы доверяете своим родителям."),
            regular(
                "Ваша семья сплоченная и всегда готова помочь друг другу.",
            ),
            regular(
                "В вашей семье принято проводить время за совместной "
                "деятельностью.",
            ),
            regular(
                "Находясь в кругу семьи, вы чувствуете себя спокойно.",
            ),
            lie("Ваша семья никогда не отказывает в помощи."),
            lie("В вашей семье все идеально и нет проблем."),
            regular(
                "В семье принято обсуждать важные решения вместе.",
            ),
            regular(
                "Родители уважают ваше личное пространство и границы.",
            ),
            regular(
                "В семье существует традиция совместных праздников "
                "и традиций.",
            ),
        ),
        interpretations=(
            interpretation(
                8,
                16,
                "low",
                "Кризисное состояние семейных отношений",
                "Недостаточная эмоциональная поддержка",
                "Проблемы в коммуникации",
                "Риск социальной изоляции",
            ),
            interpretation(
                17,
                24,
                "medium",
                "Нормализация семейных отношений",
                "Умеренная поддержка",
                "Частичные проблемы коммуникации",
                "Стабильная семейная структура",
            ),
            interpretation(
                25,
                40,
                "high",
                "Здоровая семейная система",
                "Высокая эмоциональная поддержка",
                "Эффективная коммуникация",
                "Стабильные семейные связи",
            ),
        ),
    ),
    CategorySeed(
        code="conflict_behavior",
        name="Поведение в конфликтной ситуации",
        questions=(
            regular(
                "Вас обычно так сильно задевает ссора с человеком, "
                "что вам трудно сдержать себя.",
            ),
            regular("При ссорах вы стараетесь доказать свою правоту."),
            regular("Вас никто не понимает в конфликтах."),
            regular("Вы избегаете встреч с теми, с кем конфликтуете."),
            regular("Вы не умеете решать конфликты спокойно."),
            lie("Вы всегда правы в конфликтах."),
            lie(
                "Конфликты никогда не вызывают у вас негативных эмоций.",
            ),
            regular(
                "После конфликта вы стараетесь проанализировать "
                "свое поведение.",
            ),
            regular(
                "Вы готовы извиняться, если понимаете свою неправоту.",
            ),
            regular(
                "В конфликте вы стараетесь найти компромиссное решение.",
            ),
        ),
        interpretations=(
            interpretation(
                8,
                16,
                "low",
                "Деструктивный тип реагирования",
                "Избегание конфликтов",
                "Неумение идти на компромисс",
                "Агрессивная реакция",
            ),
            interpretation(
                17,
                24,
                "medium",
                "Смешанный тип реагирования",
                "Периодические трудности в разрешении конфликтов",
                "Частичная готовность к компромиссам",
                "Умеренная конфликтность",
            ),
            interpretation(
                25,
                40,
                "high",
                "Конструктивный тип реагирования",
                "Умение находить решения",
                "Готовность к компромиссам",
                "Зрелая позиция в конфликтах",
            ),
        ),
    ),
    CategorySeed(
        code="social_adaptation",
        name="Социально-психологическая адаптация",
        questions=(
            regular("Вы быстро привыкаете к новому коллективу."),
            regular(
                "Не испытываете трудностей при общении с новыми людьми.",
            ),
            regular("Легко меняете окружение, если оно не устраивает."),
            regular("Без трудностей знакомитесь с новыми людьми."),
            regular("Легко адаптируетесь к изменениям."),
            lie("У вас нет абсолютно никаких проблем в общении."),
            lie("Вы идеально вписываетесь в любой коллектив."),
            regular(
                "Вы умеете находить общий язык с людьми разных возрастов.",
            ),
            regular("Вам комфортно выступать перед аудиторией."),
            regular("Вы легко осваиваете новые социальные роли."),
        ),
        interpretations=(
            interpretation(
                8,
                16,
                "low",
                "Дезадаптация",
                "Трудности в социализации",
                "Проблемы с новыми контактами",
                "Страх изменений",
            ),
            interpretation(
                17,
                24,
                "medium",
                "Частичная адаптация",
                "Умеренная социальная активность",
                "Периодические трудности",
                "Нормальная адаптивность",
            ),
            interpretation(
                25,
                40,
                "high",
                "Высокая адаптация",
                "Успешная социализация",
                "Хорошие коммуникативные навыки",
                "Гибкость в изменениях",
            ),
        ),
    ),
    CategorySeed(
        code="perfectionism",
        name="Перфекционизм",
        questions=(
            regular("Вы должны быть лучшим во всем."),
            regular("Критикуете себя за ошибки."),
            regular("Стремитесь к идеальному результату."),
            regular("Боитесь неудач."),
            regular("Считаете несовершенный результат неприемлемым."),
            lie("Вы никогда не делаете ошибок."),
            lie("Все, что вы делаете, всегда идеально."),
            regular(
                "Вы часто откладываете дела из-за страха сделать "
                "их неидеально.",
            ),
            regular("Вам сложно делегировать задачи другим людям."),
            regular(
                "Вы постоянно сравниваете свои результаты с чужими.",
            ),
        ),
        interpretations=(
            interpretation(
                8,
                16,
                "low",
                "Здоровые стандарты",
                "Реалистичные ожидания",
                "Адекватная самооценка",
                "Гибкие критерии успеха",
            ),
            interpretation(
                17,
                24,
                "medium",
                "Умеренный перфекционизм",
                "Повышенные требования",
                "Критичность к себе",
                "Стремление к совершенству",
            ),
            interpretation(
                25,
                40,
                "high",
                "Патологический перфекционизм",
                "Чрезмерные требования",
                "Самообвинение",
                "Страх неудачи",
            ),
        ),
    ),
    CategorySeed(
        code="hopelessness",
        name="Безнадежность",
        questions=(
            regular("Считаете, что будущее будет только хуже."),
            regular("Проблемы кажутся неразрешимыми."),
            regular("Ничего не может изменить ситуацию к лучшему."),
            regular("Чувствуете себя обреченным."),
            regular("Нет сил что-либо изменить."),
            lie("У вас всегда все получается."),
            lie("Ваша жизнь идеальна и не требует изменений."),
            regular("Вы не видите смысла в своих действиях."),
            regular("Вам кажется, что все ваши усилия бесполезны."),
            regular("Вы не верите в лучшее будущее."),
        ),
        interpretations=(
            interpretation(
                8,
                16,
                "low",
                "Оптимистичная позиция",
                "Вера в будущее",
                "Позитивный настрой",
                "Уверенность в силах",
            ),
            interpretation(
                17,
                24,
                "medium",
                "Умеренная безнадежность",
                "Периодический пессимизм",
                "Сомнения в успехе",
                "Снижение активности",
            ),
            interpretation(
                25,
                40,
                "high",
                "Глубокая безнадежность",
                "Устойчивый пессимизм",
                "Отсутствие веры в успех",
                "Пассивность",
            ),
        ),
    ),
    CategorySeed(
        code="achievement_motivation",
        name="Мотивация достижения",
        questions=(
            regular("Ставите конкретные цели."),
            regular(
                "Готовы прилагать усилия для достижения целей.",
            ),
            regular("Хорошо реагируете на неудачи."),
            regular("Стремитесь к саморазвитию."),
            regular("Считаете успех важным."),
            lie("Вы достигаете абсолютно всех поставленных целей."),
            lie("Вам не нужно прикладывать усилий для успеха."),
            regular("Вы регулярно планируете свои действия."),
            regular(
                "Вы находите мотивацию даже в сложных ситуациях.",
            ),
            regular(
                "Вы умеете разбивать большие цели на маленькие задачи.",
            ),
        ),
        interpretations=(
            interpretation(
                8,
                16,
                "low",
                "Низкая мотивация",
                "Отсутствие целей",
                "Пассивность",
                "Отсутствие стремлений",
            ),
            interpretation(
                17,
                24,
                "medium",
                "Средняя мотивация",
                "Наличие целей",
                "Периодическая активность",
                "Умеренные стремления",
            ),
            interpretation(
                25,
                40,
                "high",
                "Высокая мотивация",
                "Четкие цели",
                "Высокая активность",
                "Стремление к успеху",
            ),
        ),
    ),
    CategorySeed(
        code="anxiety",
        name="Тревога",
        questions=(
            regular("Часто испытываете беспокойство."),
            regular("Испытываете тревогу без причины."),
            regular("Беспокоитесь о будущем."),
            regular("Имеете физические симптомы тревоги."),
            regular("Тревога мешает повседневной жизни."),
            lie("Вы никогда не тревожитесь."),
            lie("Вас ничего не беспокоит."),
            regular("Вы постоянно проверяете, все ли сделано правильно."),
            regular("Вам сложно расслабиться."),
            regular("Вы часто переживаете о возможных неприятностях."),
        ),
        interpretations=(
            interpretation(
                8,
                16,
                "low",
                "Нормальная тревожность",
                "Адекватная реакция",
                "Контроль над состоянием",
                "Функциональная тревога",
            ),
            interpretation(
                17,
                24,
                "medium",
                "Умеренная тревожность",
                "Повышенный уровень",
                "Периодические беспокойства",
                "Частичный контроль",
            ),
            interpretation(
                25,
                40,
                "high",
                "Высокая тревожность",
                "Постоянный уровень",
                "Нарушение функционирования",
                "Тревожные расстройства",
            ),
        ),
    ),
    CategorySeed(
        code="depression",
        name="Депрессия",
        questions=(
            regular("Испытываете постоянную грусть."),
            regular("Теряете интерес к любимым занятиям."),
            regular("Чувствуете упадок сил."),
            regular("Имеете проблемы со сном."),
            regular("Испытываете чувство вины."),
            lie("Вы всегда счастливы."),
            lie("У вас всегда отличное настроение."),
            regular("Вам сложно получать удовольствие от жизни."),
            regular("Вы часто чувствуете себя опустошенным."),
            regular("Вам трудно концентрироваться на делах."),
        ),
        interpretations=(
            interpretation(
                8,
                16,
                "low",
                "Отсутствие депрессивных признаков",
                "Нормальное настроение",
                "Адекватная самооценка",
                "Энергичность",
            ),
            interpretation(
                17,
                24,
                "medium",
                "Легкая депрессия",
                "Снижение настроения",
                "Умеренная утомляемость",
                "Частичная потеря интереса",
            ),
            interpretation(
                25,
                40,
                "high",
                "Выраженная депрессия",
                "Стойкое снижение настроения",
                "Значительная утомляемость",
                "Потеря интереса к жизни",
            ),
        ),
    ),
    CategorySeed(
        code="suicidal_risk",
        name="Суицидальный риск",
        questions=(
            regular("Появляются мысли о самоповреждении."),
            regular("Думаете, что жизнь не имеет смысла."),
            regular(
                "Считаете, что окружающим будет лучше без вас.",
            ),
            regular("Есть план причинить себе вред."),
            regular(
                "Чувствуете неспособность справиться с проблемами.",
            ),
            lie("Вы никогда не испытываете трудностей."),
            lie("Ваша жизнь абсолютно прекрасна."),
            regular("Вы часто думаете о смерти."),
            regular("Чувствуете себя обузой для других."),
            regular("Считаете, что ваши проблемы неразрешимы."),
        ),
        interpretations=(
            interpretation(
                8,
                16,
                "low",
                "Низкий уровень риска",
                "Отсутствие устойчивых суицидальных мыслей",
                "Позитивное отношение к жизни",
                "Способность справляться с проблемами",
                "Отсутствие планов самоповреждения",
                "Понимание ценности собственной жизни",
            ),
            interpretation(
                17,
                24,
                "medium",
                "Умеренный уровень риска",
                "Периодические мысли о самоповреждении",
                "Ощущение бессмысленности жизни в кризисные периоды",
                "Чувство тяжести проблем",
                "Возможное наличие пассивных суицидальных мыслей",
                "Необходимость психологической поддержки",
                requires_attention=True,
            ),
            interpretation(
                25,
                40,
                "high",
                "Высокий уровень риска",
                "Устойчивые суицидальные мысли",
                "Разработка планов самоповреждения",
                "Убежденность в бессмысленности существования",
                "Чувство беспомощности и безнадежности",
                "Восприятие себя как обузы для окружающих",
                requires_attention=True,
            ),
        ),
    ),
)


LIE_QUESTION_POSITIONS = tuple(
    category_index * 10 + local_position
    for category_index in range(9)
    for local_position in (6, 7)
)
UNCONFIRMED_WEIGHT_QUESTION_POSITIONS = tuple(
    position
    for position in range(1, 91)
    if position not in LIE_QUESTION_POSITIONS
)
UNCONFIRMED_SCORING_DIRECTION_QUESTION_POSITIONS = (
    UNCONFIRMED_WEIGHT_QUESTION_POSITIONS
)

# Add LieQuestionAnswerScore values here only after the method is confirmed.
LIE_QUESTION_ANSWER_SCORES: dict[int, dict[int, int]] = {}


def validate_questionnaire_data() -> None:
    if len(CATEGORIES) != 9:
        raise ValueError("The questionnaire must contain 9 categories")
    if any(len(category.questions) != 10 for category in CATEGORIES):
        raise ValueError("Each category must contain 10 questions")
    if any(
        sum(question.is_lie_question for question in category.questions) != 2
        for category in CATEGORIES
    ):
        raise ValueError("Each category must contain 2 lie questions")
    if sum(len(category.questions) for category in CATEGORIES) != 90:
        raise ValueError("The questionnaire must contain 90 questions")
    for question_position, scores in LIE_QUESTION_ANSWER_SCORES.items():
        if question_position not in LIE_QUESTION_POSITIONS:
            raise ValueError(
                f"Question {question_position} is not a lie question",
            )
        if set(scores) != {1, 2, 3, 4, 5}:
            raise ValueError(
                "Each configured lie question must define answers 1-5",
            )
        if any(
            isinstance(points, bool)
            or not isinstance(points, int)
            or points < 0
            for points in scores.values()
        ):
            raise ValueError("Lie score points must be non-negative integers")
