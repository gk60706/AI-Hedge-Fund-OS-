import tempfile
import unittest
from pathlib import Path

from ai_team.adapters import load_env_file


class TestLoadEnvFile(unittest.TestCase):
    def test_parses_utf8_bom_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_bytes(
                "\ufeffOPENAI_API_KEY=test-key\nOTHER=value\n".encode("utf-8")
            )
            result = load_env_file(path)
            self.assertEqual(result["OPENAI_API_KEY"], "test-key")
            self.assertEqual(result["OTHER"], "value")

    def test_parses_file_without_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text(
                "OPENAI_API_KEY=test-key\nOTHER=value\n",
                encoding="utf-8",
            )
            result = load_env_file(path)
            self.assertEqual(result["OPENAI_API_KEY"], "test-key")
            self.assertEqual(result["OTHER"], "value")


if __name__ == "__main__":
    unittest.main()
