# Maxinator

Бот для мессенджера MAX, который позволяет администратору создавать
пациентов, назначать психологические опросники и просматривать сохранённые
результаты. Пациент проходит назначение по одноразовому коду. Состояние
диалога, порядок вопросов, ответы и результаты хранятся в PostgreSQL.

Проект использует Python, `maxapi 1.2.1`, асинхронный SQLAlchemy 2,
PostgreSQL, Alembic и `pydantic-settings`.

> Результаты опросника не являются медицинским диагнозом. Первый seed
> создаёт опросник неактивным, потому что исходный документ не содержит
> направлений `direct/reverse`. До подтверждения методики назначать его
> нельзя: тематические результаты и предупреждения нельзя считать
> достоверными.

## Структура

```text
src/maxinator_bot/
  app/
    bot/
      handlers/       # тонкие обработчики MAX
      keyboards/      # inline-клавиатуры
      states/         # состояния диалога
      formatters/     # тексты сообщений
    config/           # Settings
    database/
      models/         # SQLAlchemy-модели
      repositories/   # запросы к PostgreSQL
      migrations/     # Alembic
      base.py
      session.py
    domain/
      enums/
      models/         # DTO
      constants.py
    seed/             # данные и идемпотентный seed опросника
    services/         # бизнес-логика
    main.py
  main.py             # entry point
tests/
```

Встроенный `MemoryContext` библиотеки `maxapi` не используется как
источник критичного состояния. `BotSession`, активная попытка, выбранные
сущности, порядок вопросов и ответы находятся в PostgreSQL.

## Установка

Рекомендуется стабильный Python 3.11–3.13.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Установка только зависимостей:

```bash
pip install -r request.txt
```

## Конфигурация

```bash
cp .env.example .env
```

Пример:

```dotenv
MAX_BOT_TOKEN=
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/max_questionnaire
ADMIN_MAX_IDS=123456789,987654321

PATIENT_CODE_LENGTH=6
ASSIGNMENT_CODE_LENGTH=8
ASSIGNMENT_EXPIRATION_HOURS=168
```

`ADMIN_MAX_IDS` — MAX User ID администраторов через запятую. В приложении
идентификаторы хранятся как строки. Проверка администратора выполняется
перед каждым административным callback и сообщением.

Не добавляйте реальный токен или production-пароль в репозиторий.

## PostgreSQL

Для локальной разработки:

```bash
docker compose up -d postgres
docker compose ps
```

Остановка:

```bash
docker compose down
```

Пароль `postgres` из `docker-compose.yml` предназначен только для локальной
разработки.

## Схема базы данных

Все временные метки хранятся как `TIMESTAMP WITH TIME ZONE`. Первичные ключи
предметных сущностей - UUID; MAX User ID остаются строками.

```text
questionnaires 1---* categories 1---* questions 1---* lie_question_answer_scores
                    |                \
                    |                 `---* attempt_questions *---1 test_attempts
                    `---* category_interpretation_ranges              |
                                                                  1---* attempt_category_results
                                                                  1---1 attempt_lie_results
                                                                  1---* attempt_alerts

patients 1---* test_assignments 1---1 test_attempts
                |
                `---1 questionnaires

