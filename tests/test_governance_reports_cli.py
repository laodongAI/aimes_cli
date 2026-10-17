import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from aimes_cli.cli import main


class GovernanceReportCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "README.md").write_text("# Project\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_cleanup_audit_cli_is_read_only_and_advisory_without_registry(self):
        candidate = self.root / "pip-install-demo"
        candidate.mkdir()
        marker = candidate / "marker.txt"
        marker.write_text("preserve", encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["cleanup", "audit", "--root", str(self.root), "--format", "json"])
        self.assertEqual(code, 0)
        self.assertIn("REGISTRY_MISSING", output.getvalue())
        self.assertTrue(marker.is_file())

    def test_metrics_cli_reports_unknown_when_sources_are_missing(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["metrics", "report", "--root", str(self.root), "--format", "json"])
        self.assertEqual(code, 0)
        self.assertIn('"metrics_unknown": 9', output.getvalue())


if __name__ == "__main__":
    unittest.main()
