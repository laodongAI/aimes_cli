import unittest
from types import SimpleNamespace
from unittest.mock import patch

from aimes_cli.runtime_detect import detect_adapters
from aimes_cli.cli import parser


class RuntimeDetectionTests(unittest.TestCase):
    @patch("aimes_cli.runtime_detect.shutil.which", return_value=None)
    def test_missing_command_is_reported_without_failing_detection(self, _which):
        result = detect_adapters(["codex-cli"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["adapters"][0]["availability"], "not_found")
        self.assertEqual(result["adapters"][0]["commands"][0]["version_status"], "not_available")

    @patch("aimes_cli.runtime_detect.subprocess.run")
    @patch("aimes_cli.runtime_detect.shutil.which", return_value="/usr/local/bin/codex")
    def test_available_cli_reports_version_without_starting_interactive_session(self, _which, run):
        run.return_value = SimpleNamespace(returncode=0, stdout="codex 1.2.3\n", stderr="")
        result = detect_adapters(["codex-cli"])
        self.assertEqual(result["adapters"][0]["availability"], "available")
        self.assertEqual(result["adapters"][0]["commands"][0]["version"], "codex 1.2.3")
        self.assertEqual(run.call_args.args[0], ["/usr/local/bin/codex", "--version"])
        self.assertEqual(run.call_args.kwargs["timeout"], 4)
        self.assertFalse(run.call_args.kwargs.get("shell", False))

    @patch("aimes_cli.runtime_detect.subprocess.run")
    @patch("aimes_cli.runtime_detect.shutil.which", return_value="/opt/trae")
    def test_ide_launcher_is_discovery_only(self, _which, run):
        result = detect_adapters(["trae-code"])
        command = result["adapters"][0]["commands"][0]
        self.assertTrue(command["available"])
        self.assertEqual(command["version_status"], "skipped_non_cli")
        run.assert_not_called()

    @patch("aimes_cli.runtime_detect.shutil.which", return_value="/tools/codex.cmd")
    def test_windows_script_launcher_is_not_invoked_through_shell(self, _which):
        result = detect_adapters(["codex-cli"])
        command = result["adapters"][0]["commands"][0]
        self.assertTrue(command["available"])
        self.assertEqual(command["version_status"], "skipped_windows_script")

    @patch("aimes_cli.runtime_detect.subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("codex", 4))
    @patch("aimes_cli.runtime_detect.shutil.which", return_value="/usr/local/bin/codex")
    def test_version_timeout_does_not_abort_other_detection(self, _which, _run):
        result = detect_adapters(["codex-cli"])
        self.assertEqual(result["adapters"][0]["commands"][0]["version_status"], "timeout")

    def test_workspace_adapter_is_explicitly_not_detectable(self):
        result = detect_adapters(["chatgpt-work"])
        self.assertEqual(result["adapters"][0]["availability"], "not_detectable")
        self.assertEqual(result["summary"]["not_detectable"], 1)

    def test_cli_parser_supports_filtered_json_detection(self):
        args = parser().parse_args(["adapter", "detect", "--tool", "codex-cli", "--format", "json"])
        self.assertEqual(args.adapter_command, "detect")
        self.assertEqual(args.tool, ["codex-cli"])
        self.assertEqual(args.format, "json")


if __name__ == "__main__":
    unittest.main()
