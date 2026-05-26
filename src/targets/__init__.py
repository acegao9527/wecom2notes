"""目标适配器注册表。"""
from __future__ import annotations

from typing import Dict

from src.core.interfaces import TargetAdapter
from src.targets.craft import CraftTarget
from src.targets.http import HttpTarget
from src.targets.markdown import GitMarkdownTarget, LogseqTarget, MarkdownFilesystemTarget, ObsidianTarget
from src.targets.notion import NotionTarget
from src.targets.webdav import WebDAVTarget


_ADAPTERS: Dict[str, TargetAdapter] = {
    "craft": CraftTarget(),
    "markdown": MarkdownFilesystemTarget(),
    "obsidian": ObsidianTarget(),
    "logseq": LogseqTarget(),
    "notion": NotionTarget(),
    "webdav": WebDAVTarget(),
    "git": GitMarkdownTarget(),
    "http": HttpTarget(),
}


def get_target_adapter(target_type: str) -> TargetAdapter:
    try:
        return _ADAPTERS[target_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported target type: {target_type}") from exc


def list_target_types() -> list[str]:
    return sorted(_ADAPTERS.keys())
