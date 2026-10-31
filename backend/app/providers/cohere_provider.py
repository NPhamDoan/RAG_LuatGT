"""Cohere LLM provider (cloud, Chat API v2).

Dùng khi PRIMARY_LLM_PROVIDER=cohere. Gọi Chat API v2:
    POST https://api.cohere.com/v2/chat
Cần API key từ dashboard.cohere.com (có free TRIAL key, giới hạn rate, phí thương mại).
Khác OpenAI: response 'message.content' là MẢNG block {type,text} → phải ghép text.
Command R/A không phải model reasoning → không tốn token suy luận.
"""

from app.providers._http_base import HttpLLMProvider


class CohereProvider(HttpLLMProvider):
    """LLM synthesis dùng Cohere Chat API v2."""

    PROVIDER = "Cohere"
    URL = "https://api.cohere.com/v2/chat"

    def __init__(
        self,
        api_key: str,
        model: str = "command-r-08-2024",
        timeout: int = 30,
        max_tokens: int = 2048,
    ):
        super().__init__(api_key=api_key, model=model, timeout=timeout, max_tokens=max_tokens)

    def _extract(self, data: dict) -> tuple[str, str | None]:
        # v2: message.content là mảng block {type,text} → ghép các block type=text.
        blocks = (data.get("message") or {}).get("content") or []
        content = "".join(
            b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"
        ).strip()
        return content, data.get("finish_reason")