bot_sessions -> patients / questionnaires / test_attempts
```

| Таблица | Ключевые поля | Ограничения и назначение |
| --- | --- | --- |
| `patients` | `id`, `public_code`, `max_user_id`, `display_name`, `admin_comment`, `is_archived` | Уникальный индекс `public_code`; CHECK: ровно шесть цифр. Хранит пациента и привязку к MAX-пользователю. |
| `questionnaires` | `id`, `code`, `title`, `description`, `version`, `is_active` | Уникальный индекс `code`; `version > 0`. Опросник может быть выключен без удаления истории. |
| `categories` | `id`, `questionnaire_id`, `code`, `name`, `position` | Уникальны пары `questionnaire_id + code` и `questionnaire_id + position`; удаляются каскадно вместе с опросником. |
| `questions` | `id`, `questionnaire_id`, `category_id`, `text`, `position`, `weight`, `scoring_direction`, `is_lie_question` | Уникальна позиция в опроснике; `weight >= 0`; ловушка обязана иметь `weight=0` и `scoring_direction=none`. |
| `category_interpretation_ranges` | `category_id`, `min_score`, `max_score`, `level_code`, `title`, `requires_attention` | Уникальный диапазон на категорию; `min_score <= max_score`. Диапазоны задают интерпретацию без `if/elif` в сервисе. |
| `lie_question_answer_scores` | `question_id`, `answer_value`, `points` | Уникальна пара вопрос-ответ; `answer_value` от 1 до 5, `points >= 0`. Правила пока не заполняются seed-ом. |
| `test_assignments` | `id`, `patient_id`, `questionnaire_id`, `access_code`, `status`, `expires_at` | Уникальный индекс `access_code`; CHECK: восемь цифр. Сохраняет каждое выданное назначение и его жизненный цикл. |
| `test_attempts` | `id`, `assignment_id`, `patient_id`, `questionnaire_id`, `questionnaire_version`, `status` | `assignment_id` уникален: на одно назначение возможна одна попытка. Хранит снимок версии и текущую позицию. |
| `attempt_questions` | `attempt_id`, `question_id`, `order_index`, `selected_value`, `calculated_category_score` | Уникальны `attempt_id + question_id` и `attempt_id + order_index`; ответ - только число 1-5. Это сохранённый порядок и ответы конкретной попытки. |
| `attempt_category_results` | `attempt_id`, `category_id`, `raw_score`, `level_title`, `interpretation` | Уникальна пара попытка-категория. Исторический тематический результат не перезаписывается новой попыткой. |
| `attempt_lie_results` | `attempt_id`, `score`, `level_code`, `scoring_configured` | Одна запись на попытку. Если методика ловушек не задана, `scoring_configured=false`, а балл и интерпретация равны `NULL`. |
| `attempt_alerts` | `attempt_id`, `category_id`, `alert_type`, `notified_at`, `acknowledged_at` | Уникальна комбинация попытка-категория-тип. Предотвращает повторную отправку уведомления администраторам. |
| `bot_sessions` | `max_user_id`, `state`, `selected_patient_id`, `selected_questionnaire_id`, `active_attempt_id`, `page`, `context` | Первичный ключ - MAX User ID. Это персистентное состояние UI, а не источник ответов или порядка вопросов. |

Статусы `test_assignments`: `created`, `in_progress`, `completed`,
`cancelled`, `expired`. Статусы `test_attempts`: `in_progress`,
`completed`, `cancelled`. Направления вопроса: `direct`, `reverse`, `none`;
для неподтверждённой методики обычного вопроса допускается `NULL` до её
настройки.

## Alembic

Создание следующей миграции:

```bash
alembic revision --autogenerate -m "initial schema"
```

Применение:

```bash
alembic upgrade head
```

Откат на один шаг:

```bash
alembic downgrade -1
```

Первая миграция уже находится в
`src/maxinator_bot/app/database/migrations/versions`.

## Seed

Идемпотентная загрузка 9 категорий, 90 вопросов и 27 диапазонов:

```bash
maxinator-seed
```

Повторный запуск обновляет данные по стабильному коду опросника, коду
категории и позиции вопроса, не создавая дубликаты. Правила шкалы лжи
намеренно остаются пустыми.

Опросник создаётся с `is_active=false`. После подтверждения направлений,
весов и правил ловушек их нужно внести в
`src/maxinator_bot/app/seed/questionnaire_data.py`, повторно запустить seed,
проверить расчёты, установить `QUESTIONNAIRE_IS_ACTIVE=True` и повторно
запустить seed.

## Запуск

```bash
alembic upgrade head
maxinator-seed
maxinator
```

Точка входа создаёт `Bot`, `Dispatcher`, контейнер сервисов и запускает
long polling через фактический API `maxapi 1.2.1`.

## Тесты

```bash
pytest
```

Интеграционные тесты запускают PostgreSQL 17 через Testcontainers. Нужен
работающий Docker. Можно передать существующую тестовую БД:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/maxinator_test pytest
```

