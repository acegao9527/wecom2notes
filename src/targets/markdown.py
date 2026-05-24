"""Markdown、Obsidian、Logseq 和 Git 文件目标。"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict, List

from src.core.interfaces import TargetAdapter
from src.core.models import DeliveryResult, TargetConfig
from src.core.sanitize import safe_filename
from src.models.chat_record import AttachmentInfo, UnifiedMessage

_FILE_LOCKS: Dict[str, Lock] = {}


def _lock_for(path: Path) -> Lock:
    key = str(path.resolve())
    if key not in _FILE_LOCKS:
        _FILE_LOCKS[key] = Lock()
    return _FILE_LOCKS[key]


def _message_datetime(msg: UnifiedMessage) -> datetime:
    try:
        return datetime.fromtimestamp(int(msg.create_time))
    except Exception:
        return datetime.now()


class MarkdownFilesystemTarget(TargetAdapter):
    target_type = "markdown"

    async def verify(self, target: TargetConfig) -> DeliveryResult:
        root = Path(target.config.get("root_path", "")).expanduser()
        if not root:
            return DeliveryResult(False, "failed", target.id, "root_path is required")
        root.mkdir(parents=True, exist_ok=True)
        return DeliveryResult(root.exists(), "verified", target.id, None if root.exists() else "root_path not found")

    async def deliver(self, msg: UnifiedMessage, target: TargetConfig) -> DeliveryResult:
        config = target.config
        root = Path(config.get("root_path", "")).expanduser()
        if not root:
            return DeliveryResult(False, "failed", target.id, "root_path is required")
        root.mkdir(parents=True, exist_ok=True)

        note_path = self._note_path(root, msg, config)
        note_path.parent.mkdir(parents=True, exist_ok=True)
        attachments = self._copy_attachments(root, msg, config)
        entry = self._render_entry(msg, config, attachments)

        def write_entry() -> None:
            lock = _lock_for(note_path)
            with lock:
                current = note_path.read_text(encoding="utf-8") if note_path.exists() else ""
                if f"msg_id: {msg.msg_id}" in current:
                    return
                new_content = self._ensure_frontmatter(current, msg) + entry
                fd, tmp_name = tempfile.mkstemp(prefix=note_path.name, dir=str(note_path.parent))
                with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                    tmp.write(new_content)
                os.replace(tmp_name, note_path)

        await asyncio.to_thread(write_entry)
        return DeliveryResult(
            True,
            "delivered",
            target.id,
            external_id=str(note_path),
            metadata={"path": str(note_path), "attachments": len(attachments)},
        )

    def _note_path(self, root: Path, msg: UnifiedMessage, config: Dict) -> Path:
        mode = config.get("mode", "daily")
        base_dir = Path(config.get("base_dir", "WeCom"))
        dt = _message_datetime(msg)
        if mode == "sender":
            filename = f"{safe_filename(msg.sender_name or msg.from_user)}.md"
            return root / base_dir / "People" / filename
        if mode == "chat":
            filename = f"{safe_filename(msg.chat_id or msg.from_user)}.md"
            return root / base_dir / "Chats" / filename
        filename_template = config.get("filename_template", "{date}.md")
        filename = filename_template.format(date=dt.strftime("%Y-%m-%d"), sender=safe_filename(msg.from_user))
        return root / base_dir / filename

    def _copy_attachments(self, root: Path, msg: UnifiedMessage, config: Dict) -> List[AttachmentInfo]:
        dt = _message_datetime(msg)
        asset_dir = root / Path(config.get("asset_dir", "WeCom/assets")) / dt.strftime("%Y/%m")
        asset_dir.mkdir(parents=True, exist_ok=True)
        attachments = list(msg.attachments)
        if not attachments and msg.msg_type in {"image", "file", "video", "voice"} and msg.content and os.path.exists(msg.content):
            attachments.append(AttachmentInfo(file_name=os.path.basename(msg.content), local_path=msg.content))

        copied: List[AttachmentInfo] = []
        for attachment in attachments:
            if not attachment.local_path or not os.path.exists(attachment.local_path):
                copied.append(attachment)
                continue
            src = Path(attachment.local_path)
            filename = safe_filename(attachment.file_name or src.name)
            dest = asset_dir / filename
            counter = 1
            while dest.exists() and dest.resolve() != src.resolve():
                dest = asset_dir / f"{dest.stem}-{counter}{dest.suffix}"
                counter += 1
            if dest.resolve() != src.resolve():
                shutil.copy2(src, dest)
            copied.append(
                AttachmentInfo(
                    file_name=filename,
                    local_path=str(dest),
                    content_type=attachment.content_type,
                    size=dest.stat().st_size if dest.exists() else attachment.size,
                    sha256=attachment.sha256,
                    url=attachment.url,
                )
            )
        return copied

    def _ensure_frontmatter(self, current: str, msg: UnifiedMessage) -> str:
        if current:
            return current if current.endswith("\n") else current + "\n"
        return (
            "---\n"
            f"source: {msg.source}\n"
            "type: message-archive\n"
            "---\n\n"
        )

    def _render_entry(self, msg: UnifiedMessage, config: Dict, attachments: List[AttachmentInfo]) -> str:
        dt = _message_datetime(msg).strftime("%Y-%m-%d %H:%M:%S")
        sender = msg.sender_name or msg.from_user
        lines = [
            "\n",
            f"## {dt} - {sender}\n",
            "\n",
            f"<!-- msg_id: {msg.msg_id} -->\n",
            f"- source: {msg.source}\n",
            f"- msg_type: {msg.msg_type}\n",
            f"- sender: {msg.from_user}\n",
        ]
        if msg.chat_id:
            lines.append(f"- chat_id: {msg.chat_id}\n")
        lines.extend(["\n", self._content_markdown(msg), "\n"])
        for attachment in attachments:
            lines.append(self._attachment_link(attachment, config))
        return "".join(lines)

    def _content_markdown(self, msg: UnifiedMessage) -> str:
        if msg.msg_type == "link" and msg.content.startswith("http"):
            return f"[{msg.content}]({msg.content})\n"
        if msg.msg_type in {"image", "file", "video", "voice"} and os.path.exists(msg.content or ""):
            return ""
        return f"{msg.content}\n"

    def _attachment_link(self, attachment: AttachmentInfo, config: Dict) -> str:
        if attachment.url:
            return f"[{attachment.file_name or attachment.url}]({attachment.url})\n"
        if not attachment.local_path:
            return ""
        path = attachment.local_path
        name = attachment.file_name or os.path.basename(path)
        link_style = config.get("link_style", "markdown")
        if link_style == "wiki":
            return f"![[{name}]]\n"
        if (attachment.content_type or "").startswith("image") or Path(path).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
            return f"![{name}]({path})\n"
        return f"[{name}]({path})\n"


class ObsidianTarget(MarkdownFilesystemTarget):
    target_type = "obsidian"

    async def deliver(self, msg: UnifiedMessage, target: TargetConfig) -> DeliveryResult:
        target.config.setdefault("link_style", "wiki")
        return await super().deliver(msg, target)


class LogseqTarget(MarkdownFilesystemTarget):
    target_type = "logseq"

    def _render_entry(self, msg: UnifiedMessage, config: Dict, attachments: List[AttachmentInfo]) -> str:
        dt = _message_datetime(msg).strftime("%H:%M:%S")
        sender = msg.sender_name or msg.from_user
        lines = [
            f"\n- {dt} **{sender}** ({msg.msg_type})\n",
            f"  id:: {msg.msg_id}\n",
            f"  source:: {msg.source}\n",
        ]
        if msg.content:
            lines.append(f"  {msg.content}\n")
        for attachment in attachments:
            lines.append(f"  {self._attachment_link(attachment, config).strip()}\n")
        return "".join(lines)


class GitMarkdownTarget(MarkdownFilesystemTarget):
    target_type = "git"

    async def deliver(self, msg: UnifiedMessage, target: TargetConfig) -> DeliveryResult:
        result = await super().deliver(msg, target)
        if not result.success or not target.config.get("auto_commit", False):
            return result
        repo_path = Path(target.config.get("repo_path") or target.config.get("root_path", "")).expanduser()
        commit_message = target.config.get("commit_message", f"archive message {msg.msg_id}")

        def run_git() -> None:
            subprocess.run(["git", "add", "."], cwd=repo_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "commit", "-m", commit_message], cwd=repo_path, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        await asyncio.to_thread(run_git)
        result.metadata["git_commit_attempted"] = True
        return result
