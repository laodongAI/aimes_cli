import tempfile
import unittest
from pathlib import Path

from aimes_cli.quality_context import build_review_context


class ReviewContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "src").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "src" / "secrets").mkdir()
        (self.root / "src" / "main.py").write_text("def hello():\n    return 'hello'\n", encoding="utf-8")
        (self.root / "src" / ".env").write_text("API_KEY=do-not-include", encoding="utf-8")
        (self.root / "src" / "secrets" / "config.py").write_text("password = 'nested-secret'", encoding="utf-8")
        (self.root / ".env").write_text("SECRET=do-not-include", encoding="utf-8")
        (self.root / "README.md").write_text("# Demo project\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_includes_source_and_root_guidance(self):
        result = build_review_context(self.root)
        paths = {item["path"] for item in result["files"]}
        self.assertIn("src/main.py", paths)
        self.assertIn("README.md", paths)
        self.assertIn("evidence.excerpt", result["prompt"])

    def test_excludes_env_files_and_secret_content(self):
        result = build_review_context(self.root)
        rendered = str(result)
        self.assertNotIn("do-not-include", rendered)
        self.assertNotIn("nested-secret", rendered)
        self.assertNotIn(".env", {item["path"] for item in result["files"]})

    def test_applies_per_file_size_limit(self):
        (self.root / "src" / "large.py").write_text("x" * 9000, encoding="utf-8")
        result = build_review_context(self.root)
        self.assertEqual(result["skipped"]["per_file_limit"], 1)

    def test_skips_symlink_files(self):
        target = self.root / "outside.py"
        target.write_text("secret = True", encoding="utf-8")
        link = self.root / "src" / "linked.py"
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("Symlinks are unavailable on this platform")
        result = build_review_context(self.root)
        self.assertNotIn("src/linked.py", {item["path"] for item in result["files"]})


if __name__ == "__main__":
    unittest.main()
