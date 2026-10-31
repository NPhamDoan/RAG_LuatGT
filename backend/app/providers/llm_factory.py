"""Factory tạo LLM provider theo config.

Mỗi vai trò (primary=tổng hợp, verify=xác minh) chỉ cần chọn TÊN provider trong .env
(PRIMARY_LLM_PROVIDER / VERIFY_LLM_PROVIDER); key + model lấy từ catalog trong Settings.
Thêm provider mới: thêm nhánh trong _build + nhánh tương ứng trong Settings.resolve_llm.
"""

import logging

from app.config import LLMChoice, Settings
from app.providers.cohere_provider import CohereProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.groq_provider import GroqProvider
from app.providers.llm_provider import LLMProvider
from app.providers.mistral_provider import MistralProvider
from app.providers.ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)


def _build(choice: LLMChoice) -> LLMProvider:
    """Dựng LLMProvider cụ thể từ LLMChoice đã phân giải."""
    if choice.kind == "groq":
        return GroqProvider(
            api_key=choice.api_key, model=choice.model, timeout=choice.timeout,
            max_tokens=choice.max_tokens, reasoning_effort=choice.reasoning_effort,
        )
    if choice.kind == "mistral":
        return MistralProvider(
            api_key=choice.api_key, model=choice.model,
            timeout=choice.timeout, max_tokens=choice.max_tokens,
        )
    if choice.kind == "cohere":
        return CohereProvider(
            api_key=choice.api_key, model=choice.model,
            timeout=choice.timeout, max_tokens=choice.max_tokens,
        )
    if choice.kind == "gemini":
        return GeminiProvider(
            api_key=choice.api_key, model=choice.model, timeout=choice.timeout,
        )
    if choice.kind == "ollama":
        return OllamaProvider(
            model=choice.model, base_url=choice.base_url, timeout=choice.timeout,
            think=choice.think,
        )
    raise ValueError(f"LLMChoice.kind='{choice.kind}' không hỗ trợ.")


def create_primary_llm(settings: Settings) -> LLMProvider:
    """LLM tổng hợp câu trả lời (theo PRIMARY_LLM_PROVIDER)."""
    choice = settings.resolve_llm(settings.primary_llm_provider)
    logger.info("Khoi tao LLM synthesis: provider=%s, model=%s", choice.kind, choice.model)
    return _build(choice)
