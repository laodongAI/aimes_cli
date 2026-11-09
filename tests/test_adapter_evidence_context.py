import tempfile
import unittest
import io
from contextlib import redirect_stdout
from pathlib import Path

import yaml

from aimes_cli.v05 import validate_adapter_evidence, adapter_report
from aimes_cli.cli import emit


class AdapterEvidenceContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.path = self.root / "evidence.yaml"

    def tearDown(self):
        self.tmp.cleanup()

    def write_record(self, **overrides):
        check = {
            "id": "EVIDENCE-001",
            "tool": "codex-cli",
            "host_id": "terminal",
            "harness_id": "codex",
            "adapter_registry_version": "2.0.0",
            "verification": "NOT_RUN",
            "method": "file_inspection",
        }
        check.update(overrides)
        self.path.write_text(yaml.safe_dump({"schema_version": 2, "checks": [check]}, sort_keys=False), encoding="utf-8")

    def test_registered_host_and_harness_are_accepted(self):
        self.write_record()
        result = validate_adapter_evidence(self.path, self.root)
        self.assertTrue(result["ok"], result["findings"])

    def test_mismatched_host_is_rejected(self):
        self.write_record(host_id="vscode")
        result = validate_adapter_evidence(self.path, self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "ADAPTER_CONTEXT_MISMATCH" for item in result["findings"]))

    def test_mismatched_harness_is_rejected(self):
        self.write_record(harness_id="claude-code")
        result = validate_adapter_evidence(self.path, self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "ADAPTER_CONTEXT_MISMATCH" for item in result["findings"]))

    def test_report_aggregates_multiple_hosts_under_same_harness(self):
        checks = [
            {"id": "CLI-001", "tool": "codex-cli", "host_id": "terminal", "harness_id": "codex", "verification": "NOT_RUN", "method": "file_inspection"},
            {"id": "IDE-001", "tool": "vscode-codex", "host_id": "vscode", "harness_id": "codex", "verification": "NOT_RUN", "method": "file_inspection"},
        ]
        self.path.write_text(yaml.safe_dump({"schema_version": 2, "checks": checks}, sort_keys=False), encoding="utf-8")
        report = adapter_report(self.path, self.root)
        self.assertEqual(report["harnesses"]["codex"]["checks"], 2)
        self.assertEqual(report["hosts"]["terminal"]["checks"], 1)
        self.assertEqual(report["hosts"]["vscode"]["checks"], 1)

    def test_text_report_shows_host_and_harness_aggregates(self):
        report = {
            "ok": True,
            "hosts": {"terminal": {"checks": 1, "pass": 0, "fail": 0, "blocked": 0, "not_run": 1, "unknown": 0}},
            "harnesses": {"codex": {"checks": 1, "pass": 0, "fail": 0, "blocked": 0, "not_run": 1, "unknown": 0}},
        }
        output = io.StringIO()
        with redirect_stdout(output):
            emit(report)
        self.assertIn("Host verification summary", output.getvalue())
        self.assertIn("Harness verification summary", output.getvalue())

    def test_legacy_evidence_without_host_harness_remains_compatible(self):
        self.write_record(host_id=None, harness_id=None, adapter_registry_version=None)
        result = validate_adapter_evidence(self.path, self.root)
        self.assertTrue(result["ok"], result["findings"])


if __name__ == "__main__":
    unittest.main()
