"""
Pydantic-схемы для скилов.

SkillFrontmatter — то, что парсится из YAML между --- в SKILL.md.
SkillMeta        — то, что отдаём в API и храним в реестре.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class SkillFrontmatter(BaseModel):
    """Содержимое YAML-блока в начале SKILL.md."""

    name: str | None = Field(
        default=None,
        description="kebab-case, ≤64. Если None — берётся из имени папки.",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="Когда применять скил и что он делает.",
    )
    caption: str | None = Field(
        default=None,
        description="Публичное имя для интерфейса.",
    )


class SkillMeta(BaseModel):
    """Скил в реестре: валидный, готовый к отдаче."""

    name: str = Field(..., description="Итоговое имя (kebab-case)")
    caption: str = Field(..., description="Публичное имя")
    description: str = Field(..., description="Описание")
    has_files: bool = Field(..., description="Есть ли references/ или routes/")
    path: Path = Field(..., description="Путь к каталогу скила")