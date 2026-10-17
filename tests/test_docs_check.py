from pathlib import Path
import tempfile
import unittest

from aimes_cli.docs_check import check_docs


class DocsCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "docs" / "_governance").mkdir(parents=True)
        (self.root / "docs" / "_governance" / "AIMES-CORE-V1.2.md").write_text("# Core\n", encoding="utf-8")
        (self.root / "AGENTS.md").write_text(
            "Read docs/_governance/AIMES-CORE-V1.2.md before changes.\n", encoding="utf-8"
        )
        (self.root / "README.md").write_text("# Readme\n\n[Core](docs/_governance/AIMES-CORE-V1.2.md)\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_docs_and_thin_entry_pass(self):
        result = check_docs(self.root)
        self.assertTrue(result["ok"], result["findings"])
        self.assertEqual(result["summary"]["entry_files_checked"], 1)
        self.assertEqual(result["summary"]["local_links_checked"], 1)

    def test_broken_local_link_fails(self):
        (self.root / "README.md").write_text("[Missing](docs/nope.md)\n", encoding="utf-8")
        result = check_docs(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "BROKEN_LINK" for item in result["findings"]))

    def test_missing_core_reference_fails(self):
        (self.root / "AGENTS.md").write_text("# Full copied rules\n", encoding="utf-8")
        result = check_docs(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "CORE_REFERENCE_MISSING" for item in result["findings"]))

    def test_oversized_entry_fails(self):
        (self.root / "AGENTS.md").write_text(
            "docs/_governance/AIMES-CORE-V1.2.md\n" + "extra\n" * 40, encoding="utf-8"
        )
        result = check_docs(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "ENTRY_TOO_LONG" for item in result["findings"]))

    def test_configured_missing_entry_fails(self):
        (self.root / ".aimes").mkdir()
        (self.root / ".aimes" / "config.yaml").write_text(
            "governance:\n  core: docs/_governance/AIMES-CORE-V1.2.md\n"
            "tools:\n  - id: codex-cli\n    entry_paths: [AGENTS.md, MISSING.md]\n",
            encoding="utf-8",
        )
        result = check_docs(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "ENTRY_MISSING" for item in result["findings"]))

    def test_external_links_are_ignored(self):
        (self.root / "README.md").write_text(
            "[External](https://example.com/not-local)\n[Email](mailto:test@example.com)\n",
            encoding="utf-8",
        )
        result = check_docs(self.root)
        self.assertTrue(result["ok"], result["findings"])
        self.assertEqual(result["summary"]["local_links_checked"], 0)


if __name__ == "__main__":
    unittest.main()
