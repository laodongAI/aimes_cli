import json
import tempfile
import unittest
from pathlib import Path

from aimes_cli.core import init_project
from aimes_cli.repair import apply_safe_repairs, build_repair_plan


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

    def test_unknown_manual_adapter_is_reported_not_auto_verified(self):
        init_project(self.root, ["zcode"])
        plan = build_repair_plan(self.root)
        action = next(item for item in plan["repair_actions"] if item["code"] == "ADAPTER_MANUAL")
        self.assertFalse(action["auto_repair_available"])
        self.assertEqual(action["options"][0]["mode"], "guided")


if __name__ == "__main__":
    unittest.main()
