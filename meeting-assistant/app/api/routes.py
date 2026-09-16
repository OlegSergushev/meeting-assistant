"""HTTP-роуты."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_registry
from app.api.schemas import ReloadResponse, SkillResponse
from app.skills.registry import SkillRegistry

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get(
    "",
    response_model=list[SkillResponse],
    summary="Список скилов",
    description="Возвращает все загруженные скилы. Поддерживает поиск по подстроке в name и caption.",
)
def list_skills(
    q: str | None = Query(
        default=None,
        description="Подстрока для поиска в name и caption (case-insensitive).",
    ),
    registry: SkillRegistry = Depends(get_registry),
) -> list[SkillResponse]:
    metas = registry.list(q=q)
    return [
        SkillResponse(
            name=m.name,
            caption=m.caption,
            description=m.description,
            has_files=m.has_files,
        )
        for m in metas
    ]


@router.post(
    "/reload",
    response_model=ReloadResponse,
    summary="Перезагрузить реестр",
    description="Перечитывает каталог скилов. Бонусный эндпоинт, в ТЗ не требуется.",
)
def reload_skills(
    registry: SkillRegistry = Depends(get_registry),
) -> ReloadResponse:
    registry.reload()
    return ReloadResponse(status="ok", count=len(registry))