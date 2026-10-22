import json
import sys
import tempfile
import unittest
from pathlib import Path

from aimes_cli.code_repair import diagnose_command


class CodeRepairDiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def test_successful_command_is_recorded_without_claiming_project_acceptance(self):
        result = diagnose_command(self.root, diagnostic_id="diag-001",
            test_argv_json=json.dumps([sys.executable, "-c", "print('ok')"]))
        self.assertTrue(result["ok"])
        self.assertEqual(result["finding"]["code"], "NO_FAILURE_DETECTED")
        self.assertIn("原始问题", result["note"])
        self.assertTrue(Path(result["report_path"]).is_file())

    def test_assertion_failure_provides_guidance_and_patch_option(self):
        result = diagnose_command(self.root, diagnostic_id="diag-002",
            test_argv_json=json.dumps([sys.executable, "-c", "raise AssertionError('expected value')"]))
        self.assertFalse(result["ok"])
        self.assertEqual(result["finding"]["code"], "ASSERTION_FAILURE")
        self.assertTrue(any(item["id"] == "propose-patch" for item in result["recommendations"]))
        self.assertEqual(result["status"], "FAIL")

    def test_launch_error_is_recorded(self):
        result = diagnose_command(self.root, diagnostic_id="diag-003",
            test_argv_json=json.dumps(["/definitely/missing/aimes-test-command"]))
        self.assertFalse(result["ok"])
        self.assertEqual(result["finding"]["code"], "COMMAND_LAUNCH_FAILED")

    def test_duplicate_diagnostic_id_does_not_overwrite(self):
        diagnose_command(self.root, diagnostic_id="diag-004",
            test_argv_json=json.dumps([sys.executable, "-c", "print('first')"]))
        with self.assertRaisesRegex(ValueError, "拒绝覆盖"):
            diagnose_command(self.root, diagnostic_id="diag-004",
                test_argv_json=json.dumps([sys.executable, "-c", "print('second')"]))


if __name__ == "__main__":
    unittest.main()
