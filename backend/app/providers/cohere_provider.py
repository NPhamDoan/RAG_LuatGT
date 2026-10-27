"""Cohere LLM provider (cloud, Chat API v2).

Dung khi PRIMARY_LLM_PROVIDER=cohere. Goi Chat API v2:
    POST https://api.cohere.com/v2/chat
Can API key tu dashboard.cohere.com (co free TRIAL key, gioi han rate, phi thuong mai).
Khac OpenAI: response 'message.content' la MANG block {type,text} -> phai ghep text.
Command R/A khong phai model reasoning -> khong ton token suy luan.
"""

import logging

import httpx

from app.providers.llm_provider import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

_COHERE_URL = "https://api.cohere.com/v2/chat"


class CohereProvider(LLMProvider):
    """LLM synthesis dung Cohere Chat API v2."""

    def __init__(
        self,
        api_key: str,
        model: str = "command-r-08-2024",
        timeout: int = 30,
        max_tokens: int = 2048,
    ):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._max_tokens = max_tokens

    async def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": self._max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        logger.info("Cohere request: model=%s, prompt_len=%d", self._model, len(prompt))
        logger.debug("Cohere prompt day du:\n%s", prompt)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(_COHERE_URL, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            # 401 sai key, 422 sai tham so, 429 rate limit (trial gioi han)... -> log ro.
            logger.error(
                "Cohere tra HTTP %s: %s", exc.response.status_code, exc.response.text[:300]
            )
            raise
        except httpx.HTTPError as exc:
            logger.error("Loi ket noi Cohere (%s): %s", _COHERE_URL, exc)
            raise

        # v2: message.content la mang block {type,text} -> ghep cac block type=text.
        message = data.get("message") or {}
        blocks = message.get("content") or []
        content = "".join(
            b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"
        ).strip()
        finish_reason = data.get("finish_reason")

        if not content:
            # Content rong KHONG phai exception -> chu dong canh bao.
            logger.warning(
                "Cohere tra CONTENT RONG: model=%s, finish_reason=%s", self._model, finish_reason
            )
        else:
            logger.info(
                "Cohere response: %d ky tu, finish_reason=%s", len(content), finish_reason
            )
        logger.debug("Cohere content day du:\n%s", content)

        return LLMResponse(content=content)
