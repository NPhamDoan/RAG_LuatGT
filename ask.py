"""ask.py — hoi RAG luat giao thong qua API (khong can UI/frontend).

Backend phai dang chay truoc (run_backend.bat hoac run_all.bat).

    python ask.py "muc phat vuot den do xe may"      # hoi 1 cau
    python ask.py                                     # che do tuong tac (go nhieu cau, Ctrl+C thoat)
    python ask.py --url http://localhost:8000 "..."   # doi URL backend
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

# Console Windows mac dinh cp1252 -> in tieng Viet se loi. Ep UTF-8.
for _stream in (sys.stdout, sys.stdin):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def ask(url: str, cau_hoi: str, timeout: int = 180) -> dict:
    """Goi POST /api/query, tra ve dict KetQuaTraLoi."""
    body = json.dumps({"cauHoi": cau_hoi}).encode("utf-8")
    req = urllib.request.Request(
        f"{url}/api/query",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def show(kq: dict) -> None:
    """In ket qua goi gon."""
    print()
    print("=" * 70)
    print(f"[Do tin cay: {kq.get('doTinCay', '?')}]")
    print("-" * 70)
    print((kq.get("noiDung") or "").strip())

    trich = kq.get("trichDan") or []
    if trich:
        print("-" * 70)
        print("Trich dan:")
        for i, t in enumerate(trich, 1):
            dieu = t.get("dieu") or ""
            khoan = t.get("khoan") or ""
            extra = f" ({khoan})" if khoan else ""
            print(f"  [{i}] {t.get('soHieu', '')} - {dieu}{extra}")

    if kq.get("chunksGoc"):
        print("-" * 70)
        print("(LLM loi/timeout -> tra chunk goc thay vi tong hop)")
    print("=" * 70)


def _ask_and_show(url: str, q: str) -> None:
    q = q.strip()
    if not q:
        return
    try:
        show(ask(url, q))
    except urllib.error.URLError as exc:
        print(f"LOI ket noi {url} — backend da chay chua? (chay run_backend.bat). Chi tiet: {exc}")
    except Exception as exc:  # noqa: BLE001
        print(f"LOI: {type(exc).__name__}: {exc}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Hoi RAG luat giao thong qua API (khong can UI).")
    ap.add_argument("cauHoi", nargs="*", help="Cau hoi. Bo trong = che do tuong tac.")
    ap.add_argument("--url", default="http://localhost:8000", help="URL backend (mac dinh localhost:8000).")
    args = ap.parse_args()
    url = args.url.rstrip("/")

    if args.cauHoi:
        _ask_and_show(url, " ".join(args.cauHoi))
        return

    print(f"Che do tuong tac — backend: {url} (Ctrl+C de thoat).")
    try:
        while True:
            q = input("\nHoi> ")
            _ask_and_show(url, q)
    except (KeyboardInterrupt, EOFError):
        print("\nTam biet.")


if __name__ == "__main__":
    main()
