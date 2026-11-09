"""Fosta (codex.fosta.app) LLM provider — cổng proxy OpenAI Codex.

Dùng khi PRIMARY_LLM_PROVIDER=fosta (hoặc VERIFY_LLM_PROVIDER=fosta).
Hỗ trợ cả 2 giao thức của OpenAI / Codex CLI mà không cần cài đặt @openai/codex:
- Responses API:        POST {base_url}/responses         (mặc định của Codex CLI: wire_api="responses")
- Chat Completions API: POST {base_url}/chat/completions  (OpenAI-compatible: wire_api="chat")

Đặc thù Fosta:
- Danh sách model trên Fosta có tiền tố `cx/` (vd: `cx/gpt-6.1-sol`, `cx/gpt-6-astra`, `cx/gpt-6-sol`, `cx/gpt-6-luna`).
- Nếu cấu hình thiếu `cx/` hoặc model cũ bị Fosta gỡ (`model_not_found` / `not supported when using Codex`),
  provider tự động thử thêm tiền tố `cx/` hoặc truy vấn `GET {base_url}/models` để lấy model khả dụng đầu tiên.
"""

from __future__ import annotations

import json
import logging

import httpx

from app.providers._http_base import ERR_BODY_PREVIEW, build_messages, warn_if_empty
from app.providers.llm_provider import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

DEFAULT_FOSTA_MODEL = "cx/gpt-6.1-sol"


def _normalize_base_url(base_url: str) -> str:
    """Chuẩn hóa base_url về dạng có /v1 ở cuối (vd https://codex.fosta.app/v1)."""
    url = (base_url or "https://codex.fosta.app/v1").strip().rstrip("/")
    if not url.endswith("/v1") and "/v1/" not in url:
        url = f"{url}/v1"
    return url


def _is_unsupported_model_error(resp: httpx.Response, current_model: str = "") -> bool:
    """Kiểm tra lỗi HTTP 400/404/503 do tên model không được Fosta/Codex hỗ trợ."""
    if resp.status_code not in (400, 404, 503):
        return False
    text_lower = resp.text.lower()
    if not current_model.startswith("cx/") and "[codex/" in text_lower:
        return True
    return (
        "model_not_found" in text_lower
        or "is not supported when using codex" in text_lower
        or "model not found" in text_lower
        or "invalid model" in text_lower
    )


def _extract_from_dict(data: dict) -> tuple[str, str | None]:
    """Bóc tách (content, finish_reason) từ JSON của cả Responses API lẫn Chat Completions API."""
    # 1. Chuẩn OpenAI Chat Completions: choices[0].message.content
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0] if isinstance(choices[0], dict) else {}
        msg = choice.get("message") or {}
        content = msg.get("content") or ""
        return str(content).strip(), choice.get("finish_reason")

    # 2. Chuẩn OpenAI Responses API: trường rút gọn output_text
    if isinstance(data.get("output_text"), str) and data["output_text"]:
        return data["output_text"].strip(), data.get("status")

    # 3. Chuẩn OpenAI Responses API: mảng output[].content[].text
    output = data.get("output")
    if isinstance(output, list):
        parts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content_list = item.get("content")
            if isinstance(content_list, list):
                for block in content_list:
                    if not isinstance(block, dict):
                        continue
                    b_type = block.get("type", "")
                    if b_type in ("output_text", "text", "") and isinstance(block.get("text"), str):
                        parts.append(block["text"])
        if parts:
            return "".join(parts).strip(), data.get("status")

    return "", data.get("status") or data.get("finish_reason")


def _extract_from_sse(raw_text: str) -> tuple[str, str | None]:
    """Bóc nội dung khi cổng proxy trả về dạng SSE stream (text/event-stream)."""
    deltas: list[str] = []
    finish_reason: str | None = None

    for line in raw_text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload_str = line[5:].strip()
        if not payload_str or payload_str == "[DONE]":
            continue
        try:
            evt = json.loads(payload_str)
        except json.JSONDecodeError:
            continue
        if not isinstance(evt, dict):
            continue

        evt_type = evt.get("type", "")
        if evt_type == "response.output_text.delta" and isinstance(evt.get("delta"), str):
            deltas.append(evt["delta"])
        elif evt_type == "response.completed" and isinstance(evt.get("response"), dict):
            finish_reason = evt["response"].get("status", "completed")
            if not deltas:
                text, _ = _extract_from_dict(evt["response"])
                if text:
                    deltas.append(text)
        elif isinstance(evt.get("choices"), list) and evt["choices"]:
            ch = evt["choices"][0] if isinstance(evt["choices"][0], dict) else {}
            delta_obj = ch.get("delta") or {}
            if isinstance(delta_obj.get("content"), str):
                deltas.append(delta_obj["content"])
            if ch.get("finish_reason"):
                finish_reason = ch.get("finish_reason")

    return "".join(deltas).strip(), finish_reason


