"""
Craft 保存路由
"""
import logging

from fastapi import APIRouter, HTTPException

from src.services.craft import save_blocks_to_craft
from src.models.craft import CraftMessage

logger = logging.getLogger(__name__)

craft_router = APIRouter(prefix="/craft", tags=["Craft"])


@craft_router.post("/save")
async def craft_save(message: CraftMessage):
    """保存消息到 Craft"""
    try:
        block = {"type": "text", "markdown": message.message}
        await save_blocks_to_craft(
            [block],
            link_id=message.link_id,
            document_id=message.document_id,
            document_token=message.document_token,
        )
        return {"status": "success", "message": "Saved to Craft"}
    except Exception as e:
        logger.error(f"[Craft] 保存失败: {e}")
        raise HTTPException(status_code=500, detail="Failed to save to Craft")
