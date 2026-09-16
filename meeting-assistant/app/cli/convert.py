"""
CLI: markdown-протокол → .docx.

Запуск:
    python -m app.cli.convert --input examples/happy_path/protocol.md --output out.docx
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from app.docx.builder import save_docx
from app.logging_setup import configure_logging
from app.protocol.parser import ParseError, parse_protocol

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    configure_logging()

    parser = argparse.ArgumentParser(
        description="Конвертер markdown-протокола в .docx",
    )
    parser.add_argument("--input", type=Path, required=True, help="Путь к .md с протоколом")
    parser.add_argument("--output", type=Path, required=True, help="Путь к .docx на выходе")
    args = parser.parse_args(argv)

    if not args.input.exists():
        logger.error("Входной файл не найден: %s", args.input)
        return 1

    md = args.input.read_text(encoding="utf-8")

    try:
        protocol = parse_protocol(md)
    except ParseError as e:
        logger.error("Не удалось распарсить протокол: %s", e)
        return 2

    save_docx(protocol, args.output)
    logger.info("Готово: %s", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())