"""
API 路由分组模块
"""

from .wecom import wecom_router
from .craft import craft_router
from .binding import binding_router
from .admin import admin_router, metrics_router

__all__ = [
    "wecom_router",
    "craft_router",
    "binding_router",
    "admin_router",
    "metrics_router",
]
