"""
企业微信服务模块

集成官方 SDK 拉取消息存档
"""
import base64
import ctypes
import json
import logging
import os
import time
import urllib.request
from typing import List, Optional

logger = logging.getLogger(__name__)
# 独立的轮询日志器，与 wecom 主日志隔离
logger_polling = logging.getLogger(f"{__name__}.polling")

# 图片保存目录
IMAGE_SAVE_DIR = os.getenv("IMAGE_SAVE_DIR", "./images")


# SDK 结构体定义
class Slice_t(ctypes.Structure):
    _fields_ = [
        ("buf", ctypes.c_char_p),
        ("len", ctypes.c_int),
    ]


class MediaData_t(ctypes.Structure):
    _fields_ = [
        ("outindexbuf", ctypes.c_char_p),
        ("out_len", ctypes.c_int),
        ("data", ctypes.c_char_p),
        ("data_len", ctypes.c_int),
        ("is_finish", ctypes.c_int),
    ]


# 全局变量
_corp_id = ""
_chat_secret = ""
_private_key = ""
_sdk_lib = None
_sdk_instance = None
_access_token = ""
_access_token_expires_at = 0
WECOM_SEQ_FILE = "/app/data/.wecom_seq"
WECOM_OFFSET_MAX = int(os.getenv("WECOM_OFFSET_MAX") or "0")

def get_last_seq_from_file() -> int:
    """
    获取上次的 seq，优先使用配置中的最大偏移量
    """
    try:
        from src.services.database import DatabaseService
        db_seq = DatabaseService.get_last_seq()
        if db_seq:
            file_seq = db_seq
        else:
            file_seq = 0
    except Exception:
        file_seq = 0

    if os.path.exists(WECOM_SEQ_FILE):
        try:
            with open(WECOM_SEQ_FILE, "r") as f:
                content = f.read().strip()
                if content:
                    file_seq = max(file_seq, int(content))
                    logger_polling.info(f"[WeCom] Loaded seq from {WECOM_SEQ_FILE}: {file_seq}")
        except Exception as e:
            logger_polling.error(f"[WeCom] Error reading seq file: {e}")

    # 如果配置了最大偏移量且大于文件中的值，使用配置的值
    if WECOM_OFFSET_MAX > 0:
        if file_seq == 0 or WECOM_OFFSET_MAX > file_seq:
            logger_polling.info(f"[WeCom] Using configured max offset: {WECOM_OFFSET_MAX} (file seq: {file_seq})")
            return WECOM_OFFSET_MAX

    return file_seq

def save_last_seq_to_file(seq: int):
    try:
        with open(WECOM_SEQ_FILE, "w") as f:
            f.write(str(seq))
        try:
            from src.services.database import DatabaseService
            DatabaseService.set_source_cursor("wecom", seq)
        except Exception as e:
            logger_polling.warning(f"[WeCom] Error saving seq to db: {e}")
    except Exception as e:
        logger_polling.error(f"[WeCom] Error saving seq file: {e}")


def init_wecom(corp_id: str, chat_secret: str, private_key_path: str = "private_key.pem") -> None:
    """
    初始化企业微信配置

    Args:
        corp_id: 企业ID
        chat_secret: 消息存档的Secret
        private_key_path: 私钥文件路径
    """
    global _corp_id, _chat_secret, _private_key, _sdk_lib

    _corp_id = corp_id
    _chat_secret = chat_secret

    # 读取私钥
    if os.path.exists(private_key_path):
        with open(private_key_path, 'r') as f:
            _private_key = f.read()
    else:
        logger.warning(f"[WeCom] Private key file not found: {private_key_path}")

    # 加载 SDK
    _sdk_lib = _load_sdk_lib()


