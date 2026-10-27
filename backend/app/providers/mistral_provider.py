"""Mistral AI LLM provider (cloud, La Plateforme).

Dung khi PRIMARY_LLM_PROVIDER=mistral. Goi Chat Completions API (OpenAI-compatible):
    POST https://api.mistral.ai/v1/chat/completions
Can API key tu console.mistral.ai (co free tier). Mistral small/large KHONG phai model
reasoning -> khong ton token suy luan, khong can reasoning_effort.
"""

import logging

import httpx

from app.providers.llm_provider import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

_MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"


class MistralProvider(LLMProvider):
    """LLM synthesis dung Mistral AI API."""

    def __init__(
        self,
        api_key: str,
        model: str = "mistral-small-latest",
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

        logger.info("Mistral request: model=%s, prompt_len=%d", self._model, len(prompt))
        logger.debug("Mistral prompt day du:\n%s", prompt)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(_MISTRAL_URL, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            # 401 sai key, 422 sai tham so, 429 rate limit... -> log ro de chan doan.
            logger.error(
                "Mistral tra HTTP %s: %s", exc.response.status_code, exc.response.text[:300]
            )
            raise
        except httpx.HTTPError as exc:
            logger.error("Loi ket noi Mistral (%s): %s", _MISTRAL_URL, exc)
            raise

        choice = (data.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content", "") or ""
        finish_reason = choice.get("finish_reason")

        if not content:
            # Content rong KHONG phai exception -> chu dong canh bao, tranh loi lot am tham.
            logger.warning(
                "Mistral tra CONTENT RONG: model=%s, finish_reason=%s", self._model, finish_reason
            )
        else:
            logger.info(
                "Mistral response: %d ky tu, finish_reason=%s", len(content), finish_reason
            )
        logger.debug("Mistral content day du:\n%s", content)

        return LLMResponse(content=content)
