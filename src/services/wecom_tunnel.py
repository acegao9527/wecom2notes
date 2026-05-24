import os
import time
import asyncio
import subprocess
import logging
from src.services.wecom import WeComService, init_wecom, download_image

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("wecom_tunnel")

# 实验性 Telegram 中转配置
TARGET_BOT = os.getenv("TELEGRAM_TARGET_BOT", "")
TDL_PATH = os.getenv("TDL_PATH", "/usr/local/bin/tdl")
TDL_DATA_DIR = os.getenv("TDL_DATA_DIR", "/app/data/tdl")

# 强制开启调试日志以观察轮询过程
logging.getLogger("src.services.wecom.polling").setLevel(logging.DEBUG)
logging.getLogger("wecom_tunnel").setLevel(logging.DEBUG)

async def send_to_telegram(sender_name, content, media_path=None):
    """
    使用 tdl 模拟用户向 Bot 发送消息
    """
    caption = f"[WeCom:{sender_name}] {content}"
    if not TARGET_BOT:
        logger.error("TELEGRAM_TARGET_BOT 未配置，跳过 Telegram 中转")
        return
    
    cmd = [TDL_PATH, "upload", "--chat", TARGET_BOT, "--ns", "default", "--storage", f"path={TDL_DATA_DIR},type=bolt"]
    
    # 增加代理配置 (Linus: 既然 tc 没翻墙，那就给它加个梯子)
    proxy_url = os.getenv("TELEGRAM_PROXY_URL")
    path_to_send = media_path
    if not path_to_send:
        temp_file = f"/tmp/msg_{int(time.time())}.txt"
        with open(temp_file, "w") as f:
            f.write(content)
        path_to_send = temp_file

    if proxy_url:
        # 显式转换为字符串，防止 NoneType 导致 join 报错
        cmd.extend(["--proxy", str(proxy_url)])
    cmd.extend(["--path", path_to_send, "--caption", caption if media_path else f"[WeCom:{sender_name}]"])

    logger.info(f"Running tdl command: {' '.join(cmd)}")
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            logger.info(f"Successfully sent message from {sender_name} to Telegram")
        else:
            logger.error(f"Failed to send message via tdl: {stderr.decode()}")
    except Exception as e:
        logger.error(f"Error executing tdl: {e}")

async def tunnel_loop():
    logger.info(">>> WeCom to Telegram Tunnel Starting (Inside Docker) <<<")
    
    # 初始化 WeCom (参数已从 .env 加载)
    init_wecom(
        corp_id=os.getenv("WECOM_CORP_ID"),
        chat_secret=os.getenv("WECOM_APP_SECRET"),
        private_key_path="private_key.pem"
    )

    while True:
        try:
            # 拉取消息 (同步方法，用 to_thread)
            logger.debug("Fetching messages from WeCom...")
            messages = await asyncio.to_thread(WeComService.fetch_messages, limit=50, timeout=10)
            
            if messages:
                logger.info(f"Fetched {len(messages)} messages from WeCom")
                for msg in messages:
                    sender = msg.get("from", "Unknown")
                    msg_type = msg.get("msgtype")
                    content = ""
                    media_path = None
                    
                    if msg_type == "text":
                        content = msg.get("text", {}).get("content", "")
                    elif msg_type == "image":
                        # 下载图片
                        media_id = msg.get("image", {}).get("sdkfileid")
                        if media_id:
                            media_path = await asyncio.to_thread(download_image, media_id, msg.get("msgid"))
                    
                    # 转发到 Telegram
                    await send_to_telegram(sender, content or f"[{msg_type} message]", media_path)
            
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Tunnel Loop Error: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(tunnel_loop())
