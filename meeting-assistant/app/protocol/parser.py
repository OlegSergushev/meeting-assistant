"""
Парсер markdown-протокола → Protocol.

Толерантен к мелочам (пробелы, пустые строки), строг к структуре
(наличие H1, три секции, pipe-таблица задач). Всё, что можно
починить плейсхолдером — чинится с warning. Всё, что нельзя — ParseError.
"""
from __future__ import annotations

import logging
import re

from app.protocol.constants import (
    BULLET_PREFIX,
    DATE_LABEL,
    H1_PREFIX,
    PARTICIPANTS_LABEL,
    PLACEHOLDER,
    SECTION_DECISIONS,
    SECTION_DISCUSSION,
    SECTION_TASKS,
    SECTIONS_ORDER,
    TASK_TABLE_COLUMNS,
    TASK_TABLE_HEADER,
    TASK_TABLE_SEPARATOR,
)
from app.protocol.models import Protocol, Task

logger = logging.getLogger(__name__)


class ParseError(ValueError):
    """Фатальная ошибка парсинга: структура сломана так, что чинить нечем."""

def _normalize(markdown: str) -> str:
    """Приводит переносы строк к \\n, обрезает trailing whitespace и снимает код-обёртку."""
    text = markdown.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]

    # Срезаем обёртку ```markdown ... ``` или ``` ... ```
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    return "\n".join(lines)


def _strip_placeholder(value: str) -> str:
    """Если значение — плейсхолдер, возвращает его. Иначе — очищенную строку."""
    v = value.strip()
    if not v or v == PLACEHOLDER:
        return PLACEHOLDER
    return v


def _parse_participants(raw: str) -> list[str]:
    """'Петя, Маша, Сергей' → ['Петя', 'Маша', 'Сергей']. Плейсхолдер → []."""
    raw = raw.strip()
    if not raw or raw == PLACEHOLDER:
        return []
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


def _parse_title(lines: list[str]) -> tuple[str, int]:
    """
    Ищет H1. Возвращает (тема, индекс следующей строки после H1).
    Нет H1 → ParseError.
    """
    for i, line in enumerate(lines):
        if line.startswith(H1_PREFIX):
            title = line[len(H1_PREFIX):].strip()
            return _strip_placeholder(title), i + 1
        if line.startswith("# "):
            raise ParseError(
                f"Заголовок H1 не соответствует формату. "
                f"Ожидалось '{H1_PREFIX}<тема>', получено: {line!r}"
            )
    raise ParseError("В протоколе нет заголовка H1")


def _parse_meta(lines: list[str], start: int) -> tuple[str, list[str], int]:
    """
    Читает '**Дата:** ...' и '**Участники:** ...' начиная с start.
    Возвращает (date, participants, индекс следующей строки).
    Отсутствие строки — warning + плейсхолдер.
    """
    date = PLACEHOLDER
    participants: list[str] = []

    i = start
    while i < len(lines) and not lines[i].startswith("## "):
        line = lines[i]
        if line.startswith(DATE_LABEL):
            date = _strip_placeholder(line[len(DATE_LABEL):])
        elif line.startswith(PARTICIPANTS_LABEL):
            participants = _parse_participants(line[len(PARTICIPANTS_LABEL):])
        elif line.strip():
            logger.warning("Неизвестная строка между H1 и секциями: %r", line)
        i += 1

    if date == PLACEHOLDER:
        logger.warning("В протоколе нет строки '**Дата:**' — ставлю плейсхолдер")
    if not participants:
        logger.warning("В протоколе нет участников — ставлю плейсхолдер")

    return date, participants, i


def _split_sections(lines: list[str], start: int) -> dict[str, list[str]]:
    """
    Возвращает {'## Обсуждение': [...], '## Решения': [...], '## Задачи': [...]}.
    Секции, которых нет, — warning, пустой список.
    """
    sections: dict[str, list[str]] = {title: [] for title in SECTIONS_ORDER}
    current: str | None = None

    for line in lines[start:]:
        if line.startswith("## "):
            if line in sections:
                current = line
            else:
                logger.warning("Неизвестная секция H2: %r — игнорирую", line)
                current = None
            continue
        if current is not None:
            sections[current].append(line)

    for title in SECTIONS_ORDER:
        if not sections[title]:
            logger.warning("Секция %r пустая или отсутствует", title)

    return sections


