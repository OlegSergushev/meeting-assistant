"""
Загрузка и валидация скилов из каталога.

Правила валидации (из ТЗ):
- SKILL.md существует и читается;
- YAML frontmatter парсится;
- name (или имя папки) — kebab-case, ≤64 символов;
- description — 1..1024 символов;
- тело SKILL.md (после frontmatter) непустое.

Битый скил → warning + пропуск, не ломая загрузку остальных.
"""
from __future__ import annotations

import os
import logging
import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.skills.schemas import SkillFrontmatter, SkillMeta

logger = logging.getLogger(__name__)

SKILL_FILENAME = "SKILL.md"
SUB_DIRS = ("references", "routes")

# kebab-case: строчные буквы, цифры, дефисы; не начинается/не кончается дефисом
_KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

MAX_NAME_LEN = 64
MAX_DESCRIPTION_LEN = 1024


def _split_frontmatter(raw: str) -> tuple[str, str]:
    """
    Делит SKILL.md на (yaml_part, body).

    Ожидается формат:
        ---
        <yaml>
        ---
        <body>

    Raises:
        ValueError: если формат не соблюдён.
    """
    lines = raw.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md должен начинаться с '---' (YAML frontmatter)")

    end_idx: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        raise ValueError("YAML frontmatter не закрыт ('---' в конце не найден)")

    yaml_part = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1:]).strip()
    return yaml_part, body


def _validate_name(name: str, source: str) -> str:
    """
    Проверяет kebab-case и длину. source — откуда взято имя (для warning-а).
    Raises: ValueError.
    """
    if not name:
        raise ValueError(f"Имя скила пустое ({source})")
    if len(name) > MAX_NAME_LEN:
        raise ValueError(
            f"Имя скила длиннее {MAX_NAME_LEN} символов ({source}): {name!r}"
        )
    if not _KEBAB_RE.match(name):
        raise ValueError(
            f"Имя скила не в kebab-case ({source}): {name!r}"
        )
    return name


def _has_extra_files(skill_dir: Path) -> bool:
    """True, если рядом с SKILL.md есть references/ или routes/."""
    return any(os.path.isdir(skill_dir / sub) for sub in SUB_DIRS)


def load_skill(skill_dir: Path) -> SkillMeta | None:
    """
    Загружает один скил. None — если скил невалиден (warning уже записан).

    Не кидает исключений наружу: любая проблема → None.
    """
    skill_md = skill_dir / SKILL_FILENAME
    if not skill_md.is_file():
        logger.warning("Скил %s пропущен: нет %s", skill_dir, SKILL_FILENAME)
        return None

    try:
        raw = skill_md.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("Скил %s пропущен: не читается %s (%s)", skill_dir, SKILL_FILENAME, e)
        return None

    # frontmatter
    try:
        yaml_part, body = _split_frontmatter(raw)
    except ValueError as e:
        logger.warning("Скил %s пропущен: %s", skill_dir, e)
        return None

    if not body:
        logger.warning("Скил %s пропущен: тело SKILL.md пустое", skill_dir)
        return None

    try:
        fm_data = yaml.safe_load(yaml_part) or {}
    except yaml.YAMLError as e:
        logger.warning("Скил %s пропущен: битый YAML (%s)", skill_dir, e)
        return None

    if not isinstance(fm_data, dict):
        logger.warning("Скил %s пропущен: frontmatter не словарь", skill_dir)
        return None

    # Pydantic-валидация frontmatter
    try:
        fm = SkillFrontmatter(**fm_data)
    except ValidationError as e:
        logger.warning("Скил %s пропущен: невалидный frontmatter: %s", skill_dir, e)
        return None

    # имя: из frontmatter или из папки
    name_source = "frontmatter" if fm.name else "имя папки"
    candidate_name = fm.name or skill_dir.name
    try:
        name = _validate_name(candidate_name, name_source)
    except ValueError as e:
        logger.warning("Скил %s пропущен: %s", skill_dir, e)
        return None

    caption = fm.caption or name

    return SkillMeta(
        name=name,
        caption=caption,
        description=fm.description,
        has_files=_has_extra_files(skill_dir),
        path=skill_dir,
    )


def load_skills(root: Path) -> list[SkillMeta]:
    """
    Обходит root, грузит все подкаталоги со SKILL.md.
    Битые — warning + пропуск. Порядок — по имени папки.
    """
    if not root.is_dir():
        logger.warning("Каталог скилов не найден: %s", root)
        return []

    result: list[SkillMeta] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        meta = load_skill(entry)
        if meta is not None:
            result.append(meta)

    logger.info("Загружено скилов: %d из %s", len(result), root)
    return result

