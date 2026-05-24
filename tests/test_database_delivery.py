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


if __name__ == "__main__":
    unittest.main()
