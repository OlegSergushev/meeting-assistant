"""
Сборка .docx из Protocol.

Не знает про markdown. Работает только с Pydantic-моделью.
Плейсхолдеры ('Не указано') выделяются курсивом и серым цветом.
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.document import Document as DocumentType
from docx.shared import Pt

from app.docx.styles import (
    FONT_NAME,
    FONT_SIZE,
    H1_SIZE,
    H2_SIZE,
    LIST_LEFT_INDENT,
    PARAGRAPH_SPACE_AFTER,
    PLACEHOLDER_COLOR,
    PLACEHOLDER_ITALIC,
    TABLE_HEADER_BOLD,
    TABLE_STYLE,
)
from app.protocol.constants import (
    DATE_LABEL,
    H1_PREFIX,
    PARTICIPANTS_LABEL,
    PLACEHOLDER,
    SECTION_DECISIONS,
    SECTION_DISCUSSION,
    SECTION_TASKS,
    TASK_TABLE_HEADER,
)
from app.protocol.models import Protocol, Task


def build_docx(protocol: Protocol) -> DocumentType:
    """Protocol → Document. Файл ещё не сохранён."""
    doc = Document()
    _apply_base_font(doc)

    _add_title(doc, protocol)
    _add_meta(doc, protocol)
    _add_bullets_section(doc, SECTION_DISCUSSION, protocol.discussion)
    _add_bullets_section(doc, SECTION_DECISIONS, protocol.decisions)
    _add_tasks_section(doc, protocol.tasks)

    return doc


def save_docx(protocol: Protocol, path: Path) -> None:
    """Protocol → .docx на диск. Создаёт родительские папки."""
    doc = build_docx(protocol)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))


# ---------------------------------------------------------------- internal


def _apply_base_font(doc: DocumentType) -> None:
    """Единый шрифт для всего документа через стиль Normal."""
    style = doc.styles["Normal"]
    style.font.name = FONT_NAME
    style.font.size = FONT_SIZE


def _add_text_with_placeholders(paragraph, text: str) -> None:
    """
    Добавляет текст в параграф, разбивая его по вхождениям PLACEHOLDER.
    Плейсхолдеры выделяются курсивом и серым.
    """
    if PLACEHOLDER not in text:
        paragraph.add_run(text)
        return

    parts = text.split(PLACEHOLDER)
    for i, part in enumerate(parts):
        if part:
            paragraph.add_run(part)
        # между частями — сам плейсхолдер
        if i < len(parts) - 1:
            run = paragraph.add_run(PLACEHOLDER)
            run.italic = PLACEHOLDER_ITALIC
            run.font.color.rgb = PLACEHOLDER_COLOR


def _add_title(doc: DocumentType, protocol: Protocol) -> None:
    heading = doc.add_heading(level=1)
    heading.text = ""
    # H1 = "# Протокол встречи: <тема>"
    heading.add_run(H1_PREFIX.lstrip("# ").strip())  # "Протокол встречи:"
    heading.add_run(" ")
    _add_run_with_placeholder(heading, protocol.title)
    _set_heading_size(heading, H1_SIZE)


def _add_run_with_placeholder(paragraph, text: str) -> None:
    """Хелпер: добавить один run с учётом плейсхолдера."""
    if text == PLACEHOLDER:
        run = paragraph.add_run(PLACEHOLDER)
        run.italic = PLACEHOLDER_ITALIC
        run.font.color.rgb = PLACEHOLDER_COLOR
    else:
        paragraph.add_run(text)


def _add_meta(doc: DocumentType, protocol: Protocol) -> None:
    # Дата
    p_date = doc.add_paragraph()
    label = p_date.add_run(DATE_LABEL.strip("* "))  # "Дата:"
    label.bold = True
    p_date.add_run(" ")
    _add_run_with_placeholder(p_date, protocol.date)

    # Участники
    p_part = doc.add_paragraph()
    label = p_part.add_run(PARTICIPANTS_LABEL.strip("* "))  # "Участники:"
    label.bold = True
    p_part.add_run(" ")
    if protocol.participants:
        p_part.add_run(", ".join(protocol.participants))
    else:
        run = p_part.add_run(PLACEHOLDER)
        run.italic = PLACEHOLDER_ITALIC
        run.font.color.rgb = PLACEHOLDER_COLOR


def _add_bullets_section(doc: DocumentType, title: str, bullets: list[str]) -> None:
    heading = doc.add_heading(title.lstrip("# ").strip(), level=2)
    _set_heading_size(heading, H2_SIZE)

    if not bullets:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.left_indent = LIST_LEFT_INDENT
        _add_run_with_placeholder(p, PLACEHOLDER)
        return

    for bullet in bullets:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.left_indent = LIST_LEFT_INDENT
        _add_text_with_placeholders(p, bullet)


def _add_tasks_section(doc: DocumentType, tasks: list[Task]) -> None:
    heading = doc.add_heading(SECTION_TASKS.lstrip("# ").strip(), level=2)
    _set_heading_size(heading, H2_SIZE)

    # Таблица: шапка + строки (или одна строка-плейсхолдер)
    data_rows = tasks if tasks else [None]
    table = doc.add_table(rows=len(data_rows) + 1, cols=3)
    table.style = TABLE_STYLE

    # Шапка
    header_cells = table.rows[0].cells
    for cell, text in zip(header_cells, _header_labels()):
        cell.text = ""
        p = cell.paragraphs[0]
        run = p.add_run(text)
        run.bold = TABLE_HEADER_BOLD

    # Данные
    if not tasks:
        cells = table.rows[1].cells
        for cell in cells:
            cell.text = ""
            _add_run_with_placeholder(cell.paragraphs[0], PLACEHOLDER)
        return

    for row, task in zip(table.rows[1:], tasks):
        _fill_task_row(row, task)


def _header_labels() -> list[str]:
    """'| Задача | Ответственный | Срок |' → ['Задача', 'Ответственный', 'Срок']."""
    return [c.strip() for c in TASK_TABLE_HEADER.strip("|").split("|")]


def _fill_task_row(row, task: Task) -> None:
    values = [task.text, task.assignee, task.due_date]
    for cell, value in zip(row.cells, values):
        cell.text = ""
        _add_run_with_placeholder(cell.paragraphs[0], value)


def _set_heading_size(heading, size_pt: Pt) -> None:
    for run in heading.runs:
        run.font.size = size_pt