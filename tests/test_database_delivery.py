import asyncio
import tempfile
import unittest

from src.core.delivery import deliver_message
from src.models.chat_record import UnifiedMessage
from src.services.database import DatabaseService, init_db


class DatabaseDeliveryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        init_db(f"{self.tmp.name}/test.db")
        DatabaseService.run_migrations()

    def tearDown(self):
        self.tmp.cleanup()

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


if __name__ == "__main__":
    unittest.main()
