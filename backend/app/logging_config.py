"""Logging tập trung — console + file (rotate)."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(level: str = "INFO", log_file: str | None = None) -> None:
    """Cấu hình logging cho toàn app."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Xóa handler cũ để tránh log trùng dòng nếu setup_logging gọi nhiều lần
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler (UTF-8)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    console.stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    root.addHandler(console)

    # File handler (optional)
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)

    # Giảm noise từ thư viện
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
