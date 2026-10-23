import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aimes_cli.core import init_project, proposed_files
from aimes_cli.version_audit import audit_project_version


class ProjectVersionAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        result = init_project(self.root, ["codex-cli"])
        self.assertTrue(result["ok"], result)

    def tearDown(self):
        self.tmp.cleanup()

    def test_fresh_project_has_all_current_managed_files(self):
        report = audit_project_version(self.root)
        self.assertEqual(report["status"], "CURRENT", report)
        self.assertTrue(report["ok"])
        self.assertEqual(report["summary"]["expected"], report["summary"]["current"])
        self.assertEqual(report["summary"]["missing"], 0)

    def test_user_modified_file_is_reported_without_overwrite(self):
        target = self.root / "AGENTS.md"
        target.write_text("custom user instruction\n", encoding="utf-8")
        report = audit_project_version(self.root)
        self.assertEqual(report["status"], "CUSTOMIZED")
        self.assertIn("AGENTS.md", report["modified_files"])
        self.assertEqual(target.read_text(encoding="utf-8"), "custom user instruction\n")

    def test_missing_managed_file_is_reported(self):
        (self.root / "AGENTS.md").unlink()
        report = audit_project_version(self.root)
        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertIn("AGENTS.md", report["missing_files"])

    def test_manifest_version_mismatch_is_detected_even_when_files_match(self):
        path = self.root / ".aimes/manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["aimes_cli_version"] = "0.8.4"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report = audit_project_version(self.root)
        self.assertEqual(report["status"], "UPDATE_AVAILABLE")
        self.assertEqual(report["project_cli_version"], "0.8.4")

    def test_unchanged_old_managed_file_is_classified_as_outdated(self):
        expected = proposed_files(self.root, ["codex-cli"], "project")
        expected["AGENTS.md"] = "# changed upstream template\n"
        with patch("aimes_cli.version_audit.proposed_files", return_value=expected):
            report = audit_project_version(self.root)
        self.assertEqual(report["status"], "UPDATE_AVAILABLE")
        self.assertIn("AGENTS.md", report["outdated_files"])

    def test_manifest_path_escape_is_reported_and_not_read(self):
        path = self.root / ".aimes/manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["managed_files"].append({"path": "../../outside-secret.txt", "sha256": "0" * 64, "status": "managed"})
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report = audit_project_version(self.root)
        self.assertTrue(any(item["code"] == "AIMES_MANIFEST_PATH_UNSAFE" for item in report["findings"]))
        self.assertNotIn("../../outside-secret.txt", report["extra_managed_files"])

    def test_cli_command_is_registered(self):
        from aimes_cli.cli import parser
        args = parser().parse_args(["version-audit", "--root", str(self.root), "--format", "json"])
        self.assertEqual(args.command, "version-audit")
        self.assertEqual(args.root, self.root)


if __name__ == "__main__":
    unittest.main()
