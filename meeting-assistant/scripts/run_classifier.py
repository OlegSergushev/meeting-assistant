"""
Прогон eval_queries.md через классификатор скилов на GigaChat.

Как работает:
1. Читает skills/meeting-to-protocol/eval_queries.md.
2. Парсит 10 запросов: 6 "должны триггерить", 4 "не должны".
3. Для каждого запроса:
   - system = описание скила + инструкция "выбери скил или верни none",
   - user = запрос,
   - GigaChat возвращает имя скила или none.
4. Сравниваем с ожиданием, печатаем отчёт.

Запуск (из корня проекта):
    python -m scripts.run_classifier
"""
from __future__ import annotations

import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from app.logging_setup import configure_logging
from app.skills.loader import load_skill

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = PROJECT_ROOT / "skills" / "meeting-to-protocol"
EVAL_PATH = SKILL_DIR / "eval_queries.md"

logger = logging.getLogger(__name__)


@dataclass
class EvalQuery:
    number: int
    text: str
    should_trigger: bool
    reason: str


def parse_eval_queries(path: Path) -> list[EvalQuery]:
    """
    Парсит eval_queries.md.

    Формат:
    ## Должны триггерить скил (6)
    ### 1. Краткое название
    > текст запроса

    **Почему триггерит:** ...

    ## НЕ должны триггерить скил (4)
    ### 7. ...
    """
    raw = path.read_text(encoding="utf-8")
    queries: list[EvalQuery] = []

    # Разбиваем на секции по H2
    current_should_trigger: bool | None = None
    for line in raw.split("\n"):
        if line.startswith("## Должны триггерить"):
            current_should_trigger = True
            continue
        if line.startswith("## НЕ должны триггерить"):
            current_should_trigger = False
            continue

        # H3 с номером и названием: "### 1. Прямой запрос"
        m = re.match(r"^### (\d+)\.\s+(.*)$", line)
        if m and current_should_trigger is not None:
            queries.append(
                EvalQuery(
                    number=int(m.group(1)),
                    text="",  # заполним ниже
                    should_trigger=current_should_trigger,
                    reason=m.group(2),
                )
            )
            continue

        # Строка с цитатой: "> текст запроса"
        if line.startswith("> ") and queries:
            # только если это первая цитата для этого запроса
            if not queries[-1].text:
                queries[-1].text = line[2:].strip()

    return queries


def build_classifier_system_prompt(skill_name: str, skill_description: str) -> str:
    """System prompt для классификатора скилов."""
    return f"""\
Ты — классификатор скилов LLM-ассистента.

Доступен ровно один скил:

name: {skill_name}
description: {skill_description}

Твоя задача: по запросу пользователя определить, нужно ли применить этот скил.

Правила ответа:
- Если запрос относится к скилу — верни ТОЛЬКО имя скила: {skill_name}
- Если не относится — верни ТОЛЬКО слово: none
- Никаких пояснений, только имя скила или none.
"""


def classify(giga: GigaChat, system: str, query: str) -> str:
    """Возвращает имя скила или 'none'."""
    chat = Chat(messages=[
        Messages(role=MessagesRole.SYSTEM, content=system),
        Messages(role=MessagesRole.USER, content=query),
    ])
    response = giga.chat(chat)
    raw = response.choices[0].message.content.strip().lower()

    # GigaChat может вернуть "none." или "none\n" — нормализуем
    if "none" in raw and len(raw) < 30:
        return "none"
    if SKILL_DIR.name.lower() in raw:
        return SKILL_DIR.name
    # Если вернул что-то другое — покажем как есть
    return raw


def main() -> int:
    configure_logging()

    load_dotenv(PROJECT_ROOT / ".env")
    creds = os.environ.get("GIGACHAT_CREDENTIALS")
    if not creds:
        print("❌ GIGACHAT_CREDENTIALS не задан в .env")
        return 1

    giga = GigaChat(
        credentials=creds,
        scope=os.environ.get("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"),
        verify_ssl_certs=False,
        model=os.environ.get("GIGACHAT_MODEL", "GigaChat"),
    )

    # Метаданные скила
    meta = load_skill(SKILL_DIR)
    if meta is None:
        print(f"❌ Не удалось загрузить скил {SKILL_DIR}")
        return 2

    print(f"Скил: {meta.name}")
    print(f"Описание: {meta.description}")

    queries = parse_eval_queries(EVAL_PATH)
    print(f"\nЗагружено запросов: {len(queries)}")
    for q in queries:
        expect = "trigger" if q.should_trigger else "none"
        print(f"  [{q.number}] ожидание={expect}: {q.text[:60]}...")

    system = build_classifier_system_prompt(meta.name, meta.description)

    correct = 0
    print(f"\n{'=' * 70}")
    print("  ПРОГОН")
    print(f"{'=' * 70}")

    for q in queries:
        print(f"\n[{q.number}] {q.text}")
        try:
            result = classify(giga, system, q.text)
        except Exception as e:
            print(f"  ❌ Ошибка: {type(e).__name__}: {e}")
            continue

        expected = meta.name if q.should_trigger else "none"
        ok = result == expected
        if ok:
            correct += 1

        mark = "✅" if ok else "❌"
        print(f"  {mark} ожидание={expected!r}, получено={result!r}")

    print(f"\n{'=' * 70}")
    print(f"  ИТОГО: {correct}/{len(queries)} угадано")
    print(f"{'=' * 70}")

    return 0 if correct == len(queries) else 3


if __name__ == "__main__":
    sys.exit(main())