def _parse_bullets(lines: list[str], section_name: str) -> list[str]:
    """'- пункт' → ['пункт']. Строка-плейсхолдер '-'+PLACEHOLDER → [] + warning."""
    bullets: list[str] = []
    has_placeholder = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith(BULLET_PREFIX):
            logger.warning("Строка в секции %r не является пунктом: %r", section_name, line)
            continue
        text = stripped[len(BULLET_PREFIX):].strip()
        if not text or text == PLACEHOLDER:
            has_placeholder = True
            continue
        bullets.append(text)
    if has_placeholder and not bullets:
        logger.warning("Секция %r содержит только плейсхолдер", section_name)
    return bullets


_PIPE_ROW = re.compile(r"^\|(.+)\|$")


def _split_pipe_row(line: str) -> list[str] | None:
    """
    '| Задача | Петя | 2024-01-01 |' → ['Задача', 'Петя', '2024-01-01'].
    Не pipe-строка или неверное число колонок → None.
    """
    m = _PIPE_ROW.match(line.strip())
    if not m:
        return None
    cells = [c.strip() for c in m.group(1).split("|")]
    if len(cells) != TASK_TABLE_COLUMNS:
        return None
    return cells


def _is_separator_row(cells: list[str]) -> bool:
    """'|---|---|---|' → ['---', '---', '---']."""
    return all(set(c) <= {"-", ":", " "} and c for c in cells)


def _is_header_row(cells: list[str]) -> bool:
    """Проверяет, что ячейки — это шапка таблицы задач (без учёта пробелов)."""
    expected = [c.strip() for c in TASK_TABLE_HEADER.strip("|").split("|")]
    return cells == expected


def _parse_tasks(lines: list[str]) -> list[Task]:
    """
    Парсит секцию «Задачи»: пропускает пустые строки, шапку и разделитель,
    остальные pipe-строки → Task. Битые строки → warning + строка-плейсхолдер.
    """
    tasks: list[Task] = []
    seen_header = False
    seen_separator = False
    has_placeholder = False

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("```"):
            continue

        cells = _split_pipe_row(stripped)
        if cells is None:
            logger.warning("Битая строка в таблице задач: %r — заменяю плейсхолдером", line)
            tasks.append(Task(text=PLACEHOLDER, assignee=PLACEHOLDER, due_date=PLACEHOLDER))
            continue

        # Шапка
        if not seen_header and _is_header_row(cells):
            seen_header = True
            continue

        # Разделитель
        if not seen_separator and _is_separator_row(cells):
            seen_separator = True
            continue

        text = _strip_placeholder(cells[0])
        assignee = _strip_placeholder(cells[1])
        due_date = _strip_placeholder(cells[2])

        # Строка-плейсхолдер целиком → не добавляем задачу
        if text == PLACEHOLDER and assignee == PLACEHOLDER and due_date == PLACEHOLDER:
            has_placeholder= True
            continue

        tasks.append(Task(text=text, assignee=assignee, due_date=due_date))

    if not seen_header:
        logger.warning("В секции %r нет шапки таблицы", SECTION_TASKS)
    if not seen_separator:
        logger.warning("В секции %r нет разделителя таблицы", SECTION_TASKS)
    if has_placeholder and (not tasks):
        logger.warning("Секция %r содержит только плейсхолдер", SECTION_TASKS)

    return tasks


def parse_protocol(markdown: str) -> Protocol:
    """
    Парсит markdown-протокол в Protocol.

    Raises:
        ParseError: если нет H1 или структура сломана фатально.
    """
    if not markdown or not markdown.strip():
        raise ParseError("Пустой вход")

    lines = _normalize(markdown).split("\n")

    title, after_title = _parse_title(lines)
    date, participants, after_meta = _parse_meta(lines, after_title)
    sections = _split_sections(lines, after_meta)

    discussion = _parse_bullets(sections[SECTION_DISCUSSION], SECTION_DISCUSSION)
    decisions = _parse_bullets(sections[SECTION_DECISIONS], SECTION_DECISIONS)
    tasks = _parse_tasks(sections[SECTION_TASKS])

    return Protocol(
        title=title,
        date=date,
        participants=participants,
        discussion=discussion,
        decisions=decisions,
        tasks=tasks,
    )
