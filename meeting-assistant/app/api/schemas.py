"""Схемы ответов API."""
from __future__ import annotations

from pydantic import BaseModel


class SkillResponse(BaseModel):
    """Скил в ответе GET /skills."""

    name: str
    caption: str
    description: str
    has_files: bool

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "meeting-to-protocol",
                "caption": "Заметки встречи → протокол",
                "description": "Преобразует заметки встречи в структурированный протокол.",
                "has_files": True,
            }
        }
    }


class ReloadResponse(BaseModel):
    """Ответ POST /skills/reload."""

    status: str
    count: int