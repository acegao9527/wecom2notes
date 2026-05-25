"""管理接口：目标、路由、投递状态、重放与 metrics。"""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from src.api.auth import admin_auth_enabled, require_admin
from src.core.delivery import deliver_message
from src.core.models import TargetConfig
from src.core.router import get_router
from src.models.chat_record import UnifiedMessage
from src.services.database import DatabaseService
from src.targets import get_target_adapter, list_target_types

admin_router = APIRouter(prefix="/admin", tags=["Admin"])
metrics_router = APIRouter(tags=["Metrics"])
ADMIN_DEPS = [Depends(require_admin)]


class DestinationPayload(BaseModel):
    id: str
    name: str
    target_type: str
    config: dict = Field(default_factory=dict)
    is_enabled: bool = True


class RoutePayload(BaseModel):
    name: str | None = None
    source: str = "wecom"
    from_user: str | None = None
    chat_id: str | None = None
    msg_type: str | None = None
    keyword: str | None = None
    destination_id: str
    template: str | None = None
    is_enabled: bool = True


class ReplayPayload(BaseModel):
    source: str
    msg_id: str
    force: bool = True


class EnabledPayload(BaseModel):
    is_enabled: bool


class RouteTestPayload(BaseModel):
    msg_id: str = "preview"
    source: str = "wecom"
    msg_type: str = "text"
    content: str = ""
    from_user: str = "preview-user"
    chat_id: str | None = None
    to_user: str | None = None
    sender_name: str | None = None
    create_time: int = 0


def _clean_route_payload(payload: RoutePayload) -> dict[str, Any]:
    data = payload.model_dump()
    for key in ("name", "from_user", "chat_id", "msg_type", "keyword", "template"):
        if data.get(key) == "":
            data[key] = None
    return data


def _target_from_record(record: dict[str, Any]) -> TargetConfig:
    return TargetConfig(
        id=record["id"],
        name=record["name"],
        target_type=record["target_type"],
        config=record.get("config", {}),
    )


@admin_router.get("/session")
async def admin_session():
    return {"auth_required": admin_auth_enabled()}


@admin_router.get("/overview", dependencies=ADMIN_DEPS)
async def overview():
    seq = DatabaseService.get_last_seq()
    try:
        from src.services.wecom import get_last_seq_from_file

        seq = get_last_seq_from_file()
    except Exception:
        pass
    return {
        "metrics": DatabaseService.metrics(),
        "source_cursors": DatabaseService.list_source_cursors(),
        "recent_failed_deliveries": DatabaseService.list_deliveries(status="failed", limit=5),
        "recent_messages": DatabaseService.list_messages(limit=5)["items"],
        "target_types": list_target_types(),
        "runtime": {
            "admin_auth_enabled": admin_auth_enabled(),
            "wecom_disable_sdk": os.getenv("WECOM_DISABLE_SDK", "").lower() == "true",
            "wecom_seq": seq,
            "sqlite_db_path": os.getenv("SQLITE_DB_PATH", "data/wecom2notes.db"),
            "image_save_dir": os.getenv("IMAGE_SAVE_DIR", "./images"),
        },
    }


@admin_router.get("/target-types", dependencies=ADMIN_DEPS)
async def target_types():
    return {"items": list_target_types()}


@admin_router.get("/destinations", dependencies=ADMIN_DEPS)
async def list_destinations():
    return {"items": DatabaseService.list_destinations()}


@admin_router.post("/destinations", dependencies=ADMIN_DEPS)
async def upsert_destination(payload: DestinationPayload):
    if payload.target_type not in list_target_types():
        raise HTTPException(status_code=400, detail=f"unsupported target type: {payload.target_type}")
    destination = DatabaseService.upsert_destination(
        payload.id,
        payload.name,
        payload.target_type,
        payload.config,
        payload.is_enabled,
    )
    return {"status": "success", "item": destination.__dict__}


@admin_router.put("/destinations/{destination_id}", dependencies=ADMIN_DEPS)
async def update_destination(destination_id: str, payload: DestinationPayload):
    payload.id = destination_id
    return await upsert_destination(payload)


@admin_router.patch("/destinations/{destination_id}/enabled", dependencies=ADMIN_DEPS)
async def set_destination_enabled(destination_id: str, payload: EnabledPayload):
    if not DatabaseService.set_destination_enabled(destination_id, payload.is_enabled):
        raise HTTPException(status_code=404, detail="destination not found")
    return {"status": "success", "is_enabled": payload.is_enabled}


