from __future__ import annotations

from app.providers.base import LLMResponse


class FakeLLM:
    """Deterministic provider for tests and offline demos."""

    def __init__(self, response: str = "") -> None:
        self.response = response
        self.calls: list[list[dict[str, str]]] = []

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        response_format: dict | None = None,
    ) -> LLMResponse:
        self.calls.append(messages)
        return LLMResponse(
            content=self.response,
            prompt_tokens=10,
            completion_tokens=5,
            cost_usd=0.0,
        )
