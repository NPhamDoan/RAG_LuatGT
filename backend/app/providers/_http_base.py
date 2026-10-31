"""Tiện ích dùng chung cho các LLM provider + base class cho provider gọi HTTP thuần.

Gom phần lặp giữa các provider: dựng messages, cảnh báo content rỗng, và khung
POST → raise_for_status → log lỗi cho provider dùng httpx (Mistral, Cohere).

Provider dùng SDK riêng (Groq, Gemini) chỉ tái dùng `build_messages` / `warn_if_empty`.
"""

from __future__ import annotations

import logging

import httpx

from app.providers.llm_provider import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

# Số ký tự body lỗi ghi vào log (đủ chẩn đoán, tránh log quá dài).
ERR_BODY_PREVIEW = 300


def build_messages(prompt: str, system_prompt: str = "") -> list[dict]:
    """Dựng danh sách messages chuẩn OpenAI (system tùy chọn + user)."""
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return messages


def warn_if_empty(
    logger: logging.Logger, provider: str, content: str, model: str, finish_reason
) -> None:
    """Log cảnh báo khi content rỗng, hoặc log info độ dài khi có content.

    Content rỗng KHÔNG phải exception nhưng cần chủ động cảnh báo để không lọt âm thầm.
    """
    if not content:
        logger.warning(
            "%s trả CONTENT RỖNG: model=%s, finish_reason=%s", provider, model, finish_reason
        )
    else:
        logger.info(
            "%s response: %d ký tự, finish_reason=%s", provider, len(content), finish_reason
        )
    logger.debug("%s content đầy đủ:\n%s", provider, content)


class HttpLLMProvider(LLMProvider):
    """Base cho provider gọi Chat API qua HTTP (Bearer auth, JSON).

    Lớp con chỉ cần khai `PROVIDER`, `URL` và cài `_extract` để bóc nội dung từ response.
    Khung chung lo: dựng messages + payload, POST, raise_for_status, log lỗi/cảnh báo.
    """

    PROVIDER: str = "HTTP LLM"
    URL: str = ""

    def __init__(self, api_key: str, model: str, timeout: int, max_tokens: int):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._max_tokens = max_tokens

    def _build_payload(self, messages: list[dict]) -> dict:
        """Payload chuẩn OpenAI-compatible. Lớp con override nếu cần khác."""
        return {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": self._max_tokens,
        }

    def _extract(self, data: dict) -> tuple[str, str | None]:
        """Bóc (content, finish_reason) từ response JSON. Lớp con BẮT BUỘC cài."""
        raise NotImplementedError

    async def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        messages = build_messages(prompt, system_prompt)
        payload = self._build_payload(messages)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        logger.info("%s request: model=%s, prompt_len=%d", self.PROVIDER, self._model, len(prompt))
        logger.debug("%s prompt đầy đủ:\n%s", self.PROVIDER, prompt)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(self.URL, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            # 401 sai key, 422 sai tham số, 429 rate limit... → log rõ để chẩn đoán.
            logger.error(
                "%s trả HTTP %s: %s",
                self.PROVIDER, exc.response.status_code, exc.response.text[:ERR_BODY_PREVIEW],
            )
            raise
        except httpx.HTTPError as exc:
            logger.error("Lỗi kết nối %s (%s): %s", self.PROVIDER, self.URL, exc)
            raise

        content, finish_reason = self._extract(data)
        warn_if_empty(logger, self.PROVIDER, content, self._model, finish_reason)
        return LLMResponse(content=content)
