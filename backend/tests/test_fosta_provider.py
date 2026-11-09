"""Unit tests cho FostaProvider + Settings.resolve_llm('fosta')."""

import httpx

from app.config import Settings
from app.providers.fosta_provider import (
    FostaProvider,
    _extract_from_dict,
    _extract_from_sse,
    _normalize_base_url,
)
from app.providers.llm_factory import _build
from tests.fakes import run


def test_resolve_fosta_and_factory():
    s = Settings(
        fosta_api_key="test-key",
        fosta_base_url="https://codex.fosta.app",
        fosta_model="gpt-5.3-codex",
        fosta_wire_api="responses",
        fosta_reasoning_effort="low",
    )
    choice = s.resolve_llm("fosta")
    assert choice.kind == "fosta"
    assert choice.model == "gpt-5.3-codex"
    provider = _build(choice)
    assert isinstance(provider, FostaProvider)
    assert _normalize_base_url("https://codex.fosta.app") == "https://codex.fosta.app/v1"


def test_extract_responses_and_chat_and_sse():
    # Chat completions JSON
    c1, r1 = _extract_from_dict({
        "choices": [{"message": {"content": "Trả lời chat"}, "finish_reason": "stop"}]
    })
    assert c1 == "Trả lời chat"
    assert r1 == "stop"

    # Responses API JSON
    c2, r2 = _extract_from_dict({
        "status": "completed",
        "output": [
            {"type": "reasoning", "summary": []},
            {"type": "message", "content": [{"type": "output_text", "text": "Trả lời responses"}]},
        ],
    })
    assert c2 == "Trả lời responses"
    assert r2 == "completed"

    # Responses API SSE
    sse = (
        'event: response.output_text.delta\n'
        'data: {"type":"response.output_text.delta","delta":"Xin "}\n\n'
        'event: response.output_text.delta\n'
        'data: {"type":"response.output_text.delta","delta":"chào"}\n\n'
        'event: response.completed\n'
        'data: {"type":"response.completed","response":{"status":"completed"}}\n\n'
    )
    c3, r3 = _extract_from_sse(sse)
    assert c3 == "Xin chào"
    assert r3 == "completed"