class FostaProvider(LLMProvider):
    """LLM provider kết nối trực tiếp tới Fosta (codex.fosta.app)."""

    PROVIDER = "Fosta"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_FOSTA_MODEL,
        base_url: str = "https://codex.fosta.app/v1",
        timeout: int = 30,
        max_tokens: int = 2048,
        wire_api: str = "responses",
        reasoning_effort: str | None = "low",
    ):
        self._api_key = api_key
        self._model = (model or DEFAULT_FOSTA_MODEL).strip()
        self._base_url = _normalize_base_url(base_url)
        self._timeout = timeout
        self._max_tokens = max_tokens
        self._wire_api = (wire_api or "responses").strip().lower()
        self._reasoning_effort = reasoning_effort or None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    def _build_responses_payload(self, prompt: str, system_prompt: str = "", model: str | None = None) -> dict:
        """Payload cho endpoint /v1/responses (chuẩn OpenAI Responses API của Codex CLI)."""
        payload: dict = {
            "model": model or self._model,
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                }
            ],
            "max_output_tokens": self._max_tokens,
        }
        if system_prompt:
            payload["instructions"] = system_prompt
        if self._reasoning_effort:
            payload["reasoning"] = {"effort": self._reasoning_effort}
        return payload

    def _build_chat_payload(self, prompt: str, system_prompt: str = "", model: str | None = None) -> dict:
        """Payload cho endpoint /v1/chat/completions (chuẩn OpenAI Chat Completions)."""
        payload: dict = {
            "model": model or self._model,
            "messages": build_messages(prompt, system_prompt),
            "temperature": 0.2,
            "max_tokens": self._max_tokens,
        }
        if self._reasoning_effort:
            payload["reasoning_effort"] = self._reasoning_effort
        return payload

    @staticmethod
    def _parse_response(resp: httpx.Response) -> tuple[str, str | None]:
        content_type = (resp.headers.get("content-type") or "").lower()
        raw_text = resp.text.strip()
        if "text/event-stream" in content_type or raw_text.startswith("event:") or raw_text.startswith("data:"):
            return _extract_from_sse(raw_text)
        try:
            data = resp.json()
        except json.JSONDecodeError:
            return _extract_from_sse(raw_text)
        if isinstance(data, dict):
            return _extract_from_dict(data)
        return "", None

    async def _discover_fallback_model(self, client: httpx.AsyncClient, failed_model: str) -> str | None:
        """Tìm model thay thế khi model cấu hình bị lỗi model_not_found trên Fosta."""
        # Nếu người dùng quên tiền tố cx/ (vd điền gpt-6-astra), thử cx/<model> trước
        if "/" not in failed_model:
            prefixed = f"cx/{failed_model}"
            try:
                r = await client.get(f"{self._base_url}/models", headers=self._headers())
                if r.status_code == 200:
                    ids = [m.get("id", "") for m in (r.json().get("data") or []) if isinstance(m, dict)]
                    if prefixed in ids:
                        return prefixed
                    if ids:
                        return ids[0]
            except Exception:
                return prefixed

        # Ngược lại, lấy model đầu tiên từ danh sách /v1/models của Fosta
        try:
            r = await client.get(f"{self._base_url}/models", headers=self._headers())
            if r.status_code == 200:
                ids = [m.get("id", "") for m in (r.json().get("data") or []) if isinstance(m, dict) and m.get("id")]
                for mid in ids:
                    if mid != failed_model:
                        return mid
        except Exception as exc:
            logger.debug("Không lấy được danh sách /models từ Fosta: %s", exc)
        return None

    async def _post(
        self, client: httpx.AsyncClient, url: str, prompt: str, system_prompt: str, is_chat: bool
    ) -> httpx.Response:
        build_fn = self._build_chat_payload if is_chat else self._build_responses_payload
        payload = build_fn(prompt, system_prompt, self._model)
        resp = await client.post(url, json=payload, headers=self._headers())

        # Nếu model cấu hình không được hỗ trợ trên Fosta -> tự động dò model khả dụng từ /v1/models
        if _is_unsupported_model_error(resp, self._model):
            fallback_model = await self._discover_fallback_model(client, self._model)
            if fallback_model and fallback_model != self._model:
                logger.warning(
                    "%s: model '%s' không được hỗ trợ → tự động chuyển sang '%s' (hãy cập nhật FOSTA_MODEL trong .env).",
                    self.PROVIDER, self._model, fallback_model,
                )
                self._model = fallback_model
                payload = build_fn(prompt, system_prompt, self._model)
                resp = await client.post(url, json=payload, headers=self._headers())

        # Một số cổng Codex yêu cầu stream=True trên /responses (trả 400 nếu không bật stream)
        if (
            resp.status_code == 400
            and not is_chat
            and "stream" in resp.text.lower()
            and not payload.get("stream")
        ):
            stream_payload = {**payload, "stream": True}
            resp = await client.post(url, json=stream_payload, headers=self._headers())

        resp.raise_for_status()
        return resp

    async def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        logger.info(
            "%s request: model=%s, wire_api=%s, prompt_len=%d",
            self.PROVIDER, self._model, self._wire_api, len(prompt),
        )
        logger.debug("%s prompt đầy đủ:\n%s", self.PROVIDER, prompt)

        responses_url = f"{self._base_url}/responses"
        chat_url = f"{self._base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                if self._wire_api == "chat":
                    resp = await self._post(client, chat_url, prompt, system_prompt, is_chat=True)
                elif self._wire_api == "responses":
                    resp = await self._post(client, responses_url, prompt, system_prompt, is_chat=False)
                else:
                    try:
                        resp = await self._post(client, responses_url, prompt, system_prompt, is_chat=False)
                    except httpx.HTTPStatusError as exc:
                        if exc.response.status_code in (404, 405):
                            logger.info(
                                "%s /responses trả %d → chuyển sang /chat/completions",
                                self.PROVIDER, exc.response.status_code,
                            )
                            resp = await self._post(client, chat_url, prompt, system_prompt, is_chat=True)
                        else:
                            raise
        except httpx.HTTPStatusError as exc:
            logger.error(
                "%s trả HTTP %s: %s",
                self.PROVIDER, exc.response.status_code, exc.response.text[:ERR_BODY_PREVIEW],
            )
            raise
        except httpx.HTTPError as exc:
            logger.error("Lỗi kết nối %s (%s): %s", self.PROVIDER, self._base_url, exc)
            raise

        content, finish_reason = self._parse_response(resp)
        warn_if_empty(logger, self.PROVIDER, content, self._model, finish_reason)
        return LLMResponse(content=content)
