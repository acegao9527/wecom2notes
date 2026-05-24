"""日志与文件名清理工具。"""
from __future__ import annotations

import re


SECRET_PATTERNS = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"(token=)[^&\s]+", re.IGNORECASE),
    re.compile(r"(secret=)[^&\s]+", re.IGNORECASE),
    re.compile(r"(password=)[^&\s]+", re.IGNORECASE),
]


def redact_secret(value: str | None, keep: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep:
        return "***"
    return f"{value[:keep]}***"


def sanitize_log_text(text: str) -> str:
    result = text
    for pattern in SECRET_PATTERNS:
        result = pattern.sub(r"\1***", result)
    return result


def safe_filename(value: str | None, fallback: str = "untitled", max_len: int = 80) -> str:
    if not value:
        return fallback
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]+', "-", value).strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        cleaned = fallback
    return cleaned[:max_len]