SQLite для интеграционных тестов не используется.

## Сценарий администратора

1. `/start` открывает меню: «Новый пациент», «Назначить тестирование»,
   «Результаты».
2. «Новый пациент» создаёт запись и шестизначный цифровой код.
3. При назначении показываются последние 10 активных пациентов,
   пагинация и ручной ввод кода.
4. После пациента администратор явно выбирает активный опросник.
5. Создаётся назначение с отдельным восьмизначным цифровым кодом и сроком
   действия.
6. В «Результатах» доступны последние завершённые попытки, поиск по коду
   пациента и полный сохранённый результат.

Обычный пользователь не видит административные кнопки. Ручной вызов
административного callback также отклоняется.

## Сценарий пациента

1. Пользователь нажимает «Пройти тестирование».
2. Бот просит восьмизначный код назначения.
3. При первом успешном вводе пациент привязывается к текущему MAX User ID.
4. Код, уже привязанный к другому пользователю, отклоняется нейтральным
   сообщением без раскрытия данных.
5. Для попытки один раз создаётся случайный порядок вопросов.
6. Каждый ответ от 1 до 5 сохраняется сразу.
7. После перезапуска продолжается первый неотвеченный вопрос.
8. Последний ответ одной транзакцией сохраняет результаты и закрывает
   попытку и назначение.

## Идентификаторы и коды

- UUID — внутренний идентификатор всех основных сущностей.
- Код пациента — ровно 6 ASCII-цифр, нужен администратору.
- Код тестирования — ровно 8 ASCII-цифр, нужен пациенту.
- Коды генерируются через `secrets.randbelow`.
- Уникальность кодов гарантируют уникальные индексы PostgreSQL.
- При коллизии транзакция откатывается, и генерация ограниченно
  повторяется.

Код пациента и код тестирования имеют разный смысл и никогда не заменяют
UUID.

## Результаты и уведомления

Один `TestAssignment` имеет не более одной `TestAttempt`. Повторное
прохождение требует нового назначения. Новая попытка пациента не
перезаписывает старую.

Для настроенных категорий сохраняются балл, возможный диапазон, уровень и
интерпретация. Диапазоны загружаются из seed, а не находятся в `if/elif`
сервиса. Для диапазона `requires_attention=true` создаётся уникальный
`AttemptAlert`; уведомление администраторам отмечается `notified_at` только
после отправки.

Пациенту автоматическая категоричная интерпретация суицидального риска не
показывается.

## Нерешённые вопросы методики

1. Правило определения `direct/reverse` требует подтверждения. Документ не
   задаёт направления ни для одного из 72 обычных вопросов.
2. Веса 72 обычных вопросов требуют подтверждения. В seed временно
   используется техническое значение `weight=1`; позиции перечислены в
   `UNCONFIRMED_WEIGHT_QUESTION_POSITIONS`.
3. Формула начисления баллов по вопросам-ловушкам отсутствует в документе.
   TODO: Необходимо подтвердить правило начисления баллов по
   вопросам-ловушкам.
4. До подтверждения ловушки сохраняются, не входят в тематические суммы и
   не дают выдуманный балл шкалы лжи. `AttemptLieResult` получает
   `scoring_configured=false`.
5. Диапазоны `8–16`, `17–24`, `25–40` предполагают восемь оцениваемых
   вопросов с весом 1. После подтверждения иных весов диапазоны также
   необходимо пересмотреть.
6. Требуется методическое подтверждение, что умеренный и высокий диапазоны
   категории суицидального риска должны иметь `requires_attention=true`.
