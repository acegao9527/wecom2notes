import logging
from src.models.chat_record import UnifiedMessage
from src.services.database import DatabaseService
from src.core.delivery import deliver_message

logger = logging.getLogger(__name__)

# RPA related functions moved to src/utils/reply_sender.py
# News logic moved to src/handlers/news.py
# Link/Image/Text logic moved to respective handlers

async def _send_rpa_notification(text: str):
    """
    Deprecated: Use src.utils.reply_sender.send_reply instead.
    Kept temporarily if imported elsewhere, but internal logic delegates to new system.
    """
    logger.warning("[Dispatcher] _send_rpa_notification 已废弃，当前构建未启用 RPA 回复。")

async def process_message(msg: UnifiedMessage):
    """
    核心消息处理分发器 (Dispatcher)

    流程：
    1. 落库 (Unified Storage) - 所有消息必须存档
    2. 分发给对应的 Handler 进行业务处理 (回复、同步Craft等)
    """
    # 1. 全局落库 (Audit Log)
    try:
        DatabaseService.save_unified_message(msg)
    except Exception as e:
        logger.error(f"[Dispatcher] DB Save failed: {e}")

    if await _handle_builtin_command(msg):
        return

    # 2. 按路由投递到所有笔记目标
    try:
        await deliver_message(msg)
    except Exception as e:
        logger.error(f"[Dispatcher] Delivery failed: msgid={msg.msg_id}, error={e}", exc_info=True)


async def _handle_builtin_command(msg: UnifiedMessage) -> bool:
    """兼容旧版企微文本绑定命令。"""
    content = msg.content or ""
    if msg.source != "wecom" or not content.startswith("绑定"):
        return False
    parts = content.split()
    if len(parts) < 4 or parts[0] != "绑定":
        return False

    from src.models.binding import BindingCreate
    from src.services.binding_service import BindingService

    create = BindingCreate(
        wecom_openid=msg.from_user,
        craft_link_id=parts[2],
        craft_document_id=parts[3],
        craft_token=parts[1],
        display_name=parts[4] if len(parts) > 4 else None,
    )
    binding = BindingService.create_binding(create)
    if binding:
        logger.info(f"[Dispatcher] 用户 {msg.from_user} 绑定成功")
    else:
        logger.error(f"[Dispatcher] 用户 {msg.from_user} 绑定失败")
    return True
