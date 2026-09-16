"""
Thread-safe реестр скилов.

Чтение — lock-free (immutable snapshot).
Reload — под lock, атомарная замена ссылки.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from app.skills.loader import load_skills
from app.skills.schemas import SkillMeta

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    Реестр скилов с поддержкой hot reload.

    Гарантии:
    - list()/get() читают immutable-снапшот, не блокируются;
    - reload() создаёт новый dict и подменяет ссылку атомарно;
    - параллельные reload() сериализуются через lock.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._skills: dict[str, SkillMeta] = {}
        self._reload_lock = threading.Lock()

    def reload(self) -> None:
        """Перечитывает каталог и атомарно подменяет снапшот."""
        with self._reload_lock:
            skills_list = load_skills(self._root)
            new_snapshot = {s.name: s for s in skills_list}
            # атомарная подмена ссылки — читатели увидят либо старый, либо новый
            self._skills = new_snapshot
            logger.info("Реестр перезагружен: %d скилов", len(new_snapshot))

    def list(self, q: str | None = None) -> list[SkillMeta]:
        """
        Список скилов. Если q задан — фильтр по подстроке в name или caption
        (case-insensitive). Порядок — по name.
        """
        snapshot = self._skills
        items = list(snapshot.values())

        if q:
            needle = q.lower()
            items = [
                s for s in items
                if needle in s.name.lower() or needle in s.caption.lower()
            ]

        return sorted(items, key=lambda s: s.name)

    def get(self, name: str) -> SkillMeta | None:
        """Скил по имени. None, если нет."""
        return self._skills.get(name)

    def __len__(self) -> int:
        return len(self._skills)