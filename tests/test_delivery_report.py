import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from aimes_cli.cli import main
from aimes_cli.delivery_report import split_sections, validate_delivery_report

REPO_ROOT = Path(__file__).resolve().parents[1]

GOOD_REPORT = """## DELIVERY
- task_id: TASK-DEMO-001
- risk_level: R0
- report_level: R0
- project: demo
- tool_and_version: demo-tool 1.0
- base_commit: abc123
- final_commit: N/A
- result: IMPLEMENTED_UNVERIFIED

## FILES
- src/demo.py | demo change | behavior_change: yes

## VERIFICATION
- check: unittest
  command_or_test_id: python -m unittest
  exit_code_or_result: 0
  scope: tests
  evidence_path: reports/unittest.log
  commit: abc123
  status: PASS

## UNRESOLVED / RISKS
- none | N/A | N/A

## GIT_STATUS
- branch: demo
- working_tree: clean
- protected_user_changes: none

## NEXT
- verify e2e | dependency: browser
"""


def write_report(directory: str, text: str) -> Path:
    path = Path(directory) / "report.md"
    path.write_text(text, encoding="utf-8")
    return path


class DeliveryReportTests(unittest.TestCase):
    def test_good_r0_report_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            result = validate_delivery_report(write_report(directory, GOOD_REPORT))
            self.assertTrue(result["ok"], json.dumps(result["findings"], ensure_ascii=False))
            self.assertEqual(result["report"]["result"], "IMPLEMENTED_UNVERIFIED")

    def test_sections_are_split(self):
        sections = split_sections(GOOD_REPORT)
        self.assertIn("DELIVERY", sections)
        self.assertIn("UNRESOLVED / RISKS", sections)

    def test_verified_without_pass_evidence_is_error(self):
        text = GOOD_REPORT.replace("- result: IMPLEMENTED_UNVERIFIED", "- result: VERIFIED").replace("status: PASS", "status: NOT_RUN")
        with tempfile.TemporaryDirectory() as directory:
            result = validate_delivery_report(write_report(directory, text))
            self.assertFalse(result["ok"])
            codes = [item["code"] for item in result["findings"]]
            self.assertIn("VERIFIED_WITHOUT_PASS", codes)
        no_evidence = GOOD_REPORT.replace("- result: IMPLEMENTED_UNVERIFIED", "- result: VERIFIED").replace("  evidence_path: reports/unittest.log\n", "  evidence_path: N/A\n")
        with tempfile.TemporaryDirectory() as directory:
            result = validate_delivery_report(write_report(directory, no_evidence))
            codes = [item["code"] for item in result["findings"]]
            self.assertIn("PASS_WITHOUT_EVIDENCE", codes)

    def test_pass_without_command_is_error(self):
        text = GOOD_REPORT.replace("command_or_test_id: python -m unittest", "command_or_test_id: N/A")
        with tempfile.TemporaryDirectory() as directory:
            result = validate_delivery_report(write_report(directory, text))
            codes = [item["code"] for item in result["findings"]]
            self.assertIn("PASS_WITHOUT_COMMAND", codes)

    def test_report_level_below_risk_is_error(self):
        text = GOOD_REPORT.replace("- risk_level: R0", "- risk_level: R2")
        with tempfile.TemporaryDirectory() as directory:
            result = validate_delivery_report(write_report(directory, text))
            codes = [item["code"] for item in result["findings"]]
            self.assertIn("REPORT_LEVEL_BELOW_RISK", codes)
            self.assertIn("SECTION_MISSING", codes)  # R2 task requires the full section set

    def test_invalid_result_status_is_error(self):
        text = GOOD_REPORT.replace("- result: IMPLEMENTED_UNVERIFIED", "- result: 基本完成")
        with tempfile.TemporaryDirectory() as directory:
            result = validate_delivery_report(write_report(directory, text))
            codes = [item["code"] for item in result["findings"]]
            self.assertIn("RESULT_INVALID", codes)

    def test_example_report_is_structurally_valid(self):
        result = validate_delivery_report(REPO_ROOT / "examples/delivery/delivery-report.example.md", REPO_ROOT)
        self.assertTrue(result["ok"], json.dumps(result["findings"], ensure_ascii=False))

    def test_cli_delivery_validate_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_report(directory, GOOD_REPORT)
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["delivery", "validate", str(path), "--root", directory, "--format", "json"])
            self.assertEqual(code, 0)
            buffer.seek(0); buffer.truncate(0)
            bad = write_report(directory, GOOD_REPORT.replace("## NEXT", "## UNRESOLVED / RISKS\n\n## NEXT"))
            with redirect_stdout(buffer):
                code = main(["delivery", "validate", str(bad), "--root", directory])
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