def _load_sdk_lib():
    """加载 SDK 库并定义函数签名"""
    # 1. 检查显式禁用开关
    if os.getenv("WECOM_DISABLE_SDK", "").lower() == "true":
        logger.warning("[WeCom] SDK loading explicitly disabled by WECOM_DISABLE_SDK.")
        return None

    # 2. 根据平台选择 SDK
    import platform
    system = platform.system()
    machine = platform.machine()

    logger.info(f"[WeCom] 当前系统: {system}, 架构: {machine}")

    # 确定 SDK 路径
    if system == "Darwin" and machine in ("arm64", "aarch64"):
        # Mac ARM (M1/M2)
        sdk_path = "lib/wework-arm64/libWeWorkFinanceSdk_C.so"
    elif system == "Linux" and machine == "x86_64":
        # Linux x86_64
        sdk_path = "lib/wework-x86_64/libWeWorkFinanceSdk_C.so"
    elif system == "Linux" and machine == "aarch64":
        # Linux ARM64
        sdk_path = "lib/wework-arm64/libWeWorkFinanceSdk_C.so"
    else:
        # 默认使用 Linux SDK
        sdk_path = "lib/wework-x86_64/libWeWorkFinanceSdk_C.so"

    sdk_paths = [
        sdk_path,
        "libWeWorkFinanceSdk.so",
        "/usr/local/lib/libWeWorkFinanceSdk.so",
        "./libWeWorkFinanceSdk.so",
    ]

    logger.info(f"[WeCom] 当前工作目录: {os.getcwd()}")

    for path in sdk_paths:
        logger.info(f"[WeCom] 检查路径: {path} -> {os.path.exists(path)}")
        try:
            if os.path.exists(path):
                logger.info(f"[WeCom] 加载 SDK: {path}")
                lib = ctypes.cdll.LoadLibrary(path)

                # 定义函数签名
                lib.NewSdk.restype = ctypes.c_void_p
                lib.Init.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
                lib.Init.restype = ctypes.c_int
                lib.GetChatData.argtypes = [
                    ctypes.c_void_p, ctypes.c_ulonglong, ctypes.c_uint,
                    ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(Slice_t)
                ]
                lib.GetChatData.restype = ctypes.c_int
                lib.DecryptData.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(Slice_t)]
                lib.DecryptData.restype = ctypes.c_int
                # 媒体下载函数
                lib.GetMediaData.argtypes = [
                    ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p,
                    ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(MediaData_t)
                ]
                lib.GetMediaData.restype = ctypes.c_int
                # MediaData 辅助函数
                lib.NewMediaData.restype = ctypes.POINTER(MediaData_t)
                lib.FreeMediaData.argtypes = [ctypes.POINTER(MediaData_t)]
                lib.GetData.argtypes = [ctypes.POINTER(MediaData_t)]
                lib.GetData.restype = ctypes.c_void_p  # 必须用 c_void_p，不是 c_char_p
                lib.GetDataLen.argtypes = [ctypes.POINTER(MediaData_t)]
                lib.GetDataLen.restype = ctypes.c_int
                lib.GetOutIndexBuf.argtypes = [ctypes.POINTER(MediaData_t)]
                lib.GetOutIndexBuf.restype = ctypes.c_char_p
                lib.IsMediaDataFinish.argtypes = [ctypes.POINTER(MediaData_t)]
                lib.IsMediaDataFinish.restype = ctypes.c_int
                lib.NewSlice.restype = ctypes.POINTER(Slice_t)
                lib.FreeSlice.argtypes = [ctypes.POINTER(Slice_t)]
                lib.GetContentFromSlice.restype = ctypes.c_char_p
                lib.GetSliceLen.argtypes = [ctypes.POINTER(Slice_t)]
                lib.GetSliceLen.restype = ctypes.c_int
                lib.DestroySdk.argtypes = [ctypes.c_void_p]

                logger.info(f"[WeCom] SDK 加载成功")
                return lib
        except Exception as e:
            logger.error(f"[WeCom] 加载失败: {path}, error={e}")

    logger.warning("[WeCom] SDK 未找到")
    return None


