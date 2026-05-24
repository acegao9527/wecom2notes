import logging
import os
import sys
from typing import Dict

def setup_logging():
    """
    配置全局和模块级日志系统

    支持通过环境变量控制不同模块的日志级别。

    环境变量命名规则: LOG_LEVEL_<MODULE_ALIAS>

    支持的 MODULE_ALIAS:
    - WECOM         -> src.services.wecom
    - WECOM_POLLING -> src.services.wecom.polling (轮询日志独立配置)
    - CRAFT         -> src.services.craft
    - DB            -> src.services.database
    - API           -> src.api
    - HANDLERS      -> src.handlers
    - RPA           -> src.services.message_processor (RPA相关的日志)

    特殊值:
    - OFF/DISABLE -> CRITICAL (关闭日志)
    """

    # 1. 基础格式配置
    # 包含 logger name 以便区分模块
    log_format = '%(asctime)s - %(levelname)s - [%(name)s] - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # 2. 获取全局日志级别 (默认 INFO)
    global_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    global_level = getattr(logging, global_level_str, logging.INFO)

    # 3. 初始化根 Logger
    # 使用 force=True 覆盖之前的配置 (如 uvicorn 可能已配置)
    logging.basicConfig(
        level=global_level,
        format=log_format,
        datefmt=date_format,
        stream=sys.stdout,
        force=True
    )

    # 4. 模块映射定义
    # Key: Logger 前缀, Value: 环境变量后缀
    modules_map: Dict[str, str] = {
        "src.services.wecom": "WECOM",
        "src.services.wecom.polling": "WECOM_POLLING",  # 轮询日志独立配置
        "src.services.craft": "CRAFT",
        "src.services.database": "DB",
        "src.api": "API",
        "src.handlers": "HANDLERS",
        "src.services.message_processor": "RPA",
        "wecom2notes.startup": "STARTUP",  # 应用启动日志

        # 第三方库控制
        "uvicorn": "UVICORN",
        "uvicorn.access": "ACCESS",       # 访问日志
        "apscheduler": "APSCHEDULER",
        "httpx": "HTTPX",
    }

    configured_modules = []

    for module_name, env_suffix in modules_map.items():
        env_var_name = f"LOG_LEVEL_{env_suffix}"
        level_str = os.getenv(env_var_name)

        # 特殊处理：STARTUP 默认开启 (INFO)，除非显式关闭
        if env_suffix == "STARTUP" and not level_str:
            level_str = "INFO"

        if level_str:
            level_str = level_str.upper()
            logger = logging.getLogger(module_name)

            # 处理关闭指令
            if level_str in ["OFF", "DISABLE", "FALSE", "NO", "0", "NONE"]:
                logger.setLevel(logging.CRITICAL + 1) # 比 CRITICAL 更高，实际上不打印
                configured_modules.append(f"{env_suffix}: OFF")
            else:
                level = getattr(logging, level_str, None)
                if isinstance(level, int):
                    logger.setLevel(level)
                    # 防止父级 logger (root) 的 handlers 重复打印 (如果父级级别更低)
                    # 通常不需要 propagation=False，除非我们想完全隔离
                    configured_modules.append(f"{env_suffix}: {level_str}")
                else:
                    logging.warning(f"环境变量 {env_var_name} 的值 '{level_str}' 无效，已忽略。")

    # 打印配置摘要
    root_logger = logging.getLogger()
    logging.info(f"Log System Initialized. Global Level: {global_level_str}")
    if configured_modules:
        logging.info(f"Module Overrides: {', '.join(configured_modules)}")
