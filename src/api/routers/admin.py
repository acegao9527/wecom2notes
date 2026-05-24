"""管理接口：目标、路由、投递状态、重放与 metrics。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from src.core.delivery import deliver_message
from src.services.database import DatabaseService
from src.targets import list_target_types

admin_router = APIRouter(prefix="/admin", tags=["Admin"])
metrics_router = APIRouter(tags=["Metrics"])


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


@admin_router.get("/target-types")
async def target_types():
    return {"items": list_target_types()}


@admin_router.get("/destinations")
async def list_destinations():
    return {"items": DatabaseService.list_destinations()}


@admin_router.post("/destinations")
async def upsert_destination(payload: DestinationPayload):
    destination = DatabaseService.upsert_destination(
        payload.id,
        payload.name,
        payload.target_type,
        payload.config,
        payload.is_enabled,
    )
    return {"status": "success", "item": destination.__dict__}


@admin_router.get("/routes")
async def list_routes():
    return {"items": DatabaseService.list_routes()}


@admin_router.post("/routes")
async def create_route(payload: RoutePayload):
    route_id = DatabaseService.create_route(payload.model_dump())
    return {"status": "success", "id": route_id}


@admin_router.get("/deliveries")
async def list_deliveries(status: str | None = None, limit: int = 100):
    return {"items": DatabaseService.list_deliveries(status=status, limit=limit)}


@admin_router.post("/replay")
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