def _ensure_sdk_init():
    """确保 SDK 已初始化"""
    global _sdk_instance

    if _sdk_instance is not None:
        return _sdk_instance

    if not _sdk_lib:
        return None

    try:
        new_sdk = _sdk_lib.NewSdk()
        result = _sdk_lib.Init(new_sdk, _corp_id.encode(), _chat_secret.encode())
        if result != 0:
            error_message = f"[WeCom] SDK init failed with code: {result}. "
            if result == -1:
                error_message += "Common cause: Invalid corp_id or chat_secret. Please check your WECOM_CORP_ID and WECOM_APP_SECRET in .env file."
            elif result == -2:
                error_message += "Common cause: Invalid private key path or content. Please check your WECOM_PRIVATE_KEY_PATH and ensure private_key.pem is valid."
            elif result == -3:
                error_message += "Common cause: Network error or server unreachable. Please check your network connection and WeCom service status."
            else:
                error_message += "Refer to WeCom SDK documentation for error code details (https://work.weixin.qq.com/api/doc/90000/90003/131018)."
            logger.error(error_message)
            return None

        _sdk_instance = new_sdk
        logger.info("[WeCom] SDK initialized")
        return new_sdk
    except Exception as e:
        logger.error(f"[WeCom] SDK initialization error: {e}")
        return None


def _decrypt_message(encrypt_random_key: str, encrypt_chat_msg: str) -> dict:
    """使用私钥解密消息"""
    try:
        from Crypto.Cipher import PKCS1_v1_5
        from Crypto.PublicKey import RSA
        
        private_key = RSA.import_key(_private_key)
        cipher = PKCS1_v1_5.new(private_key)

        # 解密随机密钥
        key_bytes = cipher.decrypt(base64.b64decode(encrypt_random_key), sentinel="ERROR")
        if key_bytes == b"ERROR":
            logger.error("[WeCom] Failed to decrypt random key")
            return {}

        # 使用 SDK 解密消息内容
        slice_ptr = _sdk_lib.NewSlice()
        result = _sdk_lib.DecryptData(key_bytes, encrypt_chat_msg.encode(), slice_ptr)

        if result != 0:
            logger.error(f"[WeCom] DecryptData failed: code={result}")
            _sdk_lib.FreeSlice(slice_ptr)
            return {}

        content_ptr = _sdk_lib.GetContentFromSlice(slice_ptr)
        if not content_ptr:
            logger.error("[WeCom] GetContentFromSlice returned NULL")
            _sdk_lib.FreeSlice(slice_ptr)
            return {}

        content_len = _sdk_lib.GetSliceLen(slice_ptr)
        result_str = ctypes.string_at(content_ptr, content_len).decode("utf-8")
        _sdk_lib.FreeSlice(slice_ptr)

        result = json.loads(result_str)
        return result

    except Exception as e:
        logger.error(f"[WeCom] Decryption error: {e}")
        return {}


