from __future__ import annotations

import httpx

from app.providers.base import LLMError, LLMResponse

# DeepSeek public list prices (USD / 1M tokens). Override via env if needed.
INPUT_PRICE_PER_1M = 0.27
OUTPUT_PRICE_PER_1M = 1.10


class DeepSeekProvider:
    """OpenAI-compatible DeepSeek client."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com",
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        response_format: dict | None = None,
    ) -> LLMResponse:
        payload: dict = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        try:
            response = self._client.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            prompt_tokens = int(usage.get("prompt_tokens", 0))
            completion_tokens = int(usage.get("completion_tokens", 0))
            cost = (
                prompt_tokens / 1_000_000 * INPUT_PRICE_PER_1M
                + completion_tokens / 1_000_000 * OUTPUT_PRICE_PER_1M
            )
            return LLMResponse(
                content=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost,
            )
        except Exception as exc:
            raise LLMError(f"deepseek request failed: {exc}") from exc
