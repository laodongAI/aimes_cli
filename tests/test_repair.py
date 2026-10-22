import json
import tempfile
import unittest
from pathlib import Path

from aimes_cli.core import init_project
from aimes_cli.repair import apply_safe_repairs, build_repair_plan
import yaml


class RepairPlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan_explains_missing_config_and_requires_tool_choice(self):
        plan = build_repair_plan(self.root)
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["repair_actions"][0]["code"], "CONFIG_MISSING")
        self.assertTrue(plan["repair_actions"][0]["options"][0]["requires_approval"])
        with self.assertRaisesRegex(ValueError, "--tools"):
            apply_safe_repairs(self.root, confirm="REPAIR")

    def test_apply_requires_case_insensitive_explicit_confirmation(self):
        with self.assertRaisesRegex(ValueError, "REPAIR"):
            apply_safe_repairs(self.root, confirm="no", tools="codex-cli")
        self.assertFalse((self.root / ".aimes/config.yaml").exists())

    def test_missing_config_can_be_initialized_with_explicit_tools(self):
        result = apply_safe_repairs(self.root, confirm="repair", tools="codex-cli")
        self.assertTrue((self.root / ".aimes/config.yaml").is_file())
        self.assertEqual(result["selected_tools"], ["codex-cli"])
        self.assertEqual(result["mode"], "safe-auto-repair")

    def test_missing_managed_core_is_restored(self):
        init_project(self.root, ["codex-cli"])
        core = self.root / "docs/_governance/AIMES-CORE-V1.2.md"
        core.unlink()
        plan = build_repair_plan(self.root)
        codes = {item["code"] for item in plan["repair_actions"]}
        self.assertIn("CORE_NOT_FOUND", codes)
        result = apply_safe_repairs(self.root, confirm="REPAIR")
        self.assertTrue(core.is_file())
        self.assertNotIn("CORE_NOT_FOUND", {item["code"] for item in result["remaining_actions"]})

    def test_user_modified_entry_is_preserved(self):
        init_project(self.root, ["codex-cli"])
        entry = self.root / "AGENTS.md"
        entry.write_text("# User-owned instructions\n", encoding="utf-8")
        result = apply_safe_repairs(self.root, confirm="REPAIR")
        self.assertEqual(entry.read_text(encoding="utf-8"), "# User-owned instructions\n")
        self.assertTrue((self.root / ".aimes/proposed/AGENTS.md.proposed").is_file())
        self.assertGreater(result["remaining_issue_count"], 0)

    def test_unsupported_schema_blocks_auto_repair_without_writes(self):
        init_project(self.root, ["codex-cli"])
        config_path = self.root / ".aimes/config.yaml"
        original = config_path.read_text(encoding="utf-8")
        config_path.write_text(original.replace("schema_version: 1", "schema_version: 999", 1), encoding="utf-8")
        changed = config_path.read_text(encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SCHEMA_UNSUPPORTED"):
            apply_safe_repairs(self.root, confirm="REPAIR")
        self.assertEqual(config_path.read_text(encoding="utf-8"), changed)

    def test_plan_includes_read_only_documentation_diagnostics(self):
        (self.root / ".env.example").write_text("API_URL=http://localhost\nAPI_URL=https://example.invalid\n", encoding="utf-8")
        (self.root / ".aimes" / "proposed").mkdir(parents=True)
        proposal = self.root / ".aimes" / "proposed" / "CLAUDE.md.proposed"
        proposal.write_text("# candidate\n", encoding="utf-8")
        plan = build_repair_plan(self.root)
        env_action = next(item for item in plan["repair_actions"] if item["code"] == "ENV_KEY_DUPLICATE")
        proposal_action = next(item for item in plan["repair_actions"] if item["code"] == "PROPOSAL_PENDING")
        self.assertEqual(env_action["source"], "docs-check")
        self.assertEqual(env_action["path"], ".env.example")
        self.assertEqual(env_action["line"], 2)
        self.assertFalse(env_action["auto_repair_available"])
        self.assertEqual(proposal_action["options"][0]["id"], "manual-review")
        self.assertTrue(proposal.is_file())

    def test_plan_explains_missing_records_path_without_guessing_format(self):
        init_project(self.root, ["codex-cli"])
        config_path = self.root / ".aimes" / "config.yaml"
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config["records"] = {"tasks": ".aimes/tasks.jsonl"}
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        plan = build_repair_plan(self.root)
        action = next(item for item in plan["repair_actions"] if item["code"] == "RECORD_PATH_MISSING")
        self.assertEqual(action["path"], ".aimes/tasks.jsonl")
        self.assertFalse(action["auto_repair_available"])
        self.assertIn("不会自动创建空文件", action["reason"])

    def test_plan_marks_untracked_files_as_manual_decisions(self):
        init_project(self.root, ["codex-cli"])
        import subprocess
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "notes-local.txt").write_text("local note\n", encoding="utf-8")
        plan = build_repair_plan(self.root)
        action = next(item for item in plan["repair_actions"] if item["code"] == "GIT_UNTRACKED_FILE" and item.get("path") == "notes-local.txt")
        self.assertFalse(action["auto_repair_available"])
        self.assertIn("不会执行 git add", action["reason"])

    def test_unknown_manual_adapter_is_reported_not_auto_verified(self):
        init_project(self.root, ["zcode"])
        plan = build_repair_plan(self.root)
        action = next(item for item in plan["repair_actions"] if item["code"] == "ADAPTER_MANUAL")
        self.assertFalse(action["auto_repair_available"])
        self.assertEqual(action["options"][0]["mode"], "guided")


if __name__ == "__main__":
    unittest.main()
