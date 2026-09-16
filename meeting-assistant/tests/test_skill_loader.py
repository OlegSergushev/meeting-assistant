"""Тесты загрузчика скилов: валидные и негативные кейсы."""
from __future__ import annotations

from pathlib import Path

from app.skills.loader import load_skill, load_skills

VALID_SKILL_MD = """\
---
name: my-skill
description: Описание скила для теста.
caption: Мой скил
---

# Тело скила

Что-то полезное.
"""


_MISSING = object()

def _write_skill(
    root: Path,
    folder: str,
    content=_MISSING,
    *,
    name: str | None = None,
) -> Path:
    d = root / folder
    d.mkdir(parents=True)

    if content is _MISSING:
        # не передан вообще → дефолт VALID_SKILL_MD
        content = VALID_SKILL_MD

    if content is None:
        # явно None → не писать файл
        return d

    if name is not None:
        content = f"""\
---
name: {name}
description: Описание скила {name}.
caption: {name}
---
тело скила {name}
"""

    (d / "SKILL.md").write_text(content, encoding="utf-8")
    return d


# ------------------------------------------------------------------ happy


def test_valid_skill_is_loaded(tmp_path: Path) -> None:
    d = _write_skill(tmp_path, "my-skill")
    meta = load_skill(d)

    assert meta is not None
    assert meta.name == "my-skill"
    assert meta.caption == "Мой скил"
    assert meta.description == "Описание скила для теста."
    assert meta.has_files is False
    assert meta.path == d


def test_name_falls_back_to_folder(tmp_path: Path) -> None:
    content = """\
---
description: Без name.
---
тело
"""
    d = _write_skill(tmp_path, "from-folder", content)
    meta = load_skill(d)

    assert meta is not None
    assert meta.name == "from-folder"
    assert meta.caption == "from-folder"  # caption тоже дефолтится в name


def test_has_files_true_when_references_exists(tmp_path: Path) -> None:
    d = _write_skill(tmp_path, "with-refs")
    (d / "references").mkdir()

    meta = load_skill(d)
    assert meta is not None
    assert meta.has_files is True


def test_has_files_true_when_routes_exists(tmp_path: Path) -> None:
    d = _write_skill(tmp_path, "with-routes")
    (d / "routes").mkdir()

    meta = load_skill(d)
    assert meta is not None
    assert meta.has_files is True


# ------------------------------------------------------------------ negative


def test_skill_without_skill_md_is_skipped(tmp_path: Path) -> None:
    d = _write_skill(tmp_path, "no-file", content=None)
    assert load_skill(d) is None


def test_invalid_name_uppercase_is_skipped(tmp_path: Path) -> None:
    content = """\
---
name: MySkill
description: Валидное описание.
---
тело
"""
    d = _write_skill(tmp_path, "MySkill-folder", content)
    assert load_skill(d) is None


def test_invalid_name_with_underscore_is_skipped(tmp_path: Path) -> None:
    content = """\
---
name: my_skill
description: Валидное описание.
---
тело
"""
    d = _write_skill(tmp_path, "folder", content)
    assert load_skill(d) is None


def test_name_too_long_is_skipped(tmp_path: Path) -> None:
    long_name = "a" * 65
    content = f"""\
---
name: {long_name}
description: Валидное описание.
---
тело
"""
    d = _write_skill(tmp_path, "folder", content)
    assert load_skill(d) is None


def test_empty_body_is_skipped(tmp_path: Path) -> None:
    content = """\
---
name: ok-name
description: Валидное описание.
---
"""
    d = _write_skill(tmp_path, "ok-name", content)
    assert load_skill(d) is None


def test_description_too_long_is_skipped(tmp_path: Path) -> None:
    long_desc = "x" * 1025
    content = f"""\
---
name: ok-name
description: {long_desc}
---
тело
"""
    d = _write_skill(tmp_path, "ok-name", content)
    assert load_skill(d) is None


def test_missing_description_is_skipped(tmp_path: Path) -> None:
    content = """\
---
name: ok-name
---
тело
"""
    d = _write_skill(tmp_path, "ok-name", content)
    assert load_skill(d) is None


def test_broken_yaml_is_skipped(tmp_path: Path) -> None:
    content = """\
---
name: ok-name
description: [unclosed
---
тело
"""
    d = _write_skill(tmp_path, "ok-name", content)
    assert load_skill(d) is None


def test_no_frontmatter_is_skipped(tmp_path: Path) -> None:
    content = "# Просто markdown без frontmatter\n"
    d = _write_skill(tmp_path, "ok-name", content)
    assert load_skill(d) is None


# ------------------------------------------------------------------ batch


def test_load_skills_skips_broken_and_keeps_valid(tmp_path: Path) -> None:
    _write_skill(tmp_path, "good-one", name="good-one")
    _write_skill(tmp_path, "good-two", name="good-two")

    bad = tmp_path / "bad-one"
    bad.mkdir()
    (bad / "SKILL.md").write_text("невалидный без frontmatter", encoding="utf-8")

    result = load_skills(tmp_path)
    names = {s.name for s in result}
    assert names == {"good-one", "good-two"}


def test_load_skills_returns_empty_for_missing_root(tmp_path: Path) -> None:
    assert load_skills(tmp_path / "nope") == []