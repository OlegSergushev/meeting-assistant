"""Стили и константы оформления .docx."""
from __future__ import annotations

from docx.shared import Cm, Pt, RGBColor

# Шрифт по умолчанию
FONT_NAME = "Calibri"
FONT_SIZE = Pt(11)

# Заголовки
H1_SIZE = Pt(16)
H2_SIZE = Pt(13)

# Плейсхолдеры
PLACEHOLDER_COLOR = RGBColor(0x80, 0x80, 0x80)  # серый
PLACEHOLDER_ITALIC = True

# Отступы
LIST_LEFT_INDENT = Cm(0.5)
PARAGRAPH_SPACE_AFTER = Pt(6)

# Таблица задач
TABLE_STYLE = "Table Grid"
TABLE_HEADER_BOLD = True