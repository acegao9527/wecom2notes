"""Notion 目标适配器。"""
from __future__ import annotations

import httpx

from src.core.interfaces import TargetAdapter
from src.core.models import DeliveryResult, TargetConfig
from src.models.chat_record import UnifiedMessage


class NotionTarget(TargetAdapter):
    target_type = "notion"

    async def verify(self, target: TargetConfig) -> DeliveryResult:
        token = target.config.get("token")
        if not token:
            return DeliveryResult(False, "failed", target.id, "token is required")
        return DeliveryResult(True, "verified", target.id)

    async def deliver(self, msg: UnifiedMessage, target: TargetConfig) -> DeliveryResult:
        config = target.config
        token = config.get("token")
        if not token:
            return DeliveryResult(False, "failed", target.id, "token is required")
        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": config.get("notion_version", "2022-06-28"),
            "Content-Type": "application/json",
        }
        block = {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": f"[{msg.from_user}] {msg.content}"[:1900]},
                    }
                ]
            },
        }
        async with httpx.AsyncClient(timeout=30) as client:
            if config.get("database_id"):
                payload = {
                    "parent": {"database_id": config["database_id"]},
                    "properties": {
                        config.get("title_property", "Name"): {
                            "title": [{"text": {"content": f"{msg.source}:{msg.msg_id}"}}]
                        }
                    },
                    "children": [block],
                }
                response = await client.post("https://api.notion.com/v1/pages", headers=headers, json=payload)
            else:
                page_id = config.get("page_id")
                if not page_id:
                    return DeliveryResult(False, "failed", target.id, "page_id or database_id is required")
                response = await client.patch(
                    f"https://api.notion.com/v1/blocks/{page_id}/children",
                    headers=headers,
                    json={"children": [block]},
                )
        success = response.status_code in (200, 201)
        return DeliveryResult(
            success,
            "delivered" if success else "failed",
            target.id,
            None if success else response.text[:300],
            metadata={"status_code": response.status_code},
        )
