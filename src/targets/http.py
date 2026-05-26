"""HTTP 回调目标适配器。"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from src.core.interfaces import TargetAdapter
from src.core.models import DeliveryResult, TargetConfig
from src.models.chat_record import UnifiedMessage


_DELIVERY_METHODS = {"POST", "PUT", "PATCH", "GET"}
_VERIFY_METHODS = {"GET", "HEAD", "POST"}


def _model_to_dict(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _valid_http_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _headers(config: dict[str, Any]) -> dict[str, str]:
    raw_headers = config.get("headers") or {}
    if not isinstance(raw_headers, dict):
        raise ValueError("headers must be an object")
    headers = {str(key): str(value) for key, value in raw_headers.items()}
    if config.get("bearer_token"):
        headers.setdefault("Authorization", f"Bearer {config['bearer_token']}")
    if not any(key.lower() == "content-type" for key in headers):
        headers["Content-Type"] = "application/json"
    return headers


def _success_statuses(config: dict[str, Any]) -> set[int]:
    configured = config.get("success_statuses")
    if configured:
        return {int(status) for status in configured}
    return set(range(200, 300))


def _payload(msg: UnifiedMessage, target: TargetConfig) -> dict[str, Any]:
    return {
        "event": "wecom2notes.message",
        "target_id": target.id,
        "route_id": target.route_id,
        "message": _model_to_dict(msg),
    }


class HttpTarget(TargetAdapter):
    """把统一消息投递到 HTTP 接口。"""

    target_type = "http"

    async def verify(self, target: TargetConfig) -> DeliveryResult:
        config = target.config
        url = config.get("url")
        if not _valid_http_url(url):
            return DeliveryResult(False, "failed", target.id, "url is required and must be http(s)")
        method = str(config.get("method", "POST")).upper()
        if method not in _DELIVERY_METHODS:
            return DeliveryResult(False, "failed", target.id, f"unsupported method: {method}")
        verify_url = config.get("verify_url")
        if not verify_url:
            return DeliveryResult(True, "verified", target.id, metadata={"method": method})
        if not _valid_http_url(verify_url):
            return DeliveryResult(False, "failed", target.id, "verify_url must be http(s)")
        verify_method = str(config.get("verify_method", "GET")).upper()
        if verify_method not in _VERIFY_METHODS:
            return DeliveryResult(False, "failed", target.id, f"unsupported verify_method: {verify_method}")
        try:
            async with httpx.AsyncClient(timeout=float(config.get("timeout", 30))) as client:
                response = await client.request(verify_method, verify_url, headers=_headers(config))
        except Exception as exc:
            return DeliveryResult(False, "failed", target.id, str(exc))
        success = response.status_code in _success_statuses(config)
        return DeliveryResult(
            success,
            "verified" if success else "failed",
            target.id,
            None if success else response.text[:300],
            metadata={"status_code": response.status_code, "method": verify_method},
        )

    async def deliver(self, msg: UnifiedMessage, target: TargetConfig) -> DeliveryResult:
        config = target.config
        url = config.get("url")
        if not _valid_http_url(url):
            return DeliveryResult(False, "failed", target.id, "url is required and must be http(s)")
        method = str(config.get("method", "POST")).upper()
        if method not in _DELIVERY_METHODS:
            return DeliveryResult(False, "failed", target.id, f"unsupported method: {method}")

        payload = _payload(msg, target)
        if isinstance(config.get("extra"), dict):
            payload["extra"] = config["extra"]

        try:
            async with httpx.AsyncClient(timeout=float(config.get("timeout", 30))) as client:
                if method == "GET":
                    response = await client.get(
                        url,
                        headers=_headers(config),
                        params={
                            "source": msg.source,
                            "msg_id": msg.msg_id,
                            "msg_type": msg.msg_type,
                            "from_user": msg.from_user,
                        },
                    )
                else:
                    response = await client.request(method, url, headers=_headers(config), json=payload)
        except Exception as exc:
            return DeliveryResult(False, "failed", target.id, str(exc))

        success = response.status_code in _success_statuses(config)
        request_id = response.headers.get("x-request-id") or response.headers.get("x-correlation-id")
        return DeliveryResult(
            success,
            "delivered" if success else "failed",
            target.id,
            None if success else response.text[:300],
            external_id=request_id,
            metadata={
                "status_code": response.status_code,
                "method": method,
                "response_preview": response.text[:300],
            },
        )
