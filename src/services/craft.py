"""
Craft 集成服务模块
"""
import json
import logging
from typing import List, Dict

import asyncio
import httpx
import requests

logger = logging.getLogger(__name__)

API_BASE_URL = "https://connect.craft.do/links"


async def save_blocks_to_craft(
    blocks: List[Dict],
    link_id: str,
    document_id: str = None,
    document_token: str = None
):
    """
    保存 blocks 到 Craft

    Args:
        blocks: 要保存的 blocks 列表
        link_id: Craft 链接 ID（必填）
        document_id: Craft 文档 ID（可选）
        document_token: Craft 文档 Token（必填）
    """
    if not link_id:
        logger.error("[Craft] link_id 未提供")
        return False

    if not document_token:
        logger.error("[Craft] document_token 未提供，无法访问 Craft 文档")
        return False

    logger.info(f"[Craft] 开始保存: {len(blocks)} blocks -> link={link_id}, doc={document_id}")
    for i, block in enumerate(blocks):
        logger.info(f"[Craft] Block[{i}]: {block}")

    await asyncio.sleep(0.5)

    url = f"{API_BASE_URL}/{link_id}/api/v1/blocks"
    headers = {
        "Authorization": f"Bearer {document_token}",
        "Content-Type": "application/json",
    }
    body = {
        "blocks": blocks,
        "position": {
            "position": "end",
            "pageId": document_id
        }
    }

    try:
        logger.info(f"[Craft] === HTTP Request ===")
        logger.info(f"[Craft] POST {url}")
        token_preview = (document_token or "")[:20]
        logger.info(f"[Craft] Headers: {{'Authorization': 'Bearer {token_preview}...', 'Content-Type': 'application/json'}}")
        logger.info(f"[Craft] Body: blocks={len(blocks)}, pageId={document_id}")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=body, headers=headers)
        logger.info(f"[Craft] === HTTP Response ===")
        logger.info(f"[Craft] Status: {response.status_code}")
        logger.info(f"[Craft] Body: {response.text[:500] if response.text else 'empty'}")

        # 检查是否是弃用警告
        if "deprecated" in response.text.lower() or "single document" in response.text.lower():
            logger.error(f"[Craft] 保存失败: API 已弃用，请创建新的 Multi Document API")
            return False

        # 尝试解析 JSON 响应
        try:
            response_json = response.json()
            if response.status_code in (200, 201) and "items" in response_json:
                logger.info(f"[Craft] 保存成功: {len(blocks)} blocks")
                return True
            elif response.status_code == 404:
                logger.error(f"[Craft] 保存失败: 文档不存在，请检查 link_id 和 document_id 是否正确")
                logger.error(f"[Craft] link_id={link_id}, document_id={document_id}")
                return False
            elif response.status_code == 429:
                # 请求频率限制，添加延迟后重试
                logger.warning(f"[Craft] 请求频率限制，等待后重试...")
                await asyncio.sleep(2)
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(url, json=body, headers=headers)
                logger.info(f"[Craft] 重试 Status: {response.status_code}")
                if response.status_code in (200, 201):
                    logger.info(f"[Craft] 重试成功: {len(blocks)} blocks")
                    return True
                logger.error(f"[Craft] 重试失败: {response.text[:200]}")
                return False
            else:
                logger.error(f"[Craft] 保存失败: 响应格式异常 {response_json}")
                return False
        except json.JSONDecodeError:
            if response.status_code == 200:
                logger.info(f"[Craft] 保存成功（无 JSON 响应）: {len(blocks)} blocks")
                return True
            elif response.status_code in (502, 503, 504):
                logger.error(f"[Craft] 保存失败: Craft 服务暂时不可用 (status={response.status_code})")
                return False
            logger.error(f"[Craft] 保存失败: 响应不是有效 JSON, status={response.status_code}")
            return False

    except Exception as e:
        logger.error(f"[Craft] 请求异常: {e}")
        return False


def fetch_todo_blocks(link_id: str, doc_id: str, token: str) -> List[Dict]:
    """
    获取 Craft 待办文档中的所有 blocks

    使用 fetch API 获取指定文档的 blocks，递归收集所有层级的 blocks

    Args:
        link_id: Craft 链接 ID（必填）
        doc_id: 文档 ID（必填）
        token: Craft API Token（必填）

    Returns:
        blocks 列表
    """
    if not all([link_id, doc_id, token]):
        logger.warning("[Craft] 参数不完整，无法获取待办文档")
        return []

    url = f"{API_BASE_URL}/{link_id}/api/v1/blocks"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    params = {
        "id": doc_id,
        "maxDepth": -2,
        "fetchMetadata": "false"
    }

    try:
        logger.info("[Craft] 获取待办文档 blocks...")
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()

        all_blocks = []
        if isinstance(data, dict):
            _collect_blocks_recursive(data, all_blocks)

        logger.info(f"[Craft] 共获取到 {len(all_blocks)} 个 blocks")
        return all_blocks

    except requests.exceptions.RequestException as e:
        logger.error(f"[Craft] 获取 blocks 失败: {e}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"[Craft] 解析响应失败: {e}")
        return []


def _collect_blocks_recursive(block: Dict, results: List[Dict]) -> None:
    """
    递归收集所有 blocks（排除根 page block）

    Args:
        block: 当前 block
        results: 结果列表
    """
    if not isinstance(block, dict):
        return

    block_type = block.get("type", "")
    if block_type != "page":
        results.append(block)

    children = block.get("content", [])
    if isinstance(children, list):
        for child in children:
            _collect_blocks_recursive(child, results)


def filter_today_todos(blocks: List[Dict], today: str) -> List[Dict]:
    """
    筛选当天的未完成待办任务

    条件：
    - listStyle 为 "task"
    - taskInfo 中包含当天日期
    - 任务状态为未完成（state 为 todo）

    Args:
        blocks: 所有 blocks
        today: 当天日期字符串

    Returns:
        符合条件的待办列表
    """
    today_todos = []

    for block in blocks:
        if not isinstance(block, dict):
            continue

        # 检查 listStyle
        if block.get("listStyle") != "task":
            continue

        # 获取 taskInfo
        task_info = block.get("taskInfo", {})
        if not task_info:
            continue

        # 检查日期和状态
        if task_info.get("scheduleDate") != today:
            continue
        if task_info.get("state") != "todo":
            continue

        content = block.get("markdown", "")
        if content:
            today_todos.append({
                "doc_name": "Craft 待办",
                "text": content.strip(),
                "schedule_date": today,
                "block_id": block.get("id", "")
            })

    logger.info(f"[Craft] 筛选出 {len(today_todos)} 个当天未完成待办")
    return today_todos
