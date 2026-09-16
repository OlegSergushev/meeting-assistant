"""Тесты реестра скилов: поиск, reload, потокобезопасность."""
from __future__ import annotations

import threading
from pathlib import Path
import time

from app.skills.registry import SkillRegistry

SKILL_TMPL = """\
---
name: {name}
description: Описание скила {name}.
caption: {caption}
---
тело скила {name}
"""


def _make_skill(root: Path, name: str, caption: str) -> None:
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        SKILL_TMPL.format(name=name, caption=caption),
        encoding="utf-8",
    )


def test_reload_loads_skills(tmp_path: Path) -> None:
    _make_skill(tmp_path, "alpha", "Альфа")
    _make_skill(tmp_path, "beta", "Бета")

    reg = SkillRegistry(tmp_path)
    reg.reload()

    assert len(reg) == 2
    assert {s.name for s in reg.list()} == {"alpha", "beta"}


def test_search_by_name(tmp_path: Path) -> None:
    _make_skill(tmp_path, "alpha", "Альфа")
    _make_skill(tmp_path, "beta", "Бета")

    reg = SkillRegistry(tmp_path)
    reg.reload()

    assert [s.name for s in reg.list(q="alp")] == ["alpha"]


def test_search_by_caption_case_insensitive(tmp_path: Path) -> None:
    _make_skill(tmp_path, "alpha", "Альфа")
    _make_skill(tmp_path, "beta", "Бета")

    reg = SkillRegistry(tmp_path)
    reg.reload()

    assert [s.name for s in reg.list(q="альфа")] == ["alpha"]
    assert [s.name for s in reg.list(q="АЛЬФА")] == ["alpha"]


def test_search_no_match_returns_empty(tmp_path: Path) -> None:
    _make_skill(tmp_path, "alpha", "Альфа")
    reg = SkillRegistry(tmp_path)
    reg.reload()

    assert reg.list(q="zzz") == []


def test_get_by_name(tmp_path: Path) -> None:
    _make_skill(tmp_path, "alpha", "Альфа")
    reg = SkillRegistry(tmp_path)
    reg.reload()

    assert reg.get("alpha") is not None
    assert reg.get("missing") is None


def test_reload_replaces_snapshot(tmp_path: Path) -> None:
    _make_skill(tmp_path, "alpha", "Альфа")
    reg = SkillRegistry(tmp_path)
    reg.reload()
    assert len(reg) == 1

    _make_skill(tmp_path, "beta", "Бета")
    reg.reload()
    assert len(reg) == 2


def test_reload_removes_deleted_skills(tmp_path: Path) -> None:
    _make_skill(tmp_path, "alpha", "Альфа")
    _make_skill(tmp_path, "beta", "Бета")

    reg = SkillRegistry(tmp_path)
    reg.reload()
    assert len(reg) == 2

    # удаляем beta
    (tmp_path / "beta" / "SKILL.md").unlink()

    reg.reload()
    assert {s.name for s in reg.list()} == {"alpha"}


def test_reads_during_reload_are_safe(tmp_path: Path) -> None:
    """Читатели не должны падать, пока идёт reload."""
    for i in range(20):
        _make_skill(tmp_path, f"skill-{i:02d}", f"Скил {i}")

    reg = SkillRegistry(tmp_path)
    reg.reload()

    stop = threading.Event()
    errors: list[Exception] = []

    def reader() -> None:
        while not stop.is_set():
            try:
                for s in reg.list():
                    if stop.is_set():
                        return
                    _ = s.name, s.caption, s.description
                time.sleep(0)  # отдаём GIL
            except Exception as e:
                errors.append(e)

    threads = [threading.Thread(target=reader) for _ in range(4)]
    for t in threads:
        t.start()

    for _ in range(10):
        reg.reload()

    stop.set()
    for t in threads:
        t.join(timeout=5)  # ← защита от вечного ожидания

    assert not errors, f"читатели упали: {errors[:3]}"