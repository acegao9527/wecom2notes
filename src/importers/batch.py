"""从 CSV、Markdown、HTML 等文件导入历史消息。"""
from __future__ import annotations

import csv
import hashlib
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, List

from src.models.chat_record import UnifiedMessage


class _HTMLTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: List[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return "\n".join(self.parts)


def load_messages(path: str, source: str = "import") -> List[UnifiedMessage]:
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return list(_from_csv(file_path, source))
    if suffix in {".md", ".markdown", ".txt"}:
        return [_from_text(file_path, source, "markdown")]
    if suffix in {".html", ".htm"}:
        parser = _HTMLTextParser()
        parser.feed(file_path.read_text(encoding="utf-8"))
        return [_message(file_path, source, parser.text(), "html")]
    return [_from_text(file_path, source, "file")]


def _from_csv(path: Path, source: str) -> Iterable[UnifiedMessage]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            content = row.get("content") or row.get("message") or row.get("text") or ""
            sender = row.get("from_user") or row.get("sender") or "import"
            msg_id = row.get("msg_id") or _stable_id(path, content + sender)
            yield UnifiedMessage(
                msg_id=msg_id,
                source=source,
                msg_type=row.get("msg_type") or "text",
                content=content,
                from_user=sender,
                create_time=int(row.get("create_time") or time.time()),
                chat_id=row.get("chat_id"),
                raw_data=row,
            )


def _from_text(path: Path, source: str, msg_type: str) -> UnifiedMessage:
    return _message(path, source, path.read_text(encoding="utf-8"), msg_type)


def _message(path: Path, source: str, content: str, msg_type: str) -> UnifiedMessage:
    return UnifiedMessage(
        msg_id=_stable_id(path, content),
        source=source,
        msg_type=msg_type,
        content=content,
        from_user="import",
        create_time=int(path.stat().st_mtime),
        raw_data={"path": str(path)},
    )


def _stable_id(path: Path, content: str) -> str:
    digest = hashlib.sha256(f"{path}:{content}".encode("utf-8")).hexdigest()[:16]
    return f"import-{digest}"
