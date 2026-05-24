import os
import tempfile
import unittest

from src.services.wecom import parse_wecom_message


class WeComParserTest(unittest.TestCase):
    def test_text_url_becomes_link(self):
        msg = parse_wecom_message(
            {
                "msgid": "m1",
                "from": "u1",
                "to": "u2",
                "msgtime": 1700000000000,
                "msgtype": "text",
                "text": {"content": "https://example.com"},
            }
        )
        self.assertIsNotNone(msg)
        self.assertEqual(msg.msg_type, "link")
        self.assertEqual(msg.content, "https://example.com")
        self.assertEqual(msg.to_user, "u2")

    def test_file_attachment_uses_downloaded_path(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"data")
            path = f.name
        try:
            raw = {
                "msgid": "m2",
                "from": "u1",
                "msgtime": 1700000000,
                "msgtype": "file",
                "file": {"sdkfileid": "sdk", "filename": "a.txt", "fileext": "txt"},
            }
            original = __import__("src.services.wecom", fromlist=["download_image"]).download_image
            import src.services.wecom as wecom

            wecom.download_image = lambda *args, **kwargs: path
            msg = parse_wecom_message(raw)
            self.assertEqual(msg.content, path)
            self.assertEqual(msg.attachments[0].file_name, "a.txt")
        finally:
            import src.services.wecom as wecom

            wecom.download_image = original
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
