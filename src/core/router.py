"""消息路由。"""
from __future__ import annotations

import logging
from typing import List

from src.core.config import env_destinations, load_route_config
from src.core.models import TargetConfig
from src.models.chat_record import UnifiedMessage
from src.services.binding_service import BindingService
from src.services.database import DatabaseService

logger = logging.getLogger(__name__)


class MessageRouter:
    """按数据库、配置文件、环境变量和兼容 Craft 绑定解析目标。"""

    def resolve_targets(self, msg: UnifiedMessage) -> List[TargetConfig]:
        targets: List[TargetConfig] = []
        targets.extend(self._database_targets(msg))
        targets.extend(self._config_file_targets(msg))
        targets.extend(self._env_targets(msg))
        targets.extend(self._legacy_craft_targets(msg))
        return self._dedupe(targets)

    def _legacy_craft_targets(self, msg: UnifiedMessage) -> List[TargetConfig]:
        if msg.source != "wecom":
            return []
        binding = BindingService.get_binding_by_openid(msg.from_user)
        if not binding:
            return []
        if DatabaseService.get_destination_record(f"craft:{binding.wecom_openid}"):
            return []
        return [
            TargetConfig(
                id=f"craft:{binding.wecom_openid}",
                name=binding.display_name or binding.wecom_openid,
                target_type="craft",
                config={
                    "link_id": binding.craft_link_id,
                    "document_id": binding.craft_document_id,
                    "token": binding.craft_token,
                },
                route_id="legacy-binding",
            )
        ]

    def _database_targets(self, msg: UnifiedMessage) -> List[TargetConfig]:
        targets: List[TargetConfig] = []
        for route in DatabaseService.find_routes_for_message(msg):
            destination = DatabaseService.get_destination(route["destination_id"])
            if destination:
                destination.route_id = str(route["id"])
                if route.get("template"):
                    destination.config["template"] = route["template"]
                targets.append(destination)
        return targets

    def _config_file_targets(self, msg: UnifiedMessage) -> List[TargetConfig]:
        data = load_route_config()
        destination_map = {
            item["id"]: item
            for item in data.get("destinations", [])
            if item.get("id") and item.get("target_type")
        }
        targets: List[TargetConfig] = []
        for route in data.get("routes", []):
            if not self._matches(msg, route.get("match", {})):
                continue
            destination_id = route.get("destination_id") or route.get("destination")
            destination = destination_map.get(destination_id)
            if not destination:
                logger.warning(f"[Router] 路由目标不存在: {destination_id}")
                continue
            targets.append(
                TargetConfig(
                    id=destination["id"],
                    name=destination.get("name", destination["id"]),
                    target_type=destination["target_type"],
                    config=destination.get("config", {}),
                    route_id=route.get("id") or route.get("name"),
                )
            )
        return targets

    def _env_targets(self, msg: UnifiedMessage) -> List[TargetConfig]:
        return [
            TargetConfig(
                id=item["id"],
                name=item["name"],
                target_type=item["target_type"],
                config=item["config"],
                route_id="env",
            )
            for item in env_destinations()
        ]

    def _matches(self, msg: UnifiedMessage, match: dict) -> bool:
        if match.get("source") and match["source"] != msg.source:
            return False
        if match.get("from_user") and match["from_user"] != msg.from_user:
            return False
        if match.get("chat_id") and match["chat_id"] != msg.chat_id:
            return False
        if match.get("msg_type") and match["msg_type"] != msg.msg_type:
            return False
        if match.get("keyword") and match["keyword"] not in (msg.content or ""):
            return False
        return True

    def _dedupe(self, targets: List[TargetConfig]) -> List[TargetConfig]:
        seen = set()
        result: List[TargetConfig] = []
        for target in targets:
            if target.id in seen:
                continue
            seen.add(target.id)
            result.append(target)
        return result


_router: MessageRouter | None = None


def get_router() -> MessageRouter:
    global _router
    if _router is None:
        _router = MessageRouter()
    return _router
