"""企业微信消息源连接器。"""
from __future__ import annotations

import asyncio
from typing import List

from src.core.interfaces import SourceConnector
from src.models.chat_record import UnifiedMessage
from src.services.wecom import WeComService, parse_wecom_message


class WeComArchiveSource(SourceConnector):
    async def poll(self) -> List[UnifiedMessage]:
        raw_messages = await asyncio.to_thread(WeComService.fetch_messages, limit=100, timeout=20)
        messages: List[UnifiedMessage] = []
        for raw in raw_messages:
            msg = parse_wecom_message(raw)
            if msg:
                messages.append(msg)
        return messages
