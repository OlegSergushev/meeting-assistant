"""
FastAPI-зависимости.

get_registry достаёт реестр скилов из app.state,
куда его положил lifespan в main.py.
"""
from __future__ import annotations

from fastapi import Request

from app.skills.registry import SkillRegistry


def get_registry(request: Request) -> SkillRegistry:
    """Возвращает реестр скилов, созданный на старте приложения."""
    return request.app.state.registry