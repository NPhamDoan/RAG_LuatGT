"""Ollama LLM Provider — chay model local qua Ollama (endpoint /api/chat).

Dung khi PRIMARY_LLM_PROVIDER=ollama. Ollama phai dang chay (ollama serve) va da
`ollama pull <model>`. Model CPU co the cham -> tang PRIMARY_LLM_TIMEOUT trong .env.
"""

import logging
import re

import httpx

from app.providers.llm_provider import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

# Loai bo phan suy luan <think>...</think> cua cac model thinking (vd qwen3).
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


class OllamaProvider(LLMProvider):
    """LLM synthesis chay local qua Ollama."""

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout: int = 180,
        think: bool | None = None,
    ):
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        # None = để model tự quyết; False = TẮT suy luận (bỏ <think>, nhanh hơn với qwen3...).
        self._think = think

    async def _post_chat(self, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()

    async def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "repeat_penalty": 1.3,   # chong lap (tuong duong frequency_penalty)
                "num_predict": 2048,     # gioi han token dau ra
            },
        }
        if self._think is not None:
            payload["think"] = self._think   # think=False: model bo qua suy luan -> nhanh hon

        logger.info(
            "Ollama request: model=%s, prompt_len=%d, think=%s",
            self._model, len(prompt), self._think,
        )
        logger.debug("Ollama prompt day du:\n%s", prompt)

        try:
            data = await self._post_chat(payload)
        except httpx.ConnectError as exc:
            logger.error(
                "Khong ket noi duoc Ollama tai %s (Ollama da chay chua? `ollama serve`): %s",
                self._base_url, exc,
            )
            raise
        except httpx.HTTPStatusError as exc:
            # Model khong ho tro tham so 'think' -> goi lai khong kem think.
            if (
                self._think is not None
                and exc.response.status_code == 400
                and "think" in exc.response.text.lower()
            ):
                logger.warning(
                    "Model '%s' khong ho tro 'think' -> goi lai khong kem think.", self._model
                )
                payload.pop("think", None)
                data = await self._post_chat(payload)
            else:
                logger.error(
                    "Ollama tra HTTP %s: %s", exc.response.status_code, exc.response.text[:300]
                )
                raise

        message = data.get("message") or {}
        content = message.get("content", "") or ""
        content = _THINK_RE.sub("", content).strip()
        done_reason = data.get("done_reason")

        if not content:
            logger.warning(
                "Ollama tra CONTENT RONG: model=%s, done_reason=%s", self._model, done_reason
            )
            raise RuntimeError(
                f"Ollama trả content rỗng (model={self._model}, done_reason={done_reason})"
            )
        else:
            logger.info(
                "Ollama response: %d ky tu, done_reason=%s", len(content), done_reason
            )
        logger.debug("Ollama content day du:\n%s", content)

        return LLMResponse(content=content)
