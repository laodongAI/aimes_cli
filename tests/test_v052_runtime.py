import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from aimes_cli.audit import append_event, validate_audit
from aimes_cli.cli import parser, main
from aimes_cli.mock_runner import run_mock

ROOT = Path(__file__).resolve().parents[1]

class V052RuntimeTests(unittest.TestCase):
    def test_mock_runner_is_explicitly_not_model_evaluation(self):
        result = run_mock(ROOT / "examples/evaluation/prompt-optimization-suite.yaml", ROOT / "examples/evaluation/mock-responses.yaml", [
            "EVAL-PROMPT-ONB-001", "EVAL-PROMPT-REQ-001", "EVAL-PROMPT-TEST-001",
            "EVAL-PROMPT-SEC-001", "EVAL-PROMPT-REQ-002", "EVAL-PROMPT-ARCH-002"
        ])
        self.assertEqual(len(result["case_results"]), 6)
        self.assertTrue(all(x["status"] == "PASS" for x in result["case_results"]), result)
        self.assertFalse(result["metadata"]["model_evaluation"])
        self.assertEqual(result["metadata"]["execution_mode"], "MOCK_FIXTURE")

    def test_audit_redacts_sensitive_fields_and_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            event = append_event(path, run_id="run-1", event_type="tool.completed", status="PASS",
                                 details={"api_key": "secret-value", "summary": "authorization: Bearer abc123"})
            self.assertEqual(event["details"]["api_key"], "[REDACTED]")
            stored = path.read_text(encoding="utf-8")
            self.assertNotIn("secret-value", stored)
            self.assertNotIn("Bearer abc123", stored)
            self.assertNotIn("abc123", stored)
            self.assertTrue(validate_audit(path)["ok"])

    def test_mock_runner_detects_missing_required_phrase(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixtures = Path(tmp) / "responses.yaml"
            fixtures.write_text("responses:\n  EVAL-PROMPT-ONB-001:\n    text: 'nothing relevant'\n", encoding="utf-8")
            result = run_mock(ROOT / "examples/evaluation/prompt-optimization-suite.yaml", fixtures, ["EVAL-PROMPT-ONB-001"])
            self.assertEqual(result["case_results"][0]["status"], "FAIL")
            self.assertTrue(result["case_results"][0]["diagnostics"]["missing_required_phrases"])

    def test_audit_detects_invalid_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.jsonl"
            path.write_text("{bad json}\n", encoding="utf-8")
            report = validate_audit(path)
            self.assertFalse(report["ok"])
            self.assertEqual(report["findings"][0]["code"], "AUDIT_JSONL_INVALID")

    def test_cli_contract_has_new_stable_commands(self):
        args = parser().parse_args(["evaluation", "run-mock", "suite.yaml", "--responses", "responses.yaml", "--format", "json"])
        self.assertEqual(args.evaluation_command, "run-mock")
        self.assertEqual(args.format, "json")
        audit_args = parser().parse_args(["audit", "validate", "events.jsonl", "--format", "json"])
        self.assertEqual(audit_args.audit_command, "validate")

    def test_friendly_json_parse_error_has_location_and_advice(self):
        from aimes_cli.validators import _load
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.json"
            path.write_text('{"x": }', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "第 1 行，第 7 列.*检查逗号"):
                _load(path)

if __name__ == "__main__":
    unittest.main()
