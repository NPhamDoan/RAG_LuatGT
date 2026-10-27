"""Groq LLM provider."""

import logging

from groq import AsyncGroq

from app.providers.llm_provider import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class GroqProvider(LLMProvider):
    """LLM provider dùng Groq API."""

    def __init__(
        self,
        api_key: str,
        model: str = "openai/gpt-oss-20b",
        timeout: int = 10,
        max_tokens: int = 2048,
        reasoning_effort: str | None = "low",
    ):
        self._client = AsyncGroq(api_key=api_key)
        self._model = model
        self._timeout = timeout
        self._max_tokens = max_tokens
        # gpt-oss/qwen3 la model REASONING: "low" giam token suy luan (tranh an het max_tokens
        # -> content rong). "" / None = khong gui (de model tu quyet).
        self._reasoning_effort = reasoning_effort or None

    async def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        logger.info("Groq request: model=%s, prompt_len=%d", self._model, len(prompt))
        logger.debug("Groq prompt đầy đủ:\n%s", prompt)

        # reasoning_effort truyen qua extra_body (an toan moi phien ban SDK Groq).
        extra_body = {"reasoning_effort": self._reasoning_effort} if self._reasoning_effort else {}

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.2,
            max_tokens=self._max_tokens,
            # Chống lặp vô hạn (model kẹt lặp "điều 7, khoản 6..."): phạt token lặp lại.
            frequency_penalty=0.5,
            presence_penalty=0.3,
            timeout=self._timeout,
            extra_body=extra_body,
        )

        choice = response.choices[0]
        content = choice.message.content or ""
        finish_reason = getattr(choice, "finish_reason", None)

        # Bóc thông tin token (đặc biệt reasoning_tokens của model gpt-oss) để chẩn đoán.
        usage = getattr(response, "usage", None)
        details = getattr(usage, "completion_tokens_details", None) if usage else None
        reasoning_tokens = getattr(details, "reasoning_tokens", None) if details else None
        completion_tokens = getattr(usage, "completion_tokens", None) if usage else None

        if not content:
            # Content rỗng KHÔNG phải exception → phải chủ động cảnh báo, nếu không lỗi lọt âm thầm.
            logger.warning(
                "Groq trả CONTENT RỖNG: model=%s, finish_reason=%s, "
                "completion_tokens=%s, reasoning_tokens=%s",
                self._model, finish_reason, completion_tokens, reasoning_tokens,
            )
        else:
            logger.info(
                "Groq response: %d ký tự, finish_reason=%s (reasoning_tokens=%s)",
                len(content), finish_reason, reasoning_tokens,
            )
        logger.debug("Groq content đầy đủ:\n%s", content)

        return LLMResponse(content=content)
