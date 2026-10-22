from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from aimes_cli.branch_lifecycle import inspect_branches, cleanup_merged_local_branches


def run_git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class BranchLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        run_git(self.root, "init", "-b", "main")
        run_git(self.root, "config", "user.name", "AIMES Tests")
        run_git(self.root, "config", "user.email", "aimes-tests@example.invalid")
        (self.root / "README.md").write_text("test\n", encoding="utf-8")
        run_git(self.root, "add", "README.md")
        run_git(self.root, "commit", "-m", "initial")
        self.remote = Path(self.temp.name) / "remote.git"
        subprocess.run(["git", "init", "--bare", str(self.remote)], check=True, capture_output=True, text=True)
        run_git(self.root, "remote", "add", "origin", str(self.remote))
        run_git(self.root, "push", "-u", "origin", "main")
        run_git(self.root, "fetch", "origin")
        run_git(self.root, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
        run_git(self.root, "branch", "feature-merged")
        run_git(self.root, "branch", "feature-unmerged")
        (self.root / "new.txt").write_text("unmerged\n", encoding="utf-8")
        run_git(self.root, "add", "new.txt")
        run_git(self.root, "commit", "-m", "unmerged change")
        run_git(self.root, "checkout", "main")

    def tearDown(self):
        self.temp.cleanup()

    def test_inspect_is_read_only_and_lists_only_merged_cleanup_candidates(self):
        before = set(run_git(self.root, "branch", "--format=%(refname:short)").splitlines())
        result = inspect_branches(self.root)
        after = set(run_git(self.root, "branch", "--format=%(refname:short)").splitlines())
        self.assertTrue(result["ok"])
        self.assertEqual(before, after)
        self.assertEqual(result["default_remote_ref"], "origin/main")
        self.assertIn("feature-merged", result["local_cleanup_candidates"])
        self.assertNotIn("feature-unmerged", result["local_cleanup_candidates"])
        self.assertNotIn("main", result["local_cleanup_candidates"])

    def test_cleanup_preview_never_deletes(self):
        result = cleanup_merged_local_branches(self.root)
        self.assertEqual(result["mode"], "preview")
        self.assertEqual(result["deleted"], [])
        self.assertEqual(run_git(self.root, "branch", "--format=%(refname:short)").splitlines().count("feature-merged"), 1)
        self.assertFalse(result["remote_branches_deleted"])

    def test_apply_requires_case_insensitive_confirmation_and_deletes_only_merged_local(self):
        with self.assertRaises(ValueError):
            cleanup_merged_local_branches(self.root, apply=True, confirm="no")
        result = cleanup_merged_local_branches(self.root, apply=True, confirm="delete-branches")
        branches = run_git(self.root, "branch", "--format=%(refname:short)").splitlines()
        self.assertTrue(result["ok"])
        self.assertIn("feature-merged", result["deleted"])
        self.assertNotIn("feature-merged", branches)
        self.assertIn("feature-unmerged", branches)
        self.assertIn("main", branches)
        self.assertFalse(result["remote_branches_deleted"])


if __name__ == "__main__":
    unittest.main()
