import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from aimes_cli.code_repair import apply_patch, inspect_patch, propose_patch, rollback_patch, verify_patch


class CodeRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root / "src" / "module.py"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("VALUE = 1\n", encoding="utf-8")
        self.patch_path = self.root / "candidate.patch"
        self.patch_path.write_text(
            "diff --git a/src/module.py b/src/module.py\n"
            "index 6c2e3b1..d3d8e1a 100644\n"
            "--- a/src/module.py\n"
            "+++ b/src/module.py\n"
            "@@ -1 +1 @@\n"
            "-VALUE = 1\n"
            "+VALUE = 2\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_proposal_does_not_modify_business_file(self):
        result = propose_patch(self.root, self.patch_path, repair_id="fix-001", finding="TEST-1", rationale="correct value")
        self.assertEqual(result["status"], "PROPOSED")
        self.assertEqual(self.source.read_text(encoding="utf-8"), "VALUE = 1\n")
        self.assertTrue((self.root / ".aimes/repairs/fix-001/change.patch").is_file())

    def test_apply_requires_explicit_confirmation_and_checks_preimage(self):
        propose_patch(self.root, self.patch_path, repair_id="fix-002", finding="TEST-2")
        with self.assertRaisesRegex(ValueError, "APPLY-FIX"):
            apply_patch(self.root, "fix-002", confirm="no")
        self.assertEqual(self.source.read_text(encoding="utf-8"), "VALUE = 1\n")
        self.source.write_text("VALUE = 3\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "发生变化"):
            apply_patch(self.root, "fix-002", confirm="apply-fix")

    def test_apply_verify_and_rollback(self):
        propose_patch(self.root, self.patch_path, repair_id="fix-003", finding="TEST-3")
        applied = apply_patch(self.root, "fix-003", confirm="APPLY-FIX")
        self.assertEqual(applied["status"], "APPLIED")
        self.assertEqual(self.source.read_text(encoding="utf-8"), "VALUE = 2\n")
        verify = verify_patch(self.root, "fix-003", test_argv_json=json.dumps([sys.executable, "-c", "raise SystemExit(0)"]))
        self.assertEqual(verify["status"], "PASS")
        rolled = rollback_patch(self.root, "fix-003", confirm="rollback-fix")
        self.assertEqual(rolled["status"], "ROLLED_BACK")
        self.assertEqual(self.source.read_text(encoding="utf-8"), "VALUE = 1\n")

    def test_failed_verification_is_recorded_not_reported_as_success(self):
        propose_patch(self.root, self.patch_path, repair_id="fix-004", finding="TEST-4")
        apply_patch(self.root, "fix-004", confirm="APPLY-FIX")
        verify = verify_patch(self.root, "fix-004", test_argv_json=json.dumps([sys.executable, "-c", "raise SystemExit(7)"]))
        self.assertFalse(verify["ok"])
        self.assertEqual(verify["status"], "FAIL")
        manifest = json.loads((self.root / ".aimes/repairs/fix-004/proposal.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "VERIFICATION_FAILED")

    def test_rejects_path_escape_and_deletion(self):
        escape = self.root / "escape.patch"
        escape.write_text(
            "diff --git a/../outside.txt b/../outside.txt\n"
            "--- a/../outside.txt\n+++ b/../outside.txt\n@@ -1 +1 @@\n-a\n+b\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "不安全"):
            propose_patch(self.root, escape, repair_id="fix-005", finding="TEST-5")
        deletion = self.root / "delete.patch"
        deletion.write_text(
            "diff --git a/src/module.py b/src/module.py\n"
            "--- a/src/module.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-VALUE = 1\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "删除"):
            propose_patch(self.root, deletion, repair_id="fix-006", finding="TEST-6")

    def test_rollback_refuses_to_overwrite_changes_made_after_apply(self):
        propose_patch(self.root, self.patch_path, repair_id="fix-007", finding="TEST-7")
        apply_patch(self.root, "fix-007", confirm="APPLY-FIX")
        self.source.write_text("VALUE = 99\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "拒绝回滚"):
            rollback_patch(self.root, "fix-007", confirm="ROLLBACK-FIX")
        self.assertEqual(self.source.read_text(encoding="utf-8"), "VALUE = 99\n")


    def test_inspect_reports_proposed_state_and_safe_next_actions(self):
        propose_patch(self.root, self.patch_path, repair_id="fix-inspect-1", finding="TEST-INSPECT")
        result = inspect_patch(self.root, "fix-inspect-1")
        self.assertTrue(result["ok"])
        self.assertTrue(result["read_only"])
        self.assertEqual(result["status"], "PROPOSED")
        self.assertTrue(result["patch_integrity_ok"])
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["next_actions"][0]["id"], "review")
        self.assertEqual(self.source.read_text(encoding="utf-8"), "VALUE = 1\\n")

    def test_inspect_detects_preimage_and_patch_tampering(self):
        propose_patch(self.root, self.patch_path, repair_id="fix-inspect-2", finding="TEST-INSPECT")
        self.source.write_text("VALUE = 9\\n", encoding="utf-8")
        patch = self.root / ".aimes/repairs/fix-inspect-2/change.patch"
        patch.write_text(patch.read_text(encoding="utf-8") + "# tampered\\n", encoding="utf-8")
        result = inspect_patch(self.root, "fix-inspect-2")
        self.assertFalse(result["patch_integrity_ok"])
        self.assertIn("PATCH_HASH_MISMATCH", {issue["code"] for issue in result["issues"]})
        self.assertIn("PREIMAGE_CHANGED", {issue["code"] for issue in result["issues"]})

    def test_inspect_after_verification_points_to_acceptance_not_false_completion(self):
        propose_patch(self.root, self.patch_path, repair_id="fix-inspect-3", finding="TEST-INSPECT")
        apply_patch(self.root, "fix-inspect-3", confirm="APPLY-FIX")
        verify_patch(self.root, "fix-inspect-3", test_argv_json=json.dumps([sys.executable, "-c", "raise SystemExit(0)"]))
        result = inspect_patch(self.root, "fix-inspect-3")
        self.assertEqual(result["status"], "VERIFIED")
        self.assertTrue(any(item["id"] == "acceptance" for item in result["next_actions"]))
        self.assertIn("不代表任务最终验收通过", result["note"])

if __name__ == "__main__":
    unittest.main()
