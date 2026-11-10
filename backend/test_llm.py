"""Script kiểm tra nhanh cấu hình LLM trong backend/.env.

Cách chạy (từ thư mục gốc hoặc thư mục backend):
    .\backend\.venv\Scripts\python.exe backend/test_llm.py
    .\backend\.venv\Scripts\python.exe backend/test_llm.py --provider groq
    .\backend\.venv\Scripts\python.exe backend/test_llm.py --role verify
    .\backend\.venv\Scripts\python.exe backend/test_llm.py --all
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)

# Đảm bảo import được package `app` dù chạy từ thư mục gốc hay thư mục `backend/`
_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.config import Settings, get_settings
from app.providers.llm_factory import _build

ALL_PROVIDERS = ("groq", "mistral", "cohere", "gemini", "fosta", "ollama")


def _mask_key(key: str) -> str:
    if not key:
        return "(trống)"
    if len(key) <= 10:
        return "***"
    return f"{key[:6]}...{key[-4:]}"


async def test_one_provider(
    settings: Settings,
    provider_name: str,
    prompt: str,
    system_prompt: str,
) -> bool:
    """Test 1 provider theo cấu hình trong .env. Trả True nếu thành công."""
    print("=" * 65, flush=True)
    try:
        choice = settings.resolve_llm(provider_name)
    except Exception as exc:
        print(f"[LỖI CẤU HÌNH] provider={provider_name!r}: {exc}", flush=True)
        return False

    print(f"Provider       : {choice.kind}", flush=True)
    print(f"Model          : {choice.model}", flush=True)
    if choice.base_url:
        print(f"Base URL       : {choice.base_url}", flush=True)
    if choice.kind != "ollama":
        print(f"API Key        : {_mask_key(choice.api_key)}", flush=True)
    if choice.kind == "fosta":
        print(f"Wire API       : {choice.wire_api}", flush=True)
    if choice.reasoning_effort is not None:
        print(f"Reasoning      : {choice.reasoning_effort}", flush=True)
    print(f"Timeout / MaxT : {choice.timeout}s / {choice.max_tokens} tokens", flush=True)

    if choice.kind != "ollama" and not choice.api_key.strip():
        print(f"-> [BỎ QUA] Chưa điền API key cho '{choice.kind}' trong backend/.env.", flush=True)
        return False

    llm = _build(choice)
    start = time.perf_counter()
    try:
        resp = await llm.generate(prompt=prompt, system_prompt=system_prompt)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if not resp.content.strip():
            print(f"-> [CẢNH BÁO] ({elapsed_ms:.0f}ms) LLM trả về chuỗi RỖNG!", flush=True)
            return False
        print(f"-> [THÀNH CÔNG] ({elapsed_ms:.0f}ms) Độ dài: {len(resp.content)} ký tự", flush=True)
        print("-" * 65, flush=True)
        print(resp.content.strip(), flush=True)
        print(flush=True)
        return True
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"-> [THẤT BẠI] ({elapsed_ms:.0f}ms) {type(exc).__name__}: {exc}", flush=True)
        body = getattr(getattr(exc, "response", None), "text", None)
        if body:
            print(f"   Chi tiết HTTP: {body[:400]}", flush=True)
        print(flush=True)
        return False


async def main() -> int:
    # Cấu hình stdout UTF-8 trên Windows để in tiếng Việt không lỗi font
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Kiểm tra kết nối LLM theo cấu hình backend/.env")
    parser.add_argument(
        "--provider", "-p",
        help="Tên provider muốn test (groq | mistral | cohere | gemini | fosta | ollama). Mặc định: theo --role.",
    )
    parser.add_argument(
        "--role", "-r",
        choices=("primary", "verify"),
        default="primary",
        help="Vai trò cần test trong .env: primary (PRIMARY_LLM_PROVIDER) hoặc verify (VERIFY_LLM_PROVIDER).",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Test toàn bộ các provider đã khai báo trong .env.",
    )
    parser.add_argument(
        "--prompt",
        default="Xe thô sơ gồm những loại xe nào theo Luật Trật tự, an toàn giao thông đường bộ? Trả lời ngắn gọn 2 câu.",
        help="Câu hỏi thử nghiệm gửi tới LLM.",
    )
    args = parser.parse_args()

    settings = get_settings()
    system_prompt = "Bạn là trợ lý pháp luật giao thông Việt Nam. Trả lời chính xác, ngắn gọn bằng tiếng Việt."

    if args.all:
        print(
            f"Đang test tất cả provider trong backend/.env "
            f"(PRIMARY={settings.primary_llm_provider}, VERIFY={settings.verify_llm_provider})...",
            flush=True,
        )
        results = {}
        for name in ALL_PROVIDERS:
            results[name] = await test_one_provider(settings, name, args.prompt, system_prompt)
        print("=" * 65, flush=True)
        print("TỔNG KẾT:", flush=True)
        for name, ok in results.items():
            status = "PASS" if ok else "FAIL/SKIP"
            print(f"  - {name:<10}: {status}", flush=True)
        return 0 if any(results.values()) else 1

    if args.provider:
        target = args.provider.strip().lower()
        print(f"Đang test provider chỉ định: '{target}'", flush=True)
    elif args.role == "verify":
        target = settings.verify_llm_provider
        print(f"Đang test VERIFY_LLM_PROVIDER = '{target}' (từ backend/.env)", flush=True)
    else:
        target = settings.primary_llm_provider
        print(f"Đang test PRIMARY_LLM_PROVIDER = '{target}' (từ backend/.env)", flush=True)

    ok = await test_one_provider(settings, target, args.prompt, system_prompt)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
