"""Mistral AI LLM provider (cloud, La Plateforme).

Dùng khi PRIMARY_LLM_PROVIDER=mistral. Gọi Chat Completions API (OpenAI-compatible):
    POST https://api.mistral.ai/v1/chat/completions
Cần API key từ console.mistral.ai (có free tier). Mistral small/large KHÔNG phải model
reasoning → không tốn token suy luận, không cần reasoning_effort.
"""

from app.providers._http_base import HttpLLMProvider


class MistralProvider(HttpLLMProvider):
    """LLM synthesis dùng Mistral AI API (OpenAI-compatible)."""

    PROVIDER = "Mistral"
    URL = "https://api.mistral.ai/v1/chat/completions"

    def __init__(
        self,
        api_key: str,
        model: str = "mistral-small-latest",
        timeout: int = 30,
        max_tokens: int = 2048,
    ):
        super().__init__(api_key=api_key, model=model, timeout=timeout, max_tokens=max_tokens)

    def _extract(self, data: dict) -> tuple[str, str | None]:
        choice = (data.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content", "") or ""
        return content, choice.get("finish_reason")