@admin_router.delete("/destinations/{destination_id}", dependencies=ADMIN_DEPS)
async def delete_destination(destination_id: str):
    if not DatabaseService.delete_destination(destination_id):
        raise HTTPException(status_code=404, detail="destination not found")
    return {"status": "success"}


@admin_router.post("/destinations/{destination_id}/verify", dependencies=ADMIN_DEPS)
async def verify_destination(destination_id: str):
    record = DatabaseService.get_destination_record(destination_id)
    if not record:
        raise HTTPException(status_code=404, detail="destination not found")
    try:
        result = await get_target_adapter(record["target_type"]).verify(_target_from_record(record))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"status": "success" if result.success else "failed", "result": result.__dict__}


@admin_router.get("/routes", dependencies=ADMIN_DEPS)
async def list_routes():
    return {"items": DatabaseService.list_routes()}


@admin_router.post("/routes", dependencies=ADMIN_DEPS)
async def create_route(payload: RoutePayload):
    route_id = DatabaseService.create_route(_clean_route_payload(payload))
    return {"status": "success", "id": route_id}


@admin_router.put("/routes/{route_id}", dependencies=ADMIN_DEPS)
async def update_route(route_id: int, payload: RoutePayload):
    if not DatabaseService.update_route(route_id, _clean_route_payload(payload)):
        raise HTTPException(status_code=404, detail="route not found")
    return {"status": "success", "id": route_id}


@admin_router.patch("/routes/{route_id}/enabled", dependencies=ADMIN_DEPS)
async def set_route_enabled(route_id: int, payload: EnabledPayload):
    if not DatabaseService.set_route_enabled(route_id, payload.is_enabled):
        raise HTTPException(status_code=404, detail="route not found")
    return {"status": "success", "is_enabled": payload.is_enabled}


@admin_router.delete("/routes/{route_id}", dependencies=ADMIN_DEPS)
async def delete_route(route_id: int):
    if not DatabaseService.delete_route(route_id):
        raise HTTPException(status_code=404, detail="route not found")
    return {"status": "success"}


@admin_router.post("/routes/test", dependencies=ADMIN_DEPS)
async def test_routes(payload: RouteTestPayload):
    msg = UnifiedMessage(
        msg_id=payload.msg_id,
        source=payload.source,
        msg_type=payload.msg_type,
        content=payload.content,
        from_user=payload.from_user,
        create_time=payload.create_time,
        raw_data={},
        chat_id=payload.chat_id,
        to_user=payload.to_user,
        sender_name=payload.sender_name,
    )
    targets = get_router().resolve_targets(msg)
    return {"items": [target.__dict__ for target in targets]}


@admin_router.get("/deliveries", dependencies=ADMIN_DEPS)
async def list_deliveries(status: str | None = None, limit: int = 100):
    return {"items": DatabaseService.list_deliveries(status=status, limit=limit)}


@admin_router.get("/messages", dependencies=ADMIN_DEPS)
async def list_messages(
    source: str | None = None,
    from_user: str | None = None,
    chat_id: str | None = None,
    msg_type: str | None = None,
    keyword: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    return DatabaseService.list_messages(
        source=source,
        from_user=from_user,
        chat_id=chat_id,
        msg_type=msg_type,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )


@admin_router.get("/messages/{source}/{msg_id}", dependencies=ADMIN_DEPS)
async def get_message_detail(source: str, msg_id: str):
    item = DatabaseService.get_message_detail(source, msg_id)
    if not item:
        raise HTTPException(status_code=404, detail="message not found")
    return item


@admin_router.post("/messages/{source}/{msg_id}/replay", dependencies=ADMIN_DEPS)
async def replay_message_by_path(source: str, msg_id: str, force: bool = True):
    return await replay_message(ReplayPayload(source=source, msg_id=msg_id, force=force))


@admin_router.post("/replay", dependencies=ADMIN_DEPS)
async def replay_message(payload: ReplayPayload):
    msg = DatabaseService.get_message(payload.source, payload.msg_id)
    if not msg:
        raise HTTPException(status_code=404, detail="message not found")
    results = await deliver_message(msg, force=payload.force)
    return {"status": "success", "results": [result.__dict__ for result in results]}


@metrics_router.get("/metrics")
async def metrics():
    data = DatabaseService.metrics()
    lines = []
    for key, value in data.items():
        lines.append(f"wecom2notes_{key} {value}")
    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@metrics_router.get("/health")
async def health():
    return {"status": "ok", "metrics": DatabaseService.metrics()}
