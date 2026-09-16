"""Тесты FastAPI: GET /skills, поиск, reload."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app

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


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """TestClient с временным каталогом скилов."""
    _make_skill(tmp_path, "meeting-to-protocol", "Встречи → протокол")
    _make_skill(tmp_path, "summarize", "Суммаризация текста")

    app = create_app(skills_root=tmp_path)
    with TestClient(app) as c:
        yield c


# ------------------------------------------------------------------ happy


def test_list_skills_returns_all(client: TestClient) -> None:
    response = client.get("/skills")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

    names = {item["name"] for item in data}
    assert names == {"meeting-to-protocol", "summarize"}


def test_skill_response_has_expected_fields(client: TestClient) -> None:
    response = client.get("/skills")
    item = response.json()[0]

    assert set(item.keys()) == {"name", "caption", "description", "has_files"}
    assert item["name"]
    assert item["caption"]
    assert item["description"]
    assert isinstance(item["has_files"], bool)


def test_path_not_exposed(client: TestClient) -> None:
    """Path не должен утекать в JSON."""
    response = client.get("/skills")
    for item in response.json():
        assert "path" not in item


# ------------------------------------------------------------------ search


def test_search_by_name(client: TestClient) -> None:
    response = client.get("/skills?q=meeting")

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert names == ["meeting-to-protocol"]


def test_search_by_caption_case_insensitive(client: TestClient) -> None:
    response = client.get("/skills?q=ПРОТОКОЛ")

    names = [item["name"] for item in response.json()]
    assert names == ["meeting-to-protocol"]


def test_search_no_match_returns_empty(client: TestClient) -> None:
    response = client.get("/skills?q=zzz")

    assert response.status_code == 200
    assert response.json() == []


# ------------------------------------------------------------------ reload


def test_reload_endpoint(client: TestClient) -> None:
    response = client.post("/skills/reload")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["count"] == 2


def test_reload_picks_up_new_skill(client: TestClient, tmp_path: Path) -> None:
    _make_skill(tmp_path, "new-skill", "Новый скил")

    response = client.post("/skills/reload")
    assert response.json()["count"] == 3

    names = {item["name"] for item in client.get("/skills").json()}
    assert names == {"meeting-to-protocol", "summarize", "new-skill"}


# ------------------------------------------------------------------ edge


def test_empty_registry(tmp_path: Path) -> None:
    """Пустой каталог — 200 и []."""
    app = create_app(skills_root=tmp_path)
    with TestClient(app) as client:
        response = client.get("/skills")
        assert response.status_code == 200
        assert response.json() == []


def test_broken_skill_skipped(tmp_path: Path) -> None:
    """Битый скил не попадает в ответ, валидный остаётся."""
    _make_skill(tmp_path, "good-one", "Хороший скил")

    bad = tmp_path / "bad-one"
    bad.mkdir()
    (bad / "SKILL.md").write_text("нет frontmatter", encoding="utf-8")

    app = create_app(skills_root=tmp_path)
    with TestClient(app) as client:
        response = client.get("/skills")
        names = {item["name"] for item in response.json()}
        assert names == {"good-one"}