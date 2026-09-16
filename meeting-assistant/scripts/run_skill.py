"""
Реальный прогон скила meeting-to-protocol через GigaChat.

Для каждого примера в examples/:
1. Читает notes.txt.
2. Шлёт в GigaChat: system = тело SKILL.md, user = заметки.
3. Получает markdown-протокол.
4. Прогоняет через parse_protocol().
5. Собирает .docx.
6. Печатает: ответ модели, распарсенный JSON, путь к .docx.

Не сравнивает с эталоном автоматически — LLM недетерминирована.
Эталон examples/<name>/protocol.md печатается рядом для сверки.

Запуск (из корня проекта):
    python -m scripts.run_skill
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from app.docx.builder import save_docx
from app.logging_setup import configure_logging
from app.protocol.parser import ParseError, parse_protocol

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = PROJECT_ROOT / "skills" / "meeting-to-protocol" / "SKILL.md"
EXAMPLES_DIR = PROJECT_ROOT / "examples"

logger = logging.getLogger(__name__)


def load_skill_body() -> str:
    """
    Читает SKILL.md, отрезает YAML frontmatter,
    затем подклеивает содержимое references/*.md и routes/*.md.

    Это даёт GigaChat полный контекст скила: и основной промпт,
    и грамматику формата, и правила для краевых случаев.
    """
    raw = SKILL_PATH.read_text(encoding="utf-8")
    lines = raw.split("\n")

    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md должен начинаться с '---'")

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        raise ValueError("YAML frontmatter не закрыт")

    body = "\n".join(lines[end_idx + 1:]).strip()
    if not body:
        raise ValueError("Тело SKILL.md пустое")

    # Подклеиваем references/ и routes/
    skill_dir = SKILL_PATH.parent
    for sub in ("references", "routes"):
        sub_dir = skill_dir / sub
        if not sub_dir.is_dir():
            continue
        for md_file in sorted(sub_dir.glob("*.md")):
            extra = md_file.read_text(encoding="utf-8").strip()
            if extra:
                body += f"\n\n---\n\n# Дополнение: {md_file.name}\n\n{extra}"

    return body


def build_client() -> GigaChat:
    load_dotenv(PROJECT_ROOT / ".env")
    creds = os.environ.get("GIGACHAT_CREDENTIALS")
    if not creds:
        raise RuntimeError("GIGACHAT_CREDENTIALS не задан в .env")

    return GigaChat(
        credentials=creds,
        scope=os.environ.get("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"),
        verify_ssl_certs=False,
        model=os.environ.get("GIGACHAT_MODEL", "GigaChat"),
    )


def ask_skill(giga: GigaChat, skill_body: str, notes: str) -> str:
    """Шлёт заметки в GigaChat со скилом как system prompt."""
    chat = Chat(messages=[
        Messages(role=MessagesRole.SYSTEM, content=skill_body),
        Messages(role=MessagesRole.USER, content=notes),
    ])
    response = giga.chat(chat)
    return response.choices[0].message.content


def run_example(giga: GigaChat, skill_body: str, example_dir: Path) -> bool:
    """Прогоняет один пример. Возвращает True, если всё ок."""
    name = example_dir.name
    notes_path = example_dir / "notes.txt"
    if not notes_path.exists():
        logger.warning("Пропуск %s: нет notes.txt", name)
        return False

    print(f"\n{'=' * 70}")
    print(f"  Пример: {name}")
    print(f"{'=' * 70}")

    notes = notes_path.read_text(encoding="utf-8")
    print("\n--- ВХОД (notes.txt) ---")
    print(notes.strip())

    print("\n→ Отправляю в GigaChat...")
    raw = ask_skill(giga, skill_body, notes)

    print("\n--- ОТВЕТ МОДЕЛИ (markdown) ---")
    print(raw)

    print("\n→ Парсю ответ...")
    try:
        protocol = parse_protocol(raw)
    except ParseError as e:
        print(f"❌ ParseError: {e}")
        print("   Модель вернула невалидный протокол. Смотри ответ выше.")
        return False

    print("\n--- РАСПАРСЕННЫЙ PROTOCOL (JSON) ---")
    print(protocol.model_dump_json(indent=2))

    out_docx = example_dir / "protocol.docx"
    save_docx(protocol, out_docx)
    print(f"\n✅ .docx сохранён: {out_docx}")

    # Показываем эталон рядом, для глазами-сверки
    expected_path = example_dir / "protocol.md"
    if expected_path.exists():
        print("\n--- ЭТАЛОН (protocol.md) — для сверки глазами ---")
        print(expected_path.read_text(encoding="utf-8"))

    return True


def main() -> int:
    configure_logging()

    print(f"Загружаю скил: {SKILL_PATH}")
    try:
        skill_body = load_skill_body()
    except (OSError, ValueError) as e:
        print(f"❌ Не удалось загрузить скил: {e}")
        return 1
    print(f"✅ Тело скила загружено: {len(skill_body)} символов")

    try:
        giga = build_client()
    except RuntimeError as e:
        print(f"❌ {e}")
        return 2

    examples = sorted(p for p in EXAMPLES_DIR.iterdir() if p.is_dir())
    if not examples:
        print(f"❌ В {EXAMPLES_DIR} нет подкаталогов с примерами")
        return 3

    results: list[tuple[str, bool]] = []
    for example in examples:
        try:
            ok = run_example(giga, skill_body, example)
        except Exception as e:
            print(f"\n❌ Пример {example.name} упал с ошибкой: {type(e).__name__}: {e}")
            ok = False
        results.append((example.name, ok))

    print(f"\n{'=' * 70}")
    print("  ИТОГО")
    print(f"{'=' * 70}")
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")

    return 0 if all(ok for _, ok in results) else 4


if __name__ == "__main__":
    sys.exit(main())