import unittest

from src.models.chat_record import UnifiedMessage
from src.services.formatter import format_unified_message_as_craft_blocks


class FormatterTest(unittest.TestCase):
    def test_link_formats_to_rich_url(self):
        msg = UnifiedMessage(
            msg_id="m1",
            source="wecom",
            msg_type="link",
            content="https://example.com",
            from_user="u1",
            create_time=1700000000,
        )
        blocks = format_unified_message_as_craft_blocks(msg)
        self.assertEqual(blocks[0]["type"], "richUrl")


if __name__ == "__main__":
    unittest.main()
