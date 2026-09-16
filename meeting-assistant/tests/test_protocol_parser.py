"""Тесты парсера markdown-протокола."""
from __future__ import annotations

import pytest

from app.protocol.constants import PLACEHOLDER
from app.protocol.parser import ParseError, parse_protocol

VALID_MD = """\
# Протокол встречи: Проект Альфа

**Дата:** 2024-09-12
**Участники:** Петя, Маша, Сергей

## Обсуждение
- Релиз переносится на октябрь.
- Обсудили бюджет.

## Решения
- Перенести релиз на октябрь.

## Задачи

| Задача | Ответственный | Срок |
|---|---|---|
| Написать тесты | Маша | 2024-09-20 |
| Подготовить документацию | Петя | Не указано |
"""


# ------------------------------------------------------------------ happy


def test_parse_valid_protocol() -> None:
    p = parse_protocol(VALID_MD)

    assert p.title == "Проект Альфа"
    assert p.date == "2024-09-12"
    assert p.participants == ["Петя", "Маша", "Сергей"]
    assert p.discussion == [
        "Релиз переносится на октябрь.",
        "Обсудили бюджет.",
    ]
    assert p.decisions == ["Перенести релиз на октябрь."]
    assert len(p.tasks) == 2
    assert p.tasks[0].text == "Написать тесты"
    assert p.tasks[0].assignee == "Маша"
    assert p.tasks[0].due_date == "2024-09-20"
    assert p.tasks[1].due_date == PLACEHOLDER


def test_crlf_normalized() -> None:
    """\\r\\n из Windows-файлов не должны ломать парсер."""
    md = VALID_MD.replace("\n", "\r\n")
    p = parse_protocol(md)
    assert p.title == "Проект Альфа"


def test_extra_whitespace_tolerated() -> None:
    """Пробелы в конце строк и вокруг ячеек не мешают."""
    md = VALID_MD.replace("| Маша |", "|  Маша  |")
    p = parse_protocol(md)
    assert p.tasks[0].assignee == "Маша"


def test_empty_discussion_and_decisions() -> None:
    md = """\
# Протокол встречи: Тема

**Дата:** 2024-01-01
**Участники:** Аня

## Обсуждение

## Решения

## Задачи

| Задача | Ответственный | Срок |
|---|---|---|
| X | Y | Z |
"""
    p = parse_protocol(md)
    assert p.discussion == []
    assert p.decisions == []


# ------------------------------------------------------------------ negative


def test_empty_input_raises() -> None:
    with pytest.raises(ParseError):
        parse_protocol("")


def test_whitespace_only_input_raises() -> None:
    with pytest.raises(ParseError):
        parse_protocol("   \n\n  \n")


def test_missing_h1_raises() -> None:
    md = "**Дата:** 2024-01-01\n**Участники:** Аня\n"
    with pytest.raises(ParseError):
        parse_protocol(md)


def test_wrong_h1_format_raises() -> None:
    """H1 есть, но не с нашим префиксом."""
    md = "# Какой-то другой заголовок\n\n## Обсуждение\n- x\n"
    with pytest.raises(ParseError):
        parse_protocol(md)


# ------------------------------------------------------------------ placeholders


def test_missing_date_becomes_placeholder() -> None:
    md = """\
# Протокол встречи: Тема

**Участники:** Аня

## Обсуждение
- x

## Решения
- y

## Задачи

| Задача | Ответственный | Срок |
|---|---|---|
| X | Y | Z |
"""
    p = parse_protocol(md)
    assert p.date == PLACEHOLDER


def test_missing_participants_becomes_empty_list() -> None:
    md = """\
# Протокол встречи: Тема

**Дата:** 2024-01-01

## Обсуждение
- x

## Решения
- y

## Задачи

| Задача | Ответственный | Срок |
|---|---|---|
| X | Y | Z |
"""
    p = parse_protocol(md)
    assert p.participants == []


def test_placeholder_bullet_is_skipped() -> None:
    """'- Не указано' не должно попасть в список пунктов."""
    md = """\
# Протокол встречи: Тема

**Дата:** 2024-01-01
**Участники:** Аня

## Обсуждение
- Не указано

## Решения
- y

## Задачи

| Задача | Ответственный | Срок |
|---|---|---|
| X | Y | Z |
"""
    p = parse_protocol(md)
    assert p.discussion == []


# ------------------------------------------------------------------ tasks table


def test_broken_table_row_becomes_placeholder_task() -> None:
    """Строка с 2 колонками вместо 3 → warning + задача-плейсхолдер."""
    md = """\
# Протокол встречи: Тема

**Дата:** 2024-01-01
**Участники:** Аня

## Обсуждение
- x

## Решения
- y

## Задачи

| Задача | Ответственный | Срок |
|---|---|---|
| Хорошая задача | Петя | 2024-01-02 |
| Битая строка | без_срока |
"""
    p = parse_protocol(md)
    # хорошая задача + плейсхолдер-задача на битой строке
    assert len(p.tasks) == 2
    assert p.tasks[0].text == "Хорошая задача"
    assert p.tasks[1].text == PLACEHOLDER
    assert p.tasks[1].assignee == PLACEHOLDER
    assert p.tasks[1].due_date == PLACEHOLDER


def test_placeholder_row_is_skipped() -> None:
    """Строка '| Не указано | Не указано | Не указано |' не создаёт задачу."""
    md = """\
# Протокол встречи: Тема

**Дата:** 2024-01-01
**Участники:** Аня

## Обсуждение
- x

## Решения
- y

## Задачи

| Задача | Ответственный | Срок |
|---|---|---|
| Не указано | Не указано | Не указано |
"""
    p = parse_protocol(md)
    assert p.tasks == []


def test_empty_tasks_table_only_header() -> None:
    """Таблица с одной шапкой → пустой список задач."""
    md = """\
# Протокол встречи: Тема

**Дата:** 2024-01-01
**Участники:** Аня

## Обсуждение
- x

## Решения
- y

## Задачи

| Задача | Ответственный | Срок |
|---|---|---|
"""
    p = parse_protocol(md)
    assert p.tasks == []


def test_unknown_section_is_ignored() -> None:
    """Секция '## Риски' не должна ломать парсер и не попасть в модель."""
    md = """\
# Протокол встречи: Тема

**Дата:** 2024-01-01
**Участники:** Аня

## Обсуждение
- x

## Риски
- Что-то страшное

## Решения
- y

## Задачи

| Задача | Ответственный | Срок |
|---|---|---|
| X | Y | Z |
"""
    p = parse_protocol(md)
    assert p.discussion == ["x"]
    assert p.decisions == ["y"]
    assert len(p.tasks) == 1