"""
用户绑定服务模块
处理企微用户与Craft文档的映射关系
"""
import json
import logging
from typing import Optional, List
from datetime import datetime

import requests

from src.models.binding import UserBinding, BindingCreate, BindingResponse
from src.services.database import get_connection

logger = logging.getLogger(__name__)

# Craft 配置
API_BASE_URL = "https://connect.craft.do/links"


class BindingService:
    """绑定服务类"""

    @staticmethod
    def create_binding(create: BindingCreate) -> Optional[UserBinding]:
        """创建或更新用户绑定"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # 检查是否已存在
                cursor.execute(
                    "SELECT id FROM user_mappings WHERE wecom_openid = ?",
                    (create.wecom_openid,)
                )
                existing = cursor.fetchone()

                if existing:
                    # 更新
                    cursor.execute("""
                        UPDATE user_mappings
                        SET craft_link_id = ?, craft_document_id = ?, craft_token = ?, display_name = ?, is_enabled = ?, updated_at = ?
                        WHERE wecom_openid = ?
                    """, (
                        create.craft_link_id,
                        create.craft_document_id,
                        create.craft_token,
                        create.display_name,
                        int(create.is_enabled),
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        create.wecom_openid
                    ))
                    binding_id = existing['id']
                else:
                    # 插入
                    cursor.execute("""
                        INSERT INTO user_mappings (wecom_openid, craft_link_id, craft_document_id, craft_token, display_name, is_enabled)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        create.wecom_openid,
                        create.craft_link_id,
                        create.craft_document_id,
                        create.craft_token,
                        create.display_name,
                        int(create.is_enabled),
                    ))
                    binding_id = cursor.lastrowid

                conn.commit()
                return BindingService.get_binding_by_openid(create.wecom_openid, enabled_only=False)

        except Exception as e:
            logger.error(f"[Binding] 创建绑定失败: openid={create.wecom_openid}, error={e}")
            return None

    @staticmethod
    def get_binding_by_openid(openid: str, enabled_only: bool = True) -> Optional[UserBinding]:
        """根据企微OpenID获取绑定"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                sql = "SELECT * FROM user_mappings WHERE wecom_openid = ?"
                params = [openid]
                if enabled_only:
                    sql += " AND is_enabled = 1"
                cursor.execute(sql, params)
                row = cursor.fetchone()
                if row:
                    return BindingService._row_to_binding(row)
                return None
        except Exception as e:
            logger.error(f"[Binding] 查询绑定失败: openid={openid}, error={e}")
            return None

    @staticmethod
    def get_all_bindings() -> List[UserBinding]:
        """获取所有绑定"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM user_mappings ORDER BY created_at DESC")
                rows = cursor.fetchall()
                return [BindingService._row_to_binding(row) for row in rows]
        except Exception as e:
            logger.error(f"[Binding] 获取所有绑定失败: error={e}")
            return []

    @staticmethod
    def delete_binding(openid: str) -> bool:
        """删除绑定"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM user_mappings WHERE wecom_openid = ?", (openid,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"[Binding] 删除绑定失败: openid={openid}, error={e}")
            return False

    @staticmethod
    def set_binding_enabled(openid: str, is_enabled: bool) -> bool:
        """启用或停用绑定。"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE user_mappings SET is_enabled = ?, updated_at = ? WHERE wecom_openid = ?",
                    (int(is_enabled), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), openid),
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"[Binding] 更新绑定状态失败: openid={openid}, error={e}")
            return False

    @staticmethod
    def _row_to_binding(row) -> UserBinding:
        """将数据库行转换为UserBinding对象"""
        return UserBinding(
            id=row['id'],
            wecom_openid=row['wecom_openid'],
            craft_link_id=row['craft_link_id'],
            craft_document_id=row['craft_document_id'],
            craft_token=row['craft_token'] if 'craft_token' in row.keys() else None,
            display_name=row['display_name'] if 'display_name' in row.keys() else None,
            is_enabled=bool(row['is_enabled']) if 'is_enabled' in row.keys() else True,
            created_at=datetime.fromisoformat(row['created_at']) if isinstance(row['created_at'], str) else row['created_at'],
            updated_at=datetime.fromisoformat(row['updated_at']) if isinstance(row['updated_at'], str) else row['updated_at']
        )


def verify_craft_access(link_id: str, document_id: str, token: str = None) -> tuple[bool, str]:
    """
    验证Craft链接和文档ID是否可访问

    Args:
        link_id: Craft 链接 ID
        document_id: Craft 文档 ID
        token: 文档 Token（必填）

    Returns:
        (是否成功, 错误信息/显示名称)
    """
    if not token:
        return False, "未提供 token"

    url = f"{API_BASE_URL}/{link_id}/api/v1/blocks"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    params = {
        "id": document_id,
        "maxDepth": -2,
        "fetchMetadata": "false"
    }

    logger.info(f"[Binding] 验证 Craft: link_id={link_id}, document_id={document_id}")

    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        logger.info(f"[Binding] Craft API 响应: status={response.status_code}, body={response.text[:200]}")

        if response.status_code == 200:
            data = response.json()
            logger.info(f"[Binding] Craft API JSON 类型: {type(data).__name__}")

            # Craft API 返回 dict，content 可能是 list 或 dict
            title = None
            if isinstance(data, dict):
                title = data.get('title') or data.get('name')
                content = data.get('content')
                if not title and isinstance(content, dict):
                    title = content.get('title')
                elif not title and isinstance(content, list) and len(content) > 0:
                    # content 是 list，取第一个 page 的 markdown 作为标题
                    first_item = content[0]
                    if isinstance(first_item, dict):
                        title = first_item.get('markdown') or first_item.get('title')

            if title:
                logger.info(f"[Binding] 验证成功: title={title}")
                return True, title
            logger.info(f"[Binding] 验证成功，但未找到标题")
            return True, document_id
        else:
            return False, f"验证失败: HTTP {response.status_code}"
    except Exception as e:
        logger.error(f"[Binding] 验证异常: {e}")
        return False, f"验证失败: {str(e)}"
