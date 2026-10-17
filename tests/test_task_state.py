from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import tempfile
import unittest

from aimes_cli.task_state import validate_task_state


class TaskStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        subprocess.run(["git", "init", "-b", "main", str(self.root)], check=True, capture_output=True, text=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "aimes-test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "AIMES Test"], check=True)
        (self.root / "README.md").write_text("# fixture\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-m", "baseline"], check=True, capture_output=True, text=True)
        self.base_commit = subprocess.run(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True
        ).stdout.strip()
        self.state_path = self.root / ".aimes" / "project-control" / "active-writer.yaml"
        now = datetime.now(timezone.utc)
        self.state = {
            "schema_version": 1,
            "task_id": "TASK-TEST-001",
            "tool_id": "trae-code",
            "branch": "main",
            "base_commit": self.base_commit,
            "started_at": now.isoformat(),
            "lease_expires_at": (now + timedelta(hours=2)).isoformat(),
            "allowed_paths": ["src/"],
            "status": "ACTIVE",
        }
        self.write_state()

    def tearDown(self):
        self.tmp.cleanup()

    def write_state(self):
        import yaml
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(yaml.safe_dump(self.state, sort_keys=False), encoding="utf-8")

    def test_valid_active_writer_passes(self):
        result = validate_task_state(self.state_path, self.root, require_active=True)
        self.assertTrue(result["ok"], result["findings"])
        self.assertTrue(result["writer_active"])

    def test_change_outside_allowed_paths_fails(self):
        (self.root / "README.md").write_text("# changed outside scope\n", encoding="utf-8")
        result = validate_task_state(self.state_path, self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "CHANGE_OUTSIDE_SCOPE" for item in result["findings"]))

    def test_branch_mismatch_fails(self):
        self.state["branch"] = "task/other"
        self.write_state()
        result = validate_task_state(self.state_path, self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "BRANCH_MISMATCH" for item in result["findings"]))

    def test_expired_lease_cannot_satisfy_require_active(self):
        now = datetime.now(timezone.utc)
        self.state["started_at"] = (now - timedelta(hours=3)).isoformat()
        self.state["lease_expires_at"] = (now - timedelta(hours=1)).isoformat()
        self.write_state()
        result = validate_task_state(self.state_path, self.root, require_active=True)
        self.assertFalse(result["ok"])
        self.assertFalse(result["writer_active"])
        self.assertTrue(any(item["code"] == "LEASE_EXPIRED" for item in result["findings"]))

    def test_parent_traversal_in_scope_is_rejected(self):
        self.state["allowed_paths"] = ["../outside"]
        self.write_state()
        result = validate_task_state(self.state_path, self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["code"] == "ALLOWED_PATH_INVALID" for item in result["findings"]))

    def test_missing_state_is_warning_unless_active_required(self):
        self.state_path.unlink()
        optional = validate_task_state(self.state_path, self.root)
        required = validate_task_state(self.state_path, self.root, require_active=True)
        self.assertTrue(optional["ok"])
        self.assertFalse(required["ok"])


if __name__ == "__main__":
    unittest.main()
