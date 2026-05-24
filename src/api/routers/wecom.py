"""
企业微信回调路由。
"""
from __future__ import annotations

import logging
import os
import xml.etree.cElementTree as ET

from fastapi import APIRouter, HTTPException, Query, Request, Response

from src.services.message_processor import process_message
from src.services.wecom import WeComService, parse_wecom_message
from src.services.wecom_crypto import WXBizMsgCrypt

logger = logging.getLogger(__name__)

wecom_router = APIRouter(prefix="/wecom", tags=["WeCom"])


def _crypto() -> WXBizMsgCrypt:
    token = os.getenv("WECOM_TOKEN")
    aes_key = os.getenv("WECOM_ENCODING_AES_KEY")
    corp_id = os.getenv("WECOM_CORP_ID")
    if not all([token, aes_key, corp_id]):
        raise HTTPException(status_code=500, detail="WeCom callback crypto config is incomplete")
    return WXBizMsgCrypt(token, aes_key, corp_id)


def _decrypt_callback_xml(body: bytes, msg_signature: str | None, timestamp: str | None, nonce: str | None) -> str:
    xml_str = body.decode("utf-8") if body else ""
    if not xml_str or "<Encrypt>" not in xml_str:
        return xml_str
    if not all([msg_signature, timestamp, nonce]):
        raise HTTPException(status_code=400, detail="encrypted callback missing signature params")
    ret, decrypted = _crypto().DecryptMsg(xml_str, msg_signature, timestamp, nonce)
    if ret != 0 or decrypted is None:
        raise HTTPException(status_code=400, detail=f"WeCom decrypt failed: {ret}")
    return decrypted.decode("utf-8") if isinstance(decrypted, bytes) else decrypted


async def _process_wecom_messages() -> dict:
    from src.services.database import DatabaseService

    start_seq = DatabaseService.get_last_seq()
    raw_messages = WeComService.fetch_messages()
    logger.info(f"[WeCom] 获取到 {len(raw_messages)} 条消息, 起始 seq={start_seq}")

    processed_count = 0
    for raw in raw_messages:
        msg = parse_wecom_message(raw)
        if not msg:
            logger.warning(f"[WeCom] 消息解析失败: msgid={raw.get('msgid')}")
            continue
        await process_message(msg)
        processed_count += 1

    logger.info(f"[WeCom] 处理完成: 总数={len(raw_messages)}, 成功处理={processed_count}")
    return {"seq": start_seq, "total": len(raw_messages), "processed": processed_count}


@wecom_router.get("/callback")
async def wecom_verify_url(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
):
    """企业微信回调 URL 验证。"""
    ret, reply = _crypto().VerifyURL(msg_signature, timestamp, nonce, echostr)
    if ret != 0 or reply is None:
        raise HTTPException(status_code=400, detail=f"WeCom verify failed: {ret}")
    return Response(content=reply.decode("utf-8") if isinstance(reply, bytes) else reply)


@wecom_router.post("/callback")
async def wecom_receive_message(
    request: Request,
    msg_signature: str | None = None,
    timestamp: str | None = None,
    nonce: str | None = None,
):
    """企业微信回调入口，同时触发消息归档拉取。"""
    try:
        body = await request.body()
        if body:
            xml_str = _decrypt_callback_xml(body, msg_signature, timestamp, nonce)
            try:
                root = ET.fromstring(xml_str)
                msg_type = root.findtext("MsgType", default="")
                from_user = root.findtext("FromUserName", default="")
                logger.info(f"[WeCom] 收到回调: type={msg_type}, from={from_user}")
            except ET.ParseError as e:
                logger.warning(f"[WeCom] XML 解析失败: {e}")
        else:
            logger.info("[WeCom] 收到空回调请求体，执行主动拉取")

        result = await _process_wecom_messages()
        return {"status": "success", **result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[WeCom] 处理失败: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