class WeComService:
    """企业微信服务类"""

    @staticmethod
    def fetch_messages(limit: int = 1000, timeout: int = 5) -> List[dict]:
        """
        使用 SDK 拉取消息

        Args:
            limit: 每次拉取的最大条数
            timeout: 超时时间（秒）

        Returns:
            解密后的消息列表
        """
        if not _sdk_lib:
            return []

        sdk = _ensure_sdk_init()
        if not sdk:
            return []

        messages = []
        seq = get_last_seq_from_file()

        try:
            slice_ptr = _sdk_lib.NewSlice()

            result = _sdk_lib.GetChatData(
                sdk, seq, limit, b"", b"", timeout, slice_ptr
            )

            if result != 0:
                logger_polling.error(f"[WeCom] GetChatData failed: code={result}")
                _sdk_lib.FreeSlice(slice_ptr)
                return []

            data_ptr = _sdk_lib.GetContentFromSlice(slice_ptr)
            if not data_ptr:
                _sdk_lib.FreeSlice(slice_ptr)
                return []

            data_len = _sdk_lib.GetSliceLen(slice_ptr)
            data_str = ctypes.string_at(data_ptr, data_len).decode("utf-8")
            _sdk_lib.FreeSlice(slice_ptr)

            data = json.loads(data_str)
            chat_data = data.get("chatdata", [])

            if not chat_data:
                return []

            # 获取机器人自己的UserID，用于过滤消息
            bot_userid = os.getenv("WECOM_BOT_USERID")

            # 解密每条消息
            max_seq = seq
            for msg in chat_data:
                decrypt_result = _decrypt_message(
                    msg.get('encrypt_random_key', ''),
                    msg.get('encrypt_chat_msg', '')
                )

                if decrypt_result:
                    sender = decrypt_result.get('from')
                    # 如果配置了机器人ID且消息来自机器人自己，则忽略
                    if bot_userid and sender == bot_userid:
                        current_seq = msg.get('seq')
                        if current_seq > max_seq:
                            max_seq = current_seq
                        continue

                    current_seq = msg.get('seq')
                    decrypt_result['seq'] = current_seq
                    decrypt_result['msgid'] = msg.get('msgid')
                    messages.append(decrypt_result)
                    if current_seq > max_seq:
                        max_seq = current_seq
                else:
                    logger_polling.warning(f"[WeCom] 解密失败: msgid={msg.get('msgid')}")

            # 如果成功拉取到新消息，更新seq
            if max_seq > seq:
                save_last_seq_to_file(max_seq)

        except Exception as e:
            logger_polling.error(f"[WeCom] 获取消息异常: {e}")

        return messages


def _get_access_token() -> Optional[str]:
    """
    获取企业微信 access_token（带缓存）

    Returns:
        access_token 或 None
    """
    global _access_token, _access_token_expires_at

    # 检查缓存是否有效
    if _access_token and _access_token_expires_at > time.time() + 60:
        return _access_token

    if not _corp_id or not _chat_secret:
        logger.error("[WeCom] CorpID 或 AppSecret 未配置")
        return None

    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={_corp_id}&corpsecret={_chat_secret}"

    try:
        import requests
        response = requests.get(url, timeout=10)
        data = response.json()

        if data.get("errcode") == 0:
            _access_token = data["access_token"]
            _access_token_expires_at = time.time() + data["expires_in"] - 120  # 提前2分钟刷新
            logger.info("[WeCom] Access token 获取成功")
            return _access_token
        else:
            logger.error(f"[WeCom] 获取 access_token 失败: {data}")
            return None
    except Exception as e:
        logger.error(f"[WeCom] 获取 access_token 异常: {e}")
        return None


