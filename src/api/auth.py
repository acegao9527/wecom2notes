"""简单管理端鉴权依赖。"""
from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException, Request, status


def admin_auth_enabled() -> bool:
    """是否启用管理端 token 鉴权。"""
    return bool(os.getenv("ADMIN_TOKEN"))


async def require_admin(
    request: Request,
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
) -> None:
    """校验管理端请求。

    未配置 ADMIN_TOKEN 时保持本地开发友好；配置后支持 Bearer、X-Admin-Token
    和 admin_token cookie 三种方式。
    """
    expected = os.getenv("ADMIN_TOKEN")
    if not expected:
        return

    supplied = x_admin_token or request.cookies.get("admin_token")
    if not supplied and authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer":
            supplied = value

    if supplied and hmac.compare_digest(supplied, expected):
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="admin token required",
        headers={"WWW-Authenticate": "Bearer"},
    )
