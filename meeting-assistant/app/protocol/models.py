"""Pydantic-модели протокола. Контракт между парсером и конвертером."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.protocol.constants import PLACEHOLDER


class Task(BaseModel):
    """Одна задача из секции «Задачи»."""

    text: str = Field(..., min_length=1, description="Формулировка задачи")
    assignee: str = Field(default=PLACEHOLDER, description="Ответственный или плейсхолдер")
    due_date: str = Field(default=PLACEHOLDER, description="Срок YYYY-MM-DD или плейсхолдер")

    @field_validator("assignee", "due_date")
    @classmethod
    def _empty_to_placeholder(cls, v: str) -> str:
        return v.strip() or PLACEHOLDER
    

class Protocol(BaseModel):
    """Протокол встречи целиком."""

    title: str = Field(default=PLACEHOLDER, description="Тема без префикса H1")
    date: str = Field(default=PLACEHOLDER, description="YYYY-MM-DD или плейсхолдер")
    participants: list[str] = Field(default_factory=list, description="Список участников")
    discussion: list[str] = Field(default_factory=list, description="Пункты обсуждения")
    decisions: list[str] = Field(default_factory=list, description="Принятые решения")
    tasks: list[Task] = Field(default_factory=list, description="Задачи")

    @field_validator("title", "date")
    @classmethod
    def _empty_to_placeholder(cls, v: str) -> str:
        return v.strip() or PLACEHOLDER