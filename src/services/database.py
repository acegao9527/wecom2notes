"""
SQLite 数据库服务。

负责基础迁移、消息存档、游标、目标配置、路由和投递状态。
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.core.models import TargetConfig
from src.models.chat_record import AttachmentInfo, UnifiedMessage

logger = logging.getLogger(__name__)

_db_path = "data/wecom2notes.db"


def init_db(db_path: str = None, **kwargs) -> None:
    """初始化数据库配置。"""
    global _db_path
    if db_path:
        _db_path = db_path

    db_dir = os.path.dirname(_db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    logger.info(f"[DB] SQLite 数据库路径: {_db_path}")


@contextmanager
def get_connection():
    """获取数据库连接。"""
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _parse_msg_time(ts) -> Optional[str]:
    if not ts:
        return None
    try:
        ts = int(ts)
        if ts > 1e11:
            ts = ts // 1000
        dt = datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OSError) as e:
        logger.warning(f"[DB] 时间戳解析失败: {ts}, error={e}")
        return None


def _row_to_dict(row: sqlite3.Row | None) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def _loads_json(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


class DatabaseService:
    """数据库服务类。"""

    @staticmethod
    def get_connection():
        conn = sqlite3.connect(_db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def run_migrations() -> None:
        """执行 SQL 迁移。"""
        base_dir = Path(__file__).resolve().parents[2]
        migrations_dir = base_dir / "src" / "sql" / "migrations"
        migrations_dir.mkdir(parents=True, exist_ok=True)

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id TEXT PRIMARY KEY,
                    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            for path in sorted(migrations_dir.glob("*.sql")):
                migration_id = path.name
                cursor.execute("SELECT id FROM schema_migrations WHERE id = ?", (migration_id,))
                if cursor.fetchone():
                    continue
                logger.info(f"[DB] 执行迁移: {migration_id}")
                cursor.executescript(path.read_text(encoding="utf-8"))
                cursor.execute("INSERT INTO schema_migrations (id) VALUES (?)", (migration_id,))
            DatabaseService._ensure_columns(cursor)
            conn.commit()

    @staticmethod
    def _ensure_columns(cursor: sqlite3.Cursor) -> None:
        """为旧数据库补齐新增列。"""
        table_columns = {
            "unified_messages": {
                "chat_id": "TEXT",
                "to_user": "TEXT",
                "sender_name": "TEXT",
                "updated_at": "DATETIME",
            },
            "destinations": {
                "workspace_id": "TEXT DEFAULT 'default'",
            },
            "routes": {
                "workspace_id": "TEXT DEFAULT 'default'",
            },
            "deliveries": {
                "workspace_id": "TEXT DEFAULT 'default'",
            },
        }
        for table, columns in table_columns.items():
            cursor.execute(f"PRAGMA table_info({table})")
            existing = {row[1] for row in cursor.fetchall()}
            for column, definition in columns.items():
                if column not in existing:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                    if table == "unified_messages" and column == "updated_at":
                        cursor.execute(
                            "UPDATE unified_messages SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL"
                        )

    @staticmethod
    def message_exists(msg: UnifiedMessage) -> bool:
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM unified_messages WHERE source = ? AND msg_id = ?",
                    (msg.source, msg.msg_id),
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"[DB] 检查统一消息是否存在失败: msgid={msg.msg_id}, error={e}")
            return False

    @staticmethod
    def save_unified_message(msg: UnifiedMessage) -> bool:
        """保存统一消息，返回是否首次写入。"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                created_at = _parse_msg_time(msg.create_time)
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO unified_messages
                    (msg_id, source, msg_type, from_user, content, raw_data, created_at, chat_id, to_user, sender_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        msg.msg_id,
                        msg.source,
                        msg.msg_type,
                        msg.from_user,
                        msg.content,
                        json.dumps(msg.raw_data, ensure_ascii=False),
                        created_at,
                        msg.chat_id,
                        msg.to_user,
                        msg.sender_name,
                    ),
                )
                inserted = cursor.rowcount > 0
                if inserted:
                    DatabaseService._save_attachments(cursor, msg)
                conn.commit()
                if inserted:
                    logger.info(f"[DB] 统一消息保存成功: source={msg.source}, msgid={msg.msg_id}")
                else:
                    logger.info(f"[DB] 统一消息已存在，跳过: source={msg.source}, msgid={msg.msg_id}")
                return inserted
        except Exception as e:
            logger.error(f"[DB] 保存统一消息失败: msgid={msg.msg_id}, error={e}")
            return False

    @staticmethod
    def _save_attachments(cursor: sqlite3.Cursor, msg: UnifiedMessage) -> None:
        for attachment in msg.attachments:
            cursor.execute(
                """
                INSERT INTO attachments
                (source, msg_id, file_name, local_path, content_type, size, sha256, url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    msg.source,
                    msg.msg_id,
                    attachment.file_name,
                    attachment.local_path,
                    attachment.content_type,
                    attachment.size,
                    attachment.sha256,
                    attachment.url,
                ),
            )

    @staticmethod
    def get_source_cursor(source: str) -> Optional[str]:
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT cursor_value FROM source_cursors WHERE source = ?", (source,))
                row = cursor.fetchone()
                return row["cursor_value"] if row else None
        except Exception as e:
            logger.warning(f"[DB] 获取游标失败: source={source}, error={e}")
            return None

    @staticmethod
    def set_source_cursor(source: str, cursor_value: str | int) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO source_cursors (source, cursor_value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(source) DO UPDATE SET
                    cursor_value = excluded.cursor_value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (source, str(cursor_value)),
            )
            conn.commit()

    @staticmethod
    def get_last_seq() -> int:
        cursor = DatabaseService.get_source_cursor("wecom")
        try:
            return int(cursor) if cursor else 0
        except ValueError:
            return 0

    @staticmethod
    def list_source_cursors() -> List[Dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM source_cursors ORDER BY updated_at DESC").fetchall()
            return [_row_to_dict(row) or {} for row in rows]

    @staticmethod
    def upsert_destination(destination_id: str, name: str, target_type: str, config: Dict[str, Any], is_enabled: bool = True) -> TargetConfig:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO destinations (id, name, target_type, config_json, is_enabled, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    target_type = excluded.target_type,
                    config_json = excluded.config_json,
                    is_enabled = excluded.is_enabled,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (destination_id, name, target_type, json.dumps(config, ensure_ascii=False), int(is_enabled)),
            )
            conn.commit()
        return TargetConfig(destination_id, name, target_type, config)

    @staticmethod
    def list_destinations(enabled_only: bool = False) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM destinations"
        params: tuple[Any, ...] = ()
        if enabled_only:
            sql += " WHERE is_enabled = 1"
        sql += " ORDER BY created_at DESC"
        with get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [DatabaseService._destination_row_to_dict(row) for row in rows]

    @staticmethod
    def get_destination(destination_id: str) -> Optional[TargetConfig]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM destinations WHERE id = ? AND is_enabled = 1",
                (destination_id,),
            ).fetchone()
            if not row:
                return None
            config = json.loads(row["config_json"] or "{}")
            return TargetConfig(
                id=row["id"],
                name=row["name"],
                target_type=row["target_type"],
                config=config,
            )

    @staticmethod
    def get_destination_record(destination_id: str) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM destinations WHERE id = ?", (destination_id,)).fetchone()
            if not row:
                return None
            return DatabaseService._destination_row_to_dict(row)

    @staticmethod
    def set_destination_enabled(destination_id: str, is_enabled: bool) -> bool:
        with get_connection() as conn:
            cursor = conn.execute(
                "UPDATE destinations SET is_enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (int(is_enabled), destination_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def delete_destination(destination_id: str) -> bool:
        with get_connection() as conn:
            conn.execute("DELETE FROM routes WHERE destination_id = ?", (destination_id,))
            cursor = conn.execute("DELETE FROM destinations WHERE id = ?", (destination_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def _destination_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        result = _row_to_dict(row) or {}
        result["config"] = _loads_json(result.pop("config_json") or "{}", {})
        result["is_enabled"] = bool(result["is_enabled"])
        return result

    @staticmethod
    def create_route(route: Dict[str, Any]) -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO routes
                (name, source, from_user, chat_id, msg_type, keyword, destination_id, template, is_enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    route.get("name"),
                    route.get("source", "wecom"),
                    route.get("from_user"),
                    route.get("chat_id"),
                    route.get("msg_type"),
                    route.get("keyword"),
                    route["destination_id"],
                    route.get("template"),
                    int(route.get("is_enabled", True)),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    @staticmethod
    def update_route(route_id: int, route: Dict[str, Any]) -> bool:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE routes
                SET name = ?, source = ?, from_user = ?, chat_id = ?, msg_type = ?,
                    keyword = ?, destination_id = ?, template = ?, is_enabled = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    route.get("name"),
                    route.get("source", "wecom"),
                    route.get("from_user"),
                    route.get("chat_id"),
                    route.get("msg_type"),
                    route.get("keyword"),
                    route["destination_id"],
                    route.get("template"),
                    int(route.get("is_enabled", True)),
                    route_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def set_route_enabled(route_id: int, is_enabled: bool) -> bool:
        with get_connection() as conn:
            cursor = conn.execute(
                "UPDATE routes SET is_enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (int(is_enabled), route_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def delete_route(route_id: int) -> bool:
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM routes WHERE id = ?", (route_id,))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def list_routes(enabled_only: bool = False) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM routes"
        if enabled_only:
            sql += " WHERE is_enabled = 1"
        sql += " ORDER BY created_at DESC"
        with get_connection() as conn:
            rows = conn.execute(sql).fetchall()
            return [_row_to_dict(row) for row in rows if row is not None]

    @staticmethod
    def find_routes_for_message(msg: UnifiedMessage) -> List[Dict[str, Any]]:
        routes = DatabaseService.list_routes(enabled_only=True)
        matched: List[Dict[str, Any]] = []
        for route in routes:
            if route.get("source") and route["source"] != msg.source:
                continue
            if route.get("from_user") and route["from_user"] != msg.from_user:
                continue
            if route.get("chat_id") and route["chat_id"] != msg.chat_id:
                continue
            if route.get("msg_type") and route["msg_type"] != msg.msg_type:
                continue
            keyword = route.get("keyword")
            if keyword and keyword not in (msg.content or ""):
                continue
            matched.append(route)
        return matched

    @staticmethod
    def delivery_is_done(source: str, msg_id: str, target_id: str) -> bool:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT status FROM deliveries
                WHERE source = ? AND msg_id = ? AND target_id = ?
                """,
                (source, msg_id, target_id),
            ).fetchone()
            return bool(row and row["status"] == "delivered")

    @staticmethod
    def record_delivery(
        source: str,
        msg_id: str,
        target_id: str,
        target_type: str,
        status: str,
        route_id: str | None = None,
        error: str | None = None,
        external_id: str | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        delivered_at = "CURRENT_TIMESTAMP" if status == "delivered" else "NULL"
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        with get_connection() as conn:
            conn.execute(
                f"""
                INSERT INTO deliveries
                (source, msg_id, target_id, target_type, route_id, status, attempts, error, external_id, metadata_json, delivered_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, {delivered_at})
                ON CONFLICT(source, msg_id, target_id) DO UPDATE SET
                    target_type = excluded.target_type,
                    route_id = excluded.route_id,
                    status = excluded.status,
                    attempts = deliveries.attempts + 1,
                    error = excluded.error,
                    external_id = excluded.external_id,
                    metadata_json = excluded.metadata_json,
                    updated_at = CURRENT_TIMESTAMP,
                    delivered_at = {delivered_at}
                """,
                (source, msg_id, target_id, target_type, route_id, status, error, external_id, metadata_json),
            )
            conn.commit()

    @staticmethod
    def list_deliveries(status: str | None = None, limit: int = 100) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM deliveries"
        params: List[Any] = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            results = []
            for row in rows:
                item = _row_to_dict(row) or {}
                item["metadata"] = _loads_json(item.pop("metadata_json") or "{}", {})
                results.append(item)
            return results

    @staticmethod
    def list_messages(
        source: str | None = None,
        from_user: str | None = None,
        chat_id: str | None = None,
        msg_type: str | None = None,
        keyword: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        limit = max(1, min(limit, 500))
        offset = max(0, offset)
        where: List[str] = []
        params: List[Any] = []
        if source:
            where.append("m.source = ?")
            params.append(source)
        if from_user:
            where.append("m.from_user = ?")
            params.append(from_user)
        if chat_id:
            where.append("m.chat_id = ?")
            params.append(chat_id)
        if msg_type:
            where.append("m.msg_type = ?")
            params.append(msg_type)
        if keyword:
            like = f"%{keyword}%"
            where.append(
                "(m.content LIKE ? OR m.msg_id LIKE ? OR m.from_user LIKE ? OR COALESCE(m.sender_name, '') LIKE ?)"
            )
            params.extend([like, like, like, like])

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        with get_connection() as conn:
            total_row = conn.execute(f"SELECT COUNT(*) FROM unified_messages m {where_sql}", params).fetchone()
            rows = conn.execute(
                f"""
                SELECT
                    m.*,
                    COALESCE(a.attachments_count, 0) AS attachments_count,
                    COALESCE(d.deliveries_total, 0) AS deliveries_total,
                    COALESCE(d.deliveries_delivered, 0) AS deliveries_delivered,
                    COALESCE(d.deliveries_failed, 0) AS deliveries_failed,
                    COALESCE(d.deliveries_pending, 0) AS deliveries_pending
                FROM unified_messages m
                LEFT JOIN (
                    SELECT source, msg_id, COUNT(*) AS attachments_count
                    FROM attachments
                    GROUP BY source, msg_id
                ) a ON a.source = m.source AND a.msg_id = m.msg_id
                LEFT JOIN (
                    SELECT
                        source,
                        msg_id,
                        COUNT(*) AS deliveries_total,
                        SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) AS deliveries_delivered,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS deliveries_failed,
                        SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS deliveries_pending
                    FROM deliveries
                    GROUP BY source, msg_id
                ) d ON d.source = m.source AND d.msg_id = m.msg_id
                {where_sql}
                ORDER BY COALESCE(m.created_at, m.updated_at) DESC, m.id DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()

        return {
            "items": [DatabaseService._message_row_to_dict(row, include_raw=False) for row in rows],
            "total": int(total_row[0] or 0),
            "limit": limit,
            "offset": offset,
        }

    @staticmethod
    def get_message_detail(source: str, msg_id: str) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM unified_messages WHERE source = ? AND msg_id = ?",
                (source, msg_id),
            ).fetchone()
            if not row:
                return None
            attachments = conn.execute(
                "SELECT * FROM attachments WHERE source = ? AND msg_id = ? ORDER BY id",
                (source, msg_id),
            ).fetchall()
            deliveries = conn.execute(
                """
                SELECT * FROM deliveries
                WHERE source = ? AND msg_id = ?
                ORDER BY updated_at DESC
                """,
                (source, msg_id),
            ).fetchall()

        delivery_items = []
        for delivery in deliveries:
            item = _row_to_dict(delivery) or {}
            item["metadata"] = _loads_json(item.pop("metadata_json") or "{}", {})
            delivery_items.append(item)

        return {
            "message": DatabaseService._message_row_to_dict(row, include_raw=True),
            "attachments": [_row_to_dict(attachment) or {} for attachment in attachments],
            "deliveries": delivery_items,
        }

    @staticmethod
    def _message_row_to_dict(row: sqlite3.Row, include_raw: bool = False) -> Dict[str, Any]:
        item = _row_to_dict(row) or {}
        if include_raw:
            item["raw_data"] = _loads_json(item.get("raw_data"), {})
        else:
            item.pop("raw_data", None)
        return item

    @staticmethod
    def get_message(source: str, msg_id: str) -> Optional[UnifiedMessage]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM unified_messages WHERE source = ? AND msg_id = ?",
                (source, msg_id),
            ).fetchone()
            if not row:
                return None
            attachments = conn.execute(
                "SELECT * FROM attachments WHERE source = ? AND msg_id = ?",
                (source, msg_id),
            ).fetchall()
        raw_data = _loads_json(row["raw_data"] or "{}", {})
        return UnifiedMessage(
            msg_id=row["msg_id"],
            source=row["source"],
            msg_type=row["msg_type"] or "unknown",
            content=row["content"] or "",
            from_user=row["from_user"] or "",
            create_time=int(datetime.fromisoformat(row["created_at"]).timestamp()) if row["created_at"] else 0,
            raw_data=raw_data,
            chat_id=row["chat_id"],
            to_user=row["to_user"],
            sender_name=row["sender_name"],
            attachments=[
                AttachmentInfo(
                    file_name=a["file_name"],
                    local_path=a["local_path"],
                    content_type=a["content_type"],
                    size=a["size"],
                    sha256=a["sha256"],
                    url=a["url"],
                )
                for a in attachments
            ],
        )

    @staticmethod
    def metrics() -> Dict[str, int]:
        with get_connection() as conn:
            def count(sql: str, params: Iterable[Any] = ()) -> int:
                row = conn.execute(sql, tuple(params)).fetchone()
                return int(row[0] or 0)

            return {
                "messages_total": count("SELECT COUNT(*) FROM unified_messages"),
                "destinations_total": count("SELECT COUNT(*) FROM destinations"),
                "routes_total": count("SELECT COUNT(*) FROM routes"),
                "deliveries_total": count("SELECT COUNT(*) FROM deliveries"),
                "deliveries_delivered": count("SELECT COUNT(*) FROM deliveries WHERE status = ?", ("delivered",)),
                "deliveries_failed": count("SELECT COUNT(*) FROM deliveries WHERE status = ?", ("failed",)),
                "deliveries_pending": count("SELECT COUNT(*) FROM deliveries WHERE status = ?", ("pending",)),
            }
