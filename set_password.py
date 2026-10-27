"""Doi mat khau admin: sinh hash PBKDF2 va ghi thang vao backend/.env.

Dung:
    python set_password.py                 # nhap mat khau (an, an toan)
    python set_password.py "mat_khau_moi"  # truyen truc tiep (tien khi test)

Tu dong:
- Cap nhat ADMIN_PASSWORD_HASH.
- Neu AUTH_SECRET_KEY chua co / con la mac dinh -> sinh chuoi ngau nhien moi.
Sau khi chay: RESTART backend de co hieu luc.
"""

from __future__ import annotations

import getpass
import secrets
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "backend"))

from app.api.auth import hash_password  # noqa: E402

ENV = _ROOT / "backend" / ".env"
_DEFAULT_SECRET = "change-me-doi-thanh-chuoi-ngau-nhien-dai"


def _read_key(lines: list[str], key: str) -> str | None:
    for ln in lines:
        s = ln.strip()
        if s and not s.startswith("#") and "=" in ln and ln.split("=", 1)[0].strip() == key:
            return ln.split("=", 1)[1].strip()
    return None


def _upsert(lines: list[str], key: str, value: str) -> list[str]:
    out, found = [], False
    for ln in lines:
        s = ln.strip()
        if s and not s.startswith("#") and "=" in ln and ln.split("=", 1)[0].strip() == key:
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(ln)
    if not found:
        out.append(f"{key}={value}")
    return out


def main() -> None:
    if len(sys.argv) > 1:
        pw = sys.argv[1]
    else:
        pw = getpass.getpass("Nhap mat khau admin moi: ")
        if pw != getpass.getpass("Nhap lai: "):
            print("Hai lan nhap khong khop."); sys.exit(1)
    if not pw.strip():
        print("Mat khau rong."); sys.exit(1)

    if not ENV.exists():
        print(f"Khong thay {ENV}. Tao backend/.env truoc (copy tu .env.example)."); sys.exit(1)

    lines = ENV.read_text(encoding="utf-8").splitlines()
    lines = _upsert(lines, "ADMIN_PASSWORD_HASH", hash_password(pw))

    cur_secret = _read_key(lines, "AUTH_SECRET_KEY")
    if not cur_secret or cur_secret == _DEFAULT_SECRET:
        lines = _upsert(lines, "AUTH_SECRET_KEY", secrets.token_urlsafe(48))
        print("Da sinh AUTH_SECRET_KEY ngau nhien moi.")

    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Da cap nhat mat khau admin trong {ENV}")
    print(">>> RESTART backend de co hieu luc.")


if __name__ == "__main__":
    main()
