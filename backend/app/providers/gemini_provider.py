"""Google Gemini LLM provider."""

import logging

import google.generativeai as genai

from app.providers.llm_provider import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """LLM provider dùng Google Gemini API."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash", timeout: int = 15):
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model)
        self._timeout = timeout

    async def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        logger.debug("Gemini request: prompt_len=%d", len(full_prompt))
        logger.debug("Gemini prompt day du:\n%s", full_prompt)

        response = await self._model.generate_content_async(
            full_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=2048,
            ),
        )

        content = response.text or ""
        finish_reason = None
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            finish_reason = getattr(candidates[0], "finish_reason", None)
        logger.debug(
            "Gemini response: %d chars, finish_reason=%s",
            len(content),
            finish_reason,
        )
        logger.debug("Gemini content day du:\n%s", content)
        return LLMResponse(content=content)
