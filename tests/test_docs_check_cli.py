import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from aimes_cli.cli import main


class DocsCheckCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "docs" / "_governance").mkdir(parents=True)
        (self.root / "docs" / "_governance" / "AIMES-CORE-V1.2.md").write_text("# Core\n", encoding="utf-8")
        (self.root / "AGENTS.md").write_text("Read docs/_governance/AIMES-CORE-V1.2.md\n", encoding="utf-8")
        (self.root / "README.md").write_text("[Core](docs/_governance/AIMES-CORE-V1.2.md)\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_docs_check_command_returns_zero_for_clean_project(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["docs", "check", "--root", str(self.root), "--format", "json"])
        self.assertEqual(code, 0)
        self.assertIn('"validator": "aimes-docs-check"', output.getvalue())

    def test_docs_check_command_returns_one_for_broken_link(self):
        (self.root / "README.md").write_text("[Broken](missing.md)\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(["docs", "check", "--root", str(self.root), "--format", "json"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
