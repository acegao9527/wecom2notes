import tempfile
import unittest
from pathlib import Path

from src.importers.batch import load_messages


class ImporterTest(unittest.TestCase):
    def test_markdown_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.md"
            path.write_text("# hello", encoding="utf-8")
            messages = load_messages(str(path))
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0].content, "# hello")


if __name__ == "__main__":
    unittest.main()
