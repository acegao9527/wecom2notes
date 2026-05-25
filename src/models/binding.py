from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class UserBinding(BaseModel):
    """用户绑定模型"""
    id: Optional[int] = None
    wecom_openid: str = Field(..., description="企微用户OpenID")
    craft_link_id: str = Field(..., description="Craft链接ID")
    craft_document_id: str = Field(..., description="Craft文档ID")
    craft_token: str = Field(..., description="Craft文档Token")
    display_name: Optional[str] = Field(None, description="显示名称")
    is_enabled: bool = Field(default=True, description="是否启用")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        extra = "ignore"


class BindingCreate(BaseModel):
    """创建绑定请求"""
    wecom_openid: str
    craft_link_id: str
    craft_document_id: str
    craft_token: Optional[str] = None
    display_name: Optional[str] = None
    is_enabled: bool = True


class BindingResponse(BaseModel):
    """绑定响应"""
    id: int
    wecom_openid: str
    craft_link_id: str
    craft_document_id: str
    display_name: Optional[str]
    is_enabled: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
