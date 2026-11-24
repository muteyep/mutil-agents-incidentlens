from __future__ import annotations

import re

PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+the\s+above",
    r"system\s+prompt",
    r"you\s+are\s+now",
    r"report\s+.+\s+as\s+(the\s+)?root\s+cause",
    r"忽略.{0,10}(之前|以上).{0,10}指令",
    r"根因.{0,10}(改为|改成|是)",
]


def scan(text: str) -> list[str]:
    """Return matched injection patterns. Empty list means clean."""
    return [pattern for pattern in PATTERNS if re.search(pattern, text, re.IGNORECASE)]
