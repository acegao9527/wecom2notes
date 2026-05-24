"""Source 和 Target 的插件接口。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from src.core.models import DeliveryResult, TargetConfig
from src.models.chat_record import UnifiedMessage


class SourceConnector(ABC):
    """消息源连接器接口。"""

    @abstractmethod
    async def poll(self) -> List[UnifiedMessage]:
        """拉取并返回标准化消息。"""


class TargetAdapter(ABC):
    """笔记目标适配器接口。"""

    target_type: str

    @abstractmethod
    async def verify(self, target: TargetConfig) -> DeliveryResult:
        """验证目标配置是否可用。"""

    @abstractmethod
    async def deliver(self, msg: UnifiedMessage, target: TargetConfig) -> DeliveryResult:
        """投递消息到目标。"""
