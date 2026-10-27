"""Interface cho LLM provider."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Response từ LLM."""
    content: str


class LLMProvider(ABC):
    """Abstract base cho LLM."""

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        """Gọi LLM, trả về response."""
