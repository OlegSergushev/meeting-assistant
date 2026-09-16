"""Доменная модель протокола: константы, Pydantic-модели, парсер."""
from app.protocol.constants import PLACEHOLDER
from app.protocol.models import Protocol, Task
from app.protocol.parser import ParseError, parse_protocol

__all__ = [
    "PLACEHOLDER",
    "Protocol",
    "Task",
    "ParseError",
    "parse_protocol",
]