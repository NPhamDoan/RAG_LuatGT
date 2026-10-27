"""Auth admin (chỉ mật khẩu).

- Mật khẩu lưu dạng HASH (PBKDF2-HMAC-SHA256 + salt), KHÔNG lưu thô. Chỉ dùng stdlib.
- Đăng nhập đúng → cấp TOKEN ký HMAC + có hạn (exp). Không lưu session (stateless).
- `require_admin`: dependency chặn các route ghi. Nếu `admin_password_hash` TRỐNG → bỏ qua
  (auth tắt) để tương thích môi trường dev.

Tạo hash mật khẩu:  python -m app.api.auth "mat_khau_cua_ban"
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time

from fastapi import Header, HTTPException

from app.config import get_settings

logger = logging.getLogger(__name__)

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 200_000


# ---------- Mật khẩu (hash) ----------
def hash_password(password: str, iterations: int = _ITERATIONS) -> str:
    """Tạo hash PBKDF2: 'pbkdf2_sha256$<iter>$<salt_hex>$<hash_hex>'."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{_ALGO}${iterations}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """So mật khẩu với hash đã lưu (so sánh chống timing attack)."""
    try:
        algo, iter_s, salt_hex, hash_hex = stored.split("$")
        if algo != _ALGO:
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iter_s)
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


# ---------- Token (HMAC ký + hạn) ----------
def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def create_token(secret: str, ttl: int) -> str:
    """Tạo token 'payload_b64.signature' — payload chứa role + exp."""
    payload = _b64e(json.dumps({"role": "admin", "exp": int(time.time()) + ttl}).encode())
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_token(token: str, secret: str) -> bool:
    """Kiểm tra chữ ký + hạn + role. Sai/hết hạn → False."""
    try:
        payload_b64, sig = token.rsplit(".", 1)
        expected = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        data = json.loads(_b64d(payload_b64))
        return data.get("role") == "admin" and data.get("exp", 0) >= int(time.time())
    except Exception:
        return False


# ---------- Dependency chặn route ----------
def require_admin(authorization: str = Header(default="")) -> None:
    """Chặn route ghi: cần Bearer token hợp lệ. Auth TẮT nếu chưa cấu hình hash."""
    settings = get_settings()
    if not settings.admin_password_hash:
        return  # auth tắt (dev) — route ghi mở; đã cảnh báo ở startup
    token = authorization[7:].strip() if authorization[:7].lower() == "bearer " else authorization.strip()
    if not token or not verify_token(token, settings.auth_secret_key):
        raise HTTPException(status_code=401, detail="Cần đăng nhập admin (token không hợp lệ hoặc hết hạn).")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print('Dùng: python -m app.api.auth "mat_khau_cua_ban"')
        sys.exit(1)
    print(hash_password(sys.argv[1]))
