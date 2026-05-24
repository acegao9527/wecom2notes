"""核心抽象模型。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class TargetConfig:
    """投递目标配置。"""

    id: str
    name: str
    target_type: str
    config: Dict[str, Any] = field(default_factory=dict)
    route_id: Optional[str] = None


@dataclass
class DeliveryResult:
    """目标适配器投递结果。"""

    success: bool
    status: str
    target_id: str
    error: Optional[str] = None
    external_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
