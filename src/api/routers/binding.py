"""
绑定管理路由
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.auth import require_admin
from src.models.binding import BindingCreate, BindingResponse, UserBinding
from src.services.binding_service import BindingService, verify_craft_access

logger = logging.getLogger(__name__)

binding_router = APIRouter(prefix="/bindings", tags=["Bindings"], dependencies=[Depends(require_admin)])


class BindingEnabledPayload(BaseModel):
    is_enabled: bool


class CraftVerifyPayload(BaseModel):
    link_id: str
    document_id: str
    token: str | None = None


@binding_router.get("", response_model=list[BindingResponse])
async def list_bindings():
    """获取所有用户绑定"""
    bindings = BindingService.get_all_bindings()
    return bindings


@binding_router.get("/{openid}", response_model=BindingResponse)
async def get_binding(openid: str):
    """根据企微 OpenID 获取绑定"""
    binding = BindingService.get_binding_by_openid(openid, enabled_only=False)
    if not binding:
        raise HTTPException(status_code=404, detail="绑定不存在")
    return binding


@binding_router.post("", response_model=BindingResponse)
async def create_binding(create: BindingCreate):
    """创建或更新用户绑定"""
    # 验证 Craft 访问权限
    if create.craft_token:
        ok, msg = verify_craft_access(create.craft_link_id, create.craft_document_id, create.craft_token)
    else:
        ok, msg = verify_craft_access(create.craft_link_id, create.craft_document_id)

    if not ok:
        raise HTTPException(status_code=400, detail=f"Craft 验证失败: {msg}")

    binding = BindingService.create_binding(create)
    if not binding:
        raise HTTPException(status_code=500, detail="创建绑定失败")
    return binding


@binding_router.put("/{openid}", response_model=BindingResponse)
async def update_binding(openid: str, create: BindingCreate):
    """更新用户绑定"""
    create.wecom_openid = openid
    binding = BindingService.create_binding(create)
    if not binding:
        raise HTTPException(status_code=500, detail="更新绑定失败")
    return binding


@binding_router.delete("/{openid}")
async def delete_binding(openid: str):
    """删除用户绑定"""
    success = BindingService.delete_binding(openid)
    if not success:
        raise HTTPException(status_code=404, detail="绑定不存在或删除失败")
    return {"status": "success", "message": "绑定已删除"}


@binding_router.patch("/{openid}/enabled")
async def set_binding_enabled(openid: str, payload: BindingEnabledPayload):
    """启用或停用用户绑定。"""
    success = BindingService.set_binding_enabled(openid, payload.is_enabled)
    if not success:
        raise HTTPException(status_code=404, detail="绑定不存在或更新失败")
    return {"status": "success", "is_enabled": payload.is_enabled}


@binding_router.post("/verify")
async def verify_craft(payload: CraftVerifyPayload):
    """验证 Craft 链接和文档是否可访问"""
    ok, msg = verify_craft_access(payload.link_id, payload.document_id, payload.token)
    if ok:
        return {"status": "success", "message": f"验证成功: {msg}"}
    else:
        raise HTTPException(status_code=400, detail=msg)
