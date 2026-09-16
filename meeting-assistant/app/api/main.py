"""
FastAPI-приложение.

create_app(skills_root) — фабрика: в тестах можно передать временный каталог.
app — готовый инстанс для uvicorn.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI

from app.api.routes import router as skills_router
from app.logging_setup import configure_logging
from app.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)

DEFAULT_SKILLS_ROOT = Path("skills")


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """На старте — грузим реестр. На стопе — ничего."""
    registry: SkillRegistry = app.state.registry
    registry.reload()
    logger.info("Реестр скилов загружен: %d", len(registry))
    yield


def create_app(skills_root: Path | None = None) -> FastAPI:
    """
    Создаёт FastAPI-приложение.

    skills_root — каталог со скилами. По умолчанию ./skills.
    """
    configure_logging()

    root = skills_root or DEFAULT_SKILLS_ROOT
    registry = SkillRegistry(root)

    app = FastAPI(
        title="meeting-assistant",
        description="LLM-ассистент: заметки встречи → протокол + реестр скилов.",
        version="0.1.0",
        lifespan=_lifespan,
    )
    app.state.registry = registry
    app.include_router(skills_router)

    @app.get("/", include_in_schema=False)
    def root_redirect() -> dict[str, str]:
        return {"status": "ok", "docs": "/docs"}

    return app


# Инстанс для uvicorn: uvicorn app.api.main:app --reload
app = create_app()