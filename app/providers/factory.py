from __future__ import annotations

import os

from app.providers.base import LLMProvider
from app.providers.deepseek import DeepSeekProvider


def build_llm() -> LLMProvider | None:
    """Return a real provider when configured, otherwise None (rule-based mode)."""
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        return None
    return DeepSeekProvider(api_key, model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"))
