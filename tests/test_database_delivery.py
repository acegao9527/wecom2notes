import asyncio
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src.core.delivery import deliver_message
from src.core.router import MessageRouter
from src.models.chat_record import UnifiedMessage
from src.services.database import DatabaseService, init_db


class DatabaseDeliveryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        init_db(f"{self.tmp.name}/test.db")
        DatabaseService.run_migrations()

    def tearDown(self):
        self.tmp.cleanup()

    def _start_http_server(self, status: int = 201):
        records = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                records.append(
                    {
                        "path": self.path,
                        "headers": dict(self.headers),
                        "json": json.loads(body.decode("utf-8")),
                    }
                )
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("X-Request-Id", "req-http-target")
                self.end_headers()
                self.wfile.write(b'{"ok": true}')

            def log_message(self, *args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def cleanup():
            server.shutdown()
            server.server_close()
            thread.join(1)

        self.addCleanup(cleanup)
        return server, records

    def test_message_dedup_and_markdown_delivery(self):
        destination = DatabaseService.upsert_destination(
            "md",
            "Markdown",
            "markdown",
            {"root_path": f"{self.tmp.name}/notes", "mode": "daily"},
        )
        self.assertEqual(destination.id, "md")
        DatabaseService.create_route({"destination_id": "md", "source": "wecom"})
        msg = UnifiedMessage(
            msg_id="m1",
            source="wecom",
            msg_type="text",
            content="hello",
            from_user="u1",
            create_time=1700000000,
            raw_data={},
        )
        self.assertTrue(DatabaseService.save_unified_message(msg))
        self.assertFalse(DatabaseService.save_unified_message(msg))
        results = asyncio.run(deliver_message(msg))
        self.assertEqual(results[0].status, "delivered")
        self.assertTrue(DatabaseService.delivery_is_done("wecom", "m1", "md"))

    def test_legacy_craft_bindings_are_migrated_to_destinations_and_routes(self):
        with DatabaseService.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO user_mappings
                (wecom_openid, craft_link_id, craft_document_id, craft_token, display_name, is_enabled)
                VALUES ('u-craft', 'link-1', 'doc-1', 'token-1', 'Craft User', 1)
                """
            )
            conn.commit()

        stats = DatabaseService.migrate_legacy_craft_bindings()
        self.assertEqual(stats["bindings"], 1)
        self.assertEqual(stats["destinations_created"], 1)
        self.assertEqual(stats["routes_created"], 1)

        destination = DatabaseService.get_destination_record("craft:u-craft")
        self.assertIsNotNone(destination)
        self.assertEqual(destination["target_type"], "craft")
        self.assertEqual(destination["config"]["link_id"], "link-1")
        self.assertEqual(destination["config"]["document_id"], "doc-1")

        routes = DatabaseService.list_routes()
        migrated_routes = [route for route in routes if route["destination_id"] == "craft:u-craft"]
        self.assertEqual(len(migrated_routes), 1)
        self.assertEqual(migrated_routes[0]["from_user"], "u-craft")

        repeated = DatabaseService.migrate_legacy_craft_bindings()
        self.assertEqual(repeated["destinations_created"], 0)
        self.assertEqual(repeated["routes_created"], 0)

        msg = UnifiedMessage(
            msg_id="craft-msg",
            source="wecom",
            msg_type="text",
            content="hello",
            from_user="u-craft",
            create_time=1700000000,
            raw_data={},
        )
        targets = MessageRouter().resolve_targets(msg)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].id, "craft:u-craft")
        self.assertNotEqual(targets[0].route_id, "legacy-binding")

    def test_http_target_delivery_posts_message_payload(self):
        server, records = self._start_http_server()
        url = f"http://127.0.0.1:{server.server_port}/hook"
        DatabaseService.upsert_destination(
            "http-hook",
            "HTTP Hook",
            "http",
            {"url": url, "headers": {"X-Test": "yes"}, "timeout": 5},
        )
        DatabaseService.create_route({"destination_id": "http-hook", "source": "wecom"})
        msg = UnifiedMessage(
            msg_id="http-msg",
            source="wecom",
            msg_type="text",
            content="hello webhook",
            from_user="u-http",
            create_time=1700000000,
            raw_data={"hello": "world"},
        )
        self.assertTrue(DatabaseService.save_unified_message(msg))

        results = asyncio.run(deliver_message(msg))

        self.assertEqual(results[0].status, "delivered")
        self.assertEqual(results[0].external_id, "req-http-target")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["path"], "/hook")
        self.assertEqual(records[0]["headers"]["X-Test"], "yes")
        self.assertEqual(records[0]["json"]["event"], "wecom2notes.message")
        self.assertEqual(records[0]["json"]["message"]["msg_id"], "http-msg")
        self.assertEqual(records[0]["json"]["message"]["raw_data"]["hello"], "world")

    def test_migration_adds_updated_at_to_existing_unified_messages(self):
        legacy_db = f"{self.tmp.name}/legacy.db"
        init_db(legacy_db)
        with DatabaseService.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE unified_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    msg_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    msg_type TEXT,
                    from_user TEXT,
                    content TEXT,
                    raw_data TEXT,
                    created_at TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO unified_messages
                (msg_id, source, msg_type, from_user, content, raw_data, created_at)
                VALUES ('legacy-1', 'wecom', 'text', 'u1', 'hello', '{}', '2026-01-01 00:00:00')
                """
            )
            conn.commit()

        DatabaseService.run_migrations()
        with DatabaseService.get_connection() as conn:
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(unified_messages)")}
            row = conn.execute("SELECT updated_at FROM unified_messages WHERE msg_id = 'legacy-1'").fetchone()

        self.assertIn("updated_at", columns)
        self.assertIsNotNone(row["updated_at"])

    def test_admin_crud_message_search_and_detail(self):
        DatabaseService.upsert_destination(
            "admin-md",
            "Admin Markdown",
            "markdown",
            {"root_path": f"{self.tmp.name}/notes", "mode": "daily"},
        )
        self.assertEqual(len(DatabaseService.list_destinations()), 1)
        self.assertTrue(DatabaseService.set_destination_enabled("admin-md", False))
        self.assertFalse(DatabaseService.get_destination("admin-md"))
        self.assertTrue(DatabaseService.set_destination_enabled("admin-md", True))

        route_id = DatabaseService.create_route(
            {"destination_id": "admin-md", "source": "wecom", "msg_type": "text", "keyword": "hello"}
        )
        self.assertTrue(
            DatabaseService.update_route(
                route_id,
                {"destination_id": "admin-md", "source": "wecom", "msg_type": "text", "keyword": "updated"},
            )
        )

        msg = UnifiedMessage(
            msg_id="admin-msg",
            source="wecom",
            msg_type="text",
            content="updated content",
            from_user="u-admin",
            create_time=1700000000,
            raw_data={"hello": "world"},
        )
        self.assertTrue(DatabaseService.save_unified_message(msg))
        DatabaseService.record_delivery("wecom", "admin-msg", "admin-md", "markdown", "failed", error="boom")

        messages = DatabaseService.list_messages(keyword="updated")
        self.assertEqual(messages["total"], 1)
        self.assertEqual(messages["items"][0]["deliveries_failed"], 1)

        detail = DatabaseService.get_message_detail("wecom", "admin-msg")
        self.assertEqual(detail["message"]["raw_data"]["hello"], "world")
        self.assertEqual(detail["deliveries"][0]["error"], "boom")

        self.assertTrue(DatabaseService.delete_route(route_id))
        self.assertTrue(DatabaseService.delete_destination("admin-md"))


if __name__ == "__main__":
    unittest.main()
