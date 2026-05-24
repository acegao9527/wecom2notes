"""WebDAV Markdown 目标。"""
from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath

import httpx

from src.core.interfaces import TargetAdapter
from src.core.models import DeliveryResult, TargetConfig
from src.core.sanitize import safe_filename
from src.models.chat_record import UnifiedMessage


class WebDAVTarget(TargetAdapter):
    target_type = "webdav"

    async def verify(self, target: TargetConfig) -> DeliveryResult:
        if not target.config.get("base_url"):
            return DeliveryResult(False, "failed", target.id, "base_url is required")
        return DeliveryResult(True, "verified", target.id)

    async def deliver(self, msg: UnifiedMessage, target: TargetConfig) -> DeliveryResult:
        config = target.config
        base_url = config.get("base_url", "").rstrip("/")
        if not base_url:
            return DeliveryResult(False, "failed", target.id, "base_url is required")
        dt = datetime.fromtimestamp(int(msg.create_time or 0))
        root_path = PurePosixPath(config.get("root_path", "WeCom"))
        filename = f"{dt.strftime('%Y-%m-%d')}.md"
        remote_path = root_path / filename
        url = f"{base_url}/{remote_path.as_posix()}"
        auth = None
        if config.get("username"):
            auth = (config.get("username"), config.get("password", ""))
        entry = (
            f"\n## {dt.strftime('%Y-%m-%d %H:%M:%S')} - {safe_filename(msg.from_user)}\n\n"
            f"<!-- msg_id: {msg.msg_id} -->\n"
            f"{msg.content}\n"
        )
        async with httpx.AsyncClient(timeout=30, auth=auth) as client:
            await self._ensure_collections(client, base_url, remote_path.parent)
            response = await client.get(url)
            current = response.text if response.status_code == 200 else ""
            if f"msg_id: {msg.msg_id}" in current:
                return DeliveryResult(True, "delivered", target.id, external_id=url, metadata={"deduped": True})
            put = await client.put(url, content=(current + entry).encode("utf-8"))
        success = put.status_code in (200, 201, 204)
        return DeliveryResult(
            success,
            "delivered" if success else "failed",
            target.id,
            None if success else put.text[:300],
            external_id=url if success else None,
            metadata={"status_code": put.status_code},
        )

    async def _ensure_collections(self, client: httpx.AsyncClient, base_url: str, path: PurePosixPath) -> None:
        current = PurePosixPath("")
        for part in path.parts:
            current = current / part
            await client.request("MKCOL", f"{base_url}/{current.as_posix()}")