def download_image(media_id: str, msg_id: str = "", seq: int = 0, roomid: str = "", file_extension: str = "jpg", original_name: str = "") -> Optional[str]:
    """
    从企业微信服务器下载媒体文件（使用 SDK）

    Args:
        media_id: 媒体的 sdkfileid
        msg_id: 消息 ID
        seq: 消息序号
        roomid: 群聊 ID
        file_extension: 文件扩展名 (默认 jpg)
        original_name: 原始文件名 (可选)

    Returns:
        本地文件路径或 None
    """
    logger.info(f"[WeCom] download_image: media_id={media_id[:30] if media_id else 'None'}..., msg_id={msg_id}")

    # 确保保存目录存在
    os.makedirs(IMAGE_SAVE_DIR, exist_ok=True)

    # 生成文件名
    timestamp = int(time.time() * 1000)
    prefix = "media"

    # 构建基础文件名 (用于唯一性)
    base_name = f"{prefix}_{msg_id if msg_id else timestamp}_{media_id[:8]}"

    if original_name:
        # 清理文件名中的非法字符
        safe_name = "".join([c for c in original_name if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
        if len(safe_name) > 100:
            name, ext = os.path.splitext(safe_name)
            safe_name = name[:100] + ext
        filename = f"{base_name}_{safe_name}"
    else:
        filename = f"{base_name}.{file_extension}"

    local_path = os.path.join(IMAGE_SAVE_DIR, filename)
    logger.info(f"[WeCom] 文件保存路径: {local_path}")

    # 优先使用 SDK 下载
    if _sdk_lib:
        logger.info(f"[WeCom] 使用 SDK 下载...")
        sdk = _ensure_sdk_init()
        if sdk:
            try:
                # 使用 MediaData_t 结构体（SDK 1.8+）
                media_data_ptr = _sdk_lib.NewMediaData()
                if not media_data_ptr:
                    logger.error("[WeCom] NewMediaData 失败")
                    return None

                all_data = b""
                indexbuf = b""  # 首次为空
                max_iterations = 100  # 防止无限循环

                for iteration in range(max_iterations):
                    result = _sdk_lib.GetMediaData(
                        sdk,
                        indexbuf,
                        media_id.encode('utf-8'),
                        b"",
                        b"",
                        30,
                        media_data_ptr
                    )

                    if result != 0:
                        logger.error(f"[WeCom] GetMediaData 第{iteration+1}次调用失败: code={result}")
                        _sdk_lib.FreeMediaData(media_data_ptr)
                        return None

                    data_ptr = _sdk_lib.GetData(media_data_ptr)
                    data_len = _sdk_lib.GetDataLen(media_data_ptr)
                    is_finish = _sdk_lib.IsMediaDataFinish(media_data_ptr)

                    if data_ptr and data_len > 0:
                        chunk = ctypes.string_at(data_ptr, data_len)
                        all_data += chunk
                        logger.info(f"[WeCom] 第{iteration+1}次: {data_len} bytes, 累计: {len(all_data)}")
                    else:
                        logger.warning(f"[WeCom] 第{iteration+1}次返回空数据")

                    if is_finish:
                        logger.info(f"[WeCom] 下载完成，总大小: {len(all_data)} bytes")
                        break

                    # 获取下一次请求需要的 outindexbuf
                    media_data = media_data_ptr.contents
                    outindexbuf = media_data.outindexbuf
                    outindexbuf_len = media_data.out_len
                    if outindexbuf and outindexbuf_len > 0:
                        indexbuf = ctypes.string_at(outindexbuf, outindexbuf_len)
                    else:
                        logger.warning("[WeCom] 无法获取下一分片 outindexbuf")
                        break

                # 保存文件
                if all_data:
                    with open(local_path, "wb") as f:
                        f.write(all_data)

                    file_size = os.path.getsize(local_path)
                    logger.info(f"[WeCom] 下载成功: {local_path} ({file_size} bytes)")
                    _sdk_lib.FreeMediaData(media_data_ptr)
                    return local_path

                logger.error("[WeCom] 未获取到任何数据")
                _sdk_lib.FreeMediaData(media_data_ptr)

            except Exception as e:
                logger.error(f"[WeCom] SDK 下载异常: {e}")
                import traceback
                traceback.print_exc()

        logger.warning("[WeCom] SDK 下载失败")
    else:
        logger.warning("[WeCom] SDK 未加载")

    return None


# 便捷函数
def fetch_messages(limit: int = 1000, timeout: int = 5) -> List[dict]:
    """获取消息（便捷函数）"""
    return WeComService.fetch_messages(limit=limit, timeout=timeout)


# --- 新增轮询相关功能 ---
import asyncio
from src.models.chat_record import AttachmentInfo, UnifiedMessage
from src.services.message_processor import process_message

def parse_wecom_message(msg: dict) -> Optional[UnifiedMessage]:
    """
    解析企微消息字典为 UnifiedMessage
    """
    try:
        msg_id = msg.get("msgid")
        from_user = msg.get("from")
        to_user = msg.get("to")
        chat_id = msg.get("roomid") or msg.get("tolist") or to_user
        # 企微 msgtime 是秒级时间戳
        create_time = int(msg.get("msgtime", time.time()))
        if create_time > 1e11:
            create_time = create_time // 1000
        msg_type = msg.get("msgtype")
        content = ""
        attachments = []

        # 根据不同消息类型提取核心内容
        # 注意：这里的 content 格式需要与 message_processor 和 formatter 里的逻辑对应
        if msg_type in ["text", "markdown"]:
            content = msg.get(msg_type, {}).get("content", "")
            if msg_type == "text":
                import re
                if re.match(r"^https?://[^\s]+$", content.strip(), re.IGNORECASE):
                    msg_type = "link"
        elif msg_type in ["image", "video", "voice", "file"]:
            # 媒体消息：尝试下载文件并获取本地路径
            media_data = msg.get(msg_type, {})
            sdkfileid = media_data.get("sdkfileid")

            if sdkfileid:
                ext = "jpg"
                original_name = ""
                if msg_type == "file":
                    ext = media_data.get("fileext", "bin")
                    original_name = media_data.get("filename", "")
                elif msg_type == "video":
                    ext = "mp4"
                elif msg_type == "voice":
                    ext = "amr"

                # 下载文件 (调用 wecom.py 内部的 download_image)
                local_path = download_image(
                    media_id=sdkfileid,
                    msg_id=msg_id,
                    file_extension=ext,
                    original_name=original_name
                )

                if local_path:
                    content = local_path
                    attachments.append(
                        AttachmentInfo(
                            file_name=original_name or os.path.basename(local_path),
                            local_path=local_path,
                        )
                    )
                else:
                    logger_polling.warning(f"[WeCom Parser] 下载媒体失败: {msg_id}")
                    content = json.dumps(media_data)
            else:
                content = json.dumps(media_data)
        elif msg_type == "link":
            link_data = msg.get("link", {})
            content = link_data.get("link_url") or link_data.get("url", "")
        else:
            # 对于其他未知类型，记录一个摘要
            content = f"Unsupported message type: {msg_type}"

        if not msg_id or not from_user:
            logger_polling.warning(f"[WeCom Parser] 缺少 msgid 或 from_user: {msg}")
            return None

        return UnifiedMessage(
            msg_id=msg_id,
            source="wecom",
            msg_type=msg_type,
            content=content,
            from_user=from_user,
            create_time=create_time,
            raw_data=msg,
            chat_id=chat_id if isinstance(chat_id, str) else None,
            to_user=to_user,
            sender_name=msg.get("from_name") or msg.get("sender_name"),
            attachments=attachments,
        )
    except Exception as e:
        logger_polling.error(f"[WeCom Parser] 解析消息失败: {e}", exc_info=True)
        return None


async def run_wecom_polling():
    """
    企微消息轮询主循环
    """
    logger_polling.info(">>> WeCom Polling Service Starting... <<<")

    # 检查 SDK 是否被禁用
    if os.getenv("WECOM_DISABLE_SDK", "").lower() == "true" or not _sdk_lib:
        logger_polling.warning("[WeCom Polling] SDK 未加载或被禁用，轮询服务已停止。")
        return

    while True:
        try:
            # 使用 to_thread 在异步事件循环中运行同步的 fetch_messages
            # 将超时延长至20秒，提高长轮询效率
            messages = await asyncio.to_thread(fetch_messages, limit=100, timeout=20)

            if messages:
                logger_polling.info(f"[WeCom Polling] 拉取到 {len(messages)} 条消息")
                for msg_data in messages:
                    msg_type = msg_data.get("msgtype", "unknown")
                    from_user = msg_data.get("from", "unknown")
                    content_preview = msg_data.get("text", {}).get("content", "")[:100] if msg_data.get("text") else ""
                    logger_polling.info(f"[WeCom] 消息: from={from_user}, type={msg_type}, content={content_preview}")

                    unified_msg = parse_wecom_message(msg_data)
                    if unified_msg:
                        asyncio.create_task(process_message(unified_msg))
                    else:
                        logger_polling.warning(f"[WeCom Polling] 解析失败: {msg_data.get('msgid')}")
            else:
                await asyncio.sleep(1)

        except Exception as e:
            logger_polling.error(f"[WeCom Polling] 轮询错误: {e}", exc_info=True)
            await asyncio.sleep(15)
