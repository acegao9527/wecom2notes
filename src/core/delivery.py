"""消息投递编排。"""
from __future__ import annotations

import logging
from typing import List

from src.core.models import DeliveryResult
from src.core.router import get_router
from src.models.chat_record import UnifiedMessage
from src.services.database import DatabaseService
from src.targets import get_target_adapter

logger = logging.getLogger(__name__)


async def deliver_message(msg: UnifiedMessage, force: bool = False) -> List[DeliveryResult]:
    targets = get_router().resolve_targets(msg)
    if not targets:
        logger.warning(f"[Delivery] 没有匹配目标: source={msg.source}, msgid={msg.msg_id}, from={msg.from_user}")
        return []

    results: List[DeliveryResult] = []
    for target in targets:
        if not force and DatabaseService.delivery_is_done(msg.source, msg.msg_id, target.id):
            results.append(DeliveryResult(True, "delivered", target.id, metadata={"deduped": True}))
            continue
        DatabaseService.record_delivery(
            msg.source,
            msg.msg_id,
            target.id,
            target.target_type,
            "pending",
            route_id=target.route_id,
        )
        try:
            adapter = get_target_adapter(target.target_type)
            result = await adapter.deliver(msg, target)
        except Exception as e:
            logger.error(f"[Delivery] 投递异常: target={target.id}, msgid={msg.msg_id}, error={e}", exc_info=True)
            result = DeliveryResult(False, "failed", target.id, error=str(e))
        DatabaseService.record_delivery(
            msg.source,
            msg.msg_id,
            target.id,
            target.target_type,
            result.status,
            route_id=target.route_id,
            error=result.error,
            external_id=result.external_id,
            metadata=result.metadata,
        )
        results.append(result)
    return results
