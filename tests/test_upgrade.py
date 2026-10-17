import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aimes_cli.core import init_project
from aimes_cli.upgrade import apply_upgrade, plan_upgrade


class SafeUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        init_project(self.root, ["codex-cli", "claude-code"])

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_is_read_only_and_lists_managed_updates_and_new_files(self):
        agents = self.root / "AGENTS.md"
        claude = self.root / "CLAUDE.md"
        proposed = {
            "AGENTS.md": agents.read_text(encoding="utf-8") + "\n# new managed line\n",
            "CLAUDE.md": "# upgraded Claude instructions\n",
            "new-rules.md": "# new file\n",
            ".aimes/config.yaml": (self.root / ".aimes/config.yaml").read_text(encoding="utf-8"),
            ".aimes/tool-capabilities.yaml": (self.root / ".aimes/tool-capabilities.yaml").read_text(encoding="utf-8"),
            ".aimes/adapters/README.md": (self.root / ".aimes/adapters/README.md").read_text(encoding="utf-8"),
        }
        with patch("aimes_cli.upgrade.proposed_files", return_value=proposed):
            plan = plan_upgrade(self.root)
        self.assertTrue(plan["ok"])
        self.assertFalse((self.root / "new-rules.md").exists())
        actions = {item["path"]: item["action"] for item in plan["actions"]}
        self.assertEqual(actions["AGENTS.md"], "update-managed")
        self.assertEqual(actions["CLAUDE.md"], "update-managed")
        self.assertEqual(actions["new-rules.md"], "add")

    def test_user_modified_file_is_preserved_and_candidate_is_written(self):
        agents = self.root / "AGENTS.md"
        agents.write_text("# project-specific custom rules\n", encoding="utf-8")
        original = agents.read_text(encoding="utf-8")
        proposed = {
            "AGENTS.md": "# upstream template update\n",
            ".aimes/config.yaml": (self.root / ".aimes/config.yaml").read_text(encoding="utf-8"),
            ".aimes/tool-capabilities.yaml": (self.root / ".aimes/tool-capabilities.yaml").read_text(encoding="utf-8"),
            ".aimes/adapters/README.md": (self.root / ".aimes/adapters/README.md").read_text(encoding="utf-8"),
        }
        with patch("aimes_cli.upgrade.proposed_files", return_value=proposed):
            plan = plan_upgrade(self.root)
            self.assertEqual(next(x for x in plan["actions"] if x["path"] == "AGENTS.md")["action"], "conflict-preserve")
            result = apply_upgrade(self.root, ["AGENTS.md"])
        self.assertTrue(result["ok"], result)
        self.assertEqual(agents.read_text(encoding="utf-8"), original)
        proposal = self.root / ".aimes/proposed-upgrade/AGENTS.md.proposed"
        self.assertEqual(proposal.read_text(encoding="utf-8"), "# upstream template update\n")

    def test_apply_creates_backup_before_replacing_unchanged_managed_file(self):
        claude = self.root / "CLAUDE.md"
        proposed = {
            "CLAUDE.md": "# safe managed upgrade\n",
            ".aimes/config.yaml": (self.root / ".aimes/config.yaml").read_text(encoding="utf-8"),
            ".aimes/tool-capabilities.yaml": (self.root / ".aimes/tool-capabilities.yaml").read_text(encoding="utf-8"),
            ".aimes/adapters/README.md": (self.root / ".aimes/adapters/README.md").read_text(encoding="utf-8"),
        }
        with patch("aimes_cli.upgrade.proposed_files", return_value=proposed):
            result = apply_upgrade(self.root, ["CLAUDE.md"])
        self.assertTrue(result["ok"], result)
        self.assertEqual(claude.read_text(encoding="utf-8"), "# safe managed upgrade\n")
        backup = Path(result["backup_dir"]) / "CLAUDE.md"
        self.assertTrue(backup.is_file())
        self.assertIn("CLAUDE.md", [x["path"] for x in result["written"]])
        manifest = json.loads((self.root / ".aimes/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["aimes_cli_version"], result["installed_cli_version"])


if __name__ == "__main__":
    unittest.main()
