"""测试和示例用消息源。"""
from __future__ import annotations

import time
from typing import List

from src.core.interfaces import SourceConnector
from src.models.chat_record import UnifiedMessage


class MockSource(SourceConnector):
    def __init__(self, messages: List[UnifiedMessage] | None = None):
        self.messages = messages or [
            UnifiedMessage(
                msg_id="mock-1",
                source="mock",
                msg_type="text",
                content="hello from mock source",
                from_user="mock-user",
                create_time=int(time.time()),
                raw_data={},
            )
        ]

    async def poll(self) -> List[UnifiedMessage]:
        return self.messages
