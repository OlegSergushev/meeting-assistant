"""
Единый источник правды о формате протокола.

"""
from __future__ import annotations

# Единый плейсхолдер для отсутствующих данных
PLACEHOLDER = "Не указано"

# Формат даты
DATE_FORMAT = "%Y-%m-%d"

# Заголовок H1
H1_PREFIX = "# Протокол встречи: "

# Метки метаданных
DATE_LABEL = "**Дата:** "
PARTICIPANTS_LABEL = "**Участники:** "

# Заголовки секций H2
SECTION_DISCUSSION = "## Обсуждение"
SECTION_DECISIONS = "## Решения"
SECTION_TASKS = "## Задачи"

SECTIONS_ORDER = (SECTION_DISCUSSION, SECTION_DECISIONS, SECTION_TASKS)

# Маркер маркированного списка
BULLET_PREFIX = "- "

# Таблица задач
TASK_TABLE_HEADER = "| Задача | Ответственный | Срок |"
TASK_TABLE_SEPARATOR = "|---|---|---|"
TASK_TABLE_COLUMNS = 3