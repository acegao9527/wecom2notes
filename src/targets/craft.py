"""Craft 目标适配器。"""
from __future__ import annotations

from src.core.interfaces import TargetAdapter
from src.core.models import DeliveryResult, TargetConfig
from src.models.chat_record import UnifiedMessage
from src.services.binding_service import verify_craft_access
from src.services.craft import save_blocks_to_craft
from src.services.formatter import format_unified_message_as_craft_blocks


class CraftTarget(TargetAdapter):
    target_type = "craft"

    async def verify(self, target: TargetConfig) -> DeliveryResult:
        config = target.config
        ok, message = verify_craft_access(
            config.get("link_id") or config.get("craft_link_id"),
            config.get("document_id") or config.get("craft_document_id"),
            config.get("token") or config.get("craft_token"),
        )
        return DeliveryResult(ok, "verified" if ok else "failed", target.id, None if ok else message)

    async def deliver(self, msg: UnifiedMessage, target: TargetConfig) -> DeliveryResult:
        config = target.config
        blocks = format_unified_message_as_craft_blocks(msg)
        success = await save_blocks_to_craft(
            blocks,
            link_id=config.get("link_id") or config.get("craft_link_id"),
            document_id=config.get("document_id") or config.get("craft_document_id"),
            document_token=config.get("token") or config.get("craft_token"),
        )
        return DeliveryResult(
            success=success,
            status="delivered" if success else "failed",
            target_id=target.id,
            error=None if success else "Craft API returned failure",
            metadata={"blocks": len(blocks)},
        )
