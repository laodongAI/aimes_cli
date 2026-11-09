import tempfile
import unittest
from pathlib import Path

import yaml

from aimes_cli.core import init_project
from aimes_cli.project_state import (
    detect_mode, list_project_modes, read_project_state,
    set_project_state, show_project_state, load_mode_registry,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MODE_TEMPLATE = REPO_ROOT / "src/aimes_cli/templates/project-state/engineering-modes.yaml"


class ProjectStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        init_project(self.root, ["codex-cli"])

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_deploys_mode_registry_and_initial_state(self):
        self.assertTrue((self.root / ".aimes/project-state/engineering-modes.yaml").is_file())
        self.assertEqual(read_project_state(self.root)["project_lifecycle"], "unknown")

    def test_lifecycle_mode_and_phase_are_independent(self):
        result = set_project_state(self.root, lifecycle="development",
                                   mode="frontend-optimization", phase="analysis",
                                   task="优化学习页面")
        state = result["state"]
        self.assertEqual(state["project_lifecycle"], "development")
        self.assertEqual(state["engineering_mode"], "frontend-optimization")
        self.assertEqual(state["task_phase"], "analysis")
        self.assertEqual(result["routed_skills"][0], "vue-frontend-engineering")

    def test_explicit_user_mode_has_high_confidence(self):
        result = set_project_state(self.root, mode="refactoring", source="user")
        self.assertEqual(result["state"]["confidence"], "high")
        self.assertEqual(result["state"]["mode_source"], "user")

    def test_unknown_mode_is_rejected_without_writing(self):
        before = (self.root / ".aimes/project-state.yaml").read_text(encoding="utf-8")
        with self.assertRaises(ValueError):
            set_project_state(self.root, mode="invented-mode")
        after = (self.root / ".aimes/project-state.yaml").read_text(encoding="utf-8")
        self.assertEqual(after, before)

    def test_invalid_phase_is_rejected(self):
        with self.assertRaises(ValueError):
            set_project_state(self.root, phase="coding")

    def test_detection_is_conservative_when_ambiguous(self):
        registry = load_mode_registry(self.root)
        result = detect_mode("前端优化和代码重构", registry)
        self.assertIsNone(result["mode"])
        self.assertEqual(result["confidence"], "low")

    def test_detection_returns_candidate_but_does_not_persist(self):
        registry = load_mode_registry(self.root)
        before = (self.root / ".aimes/project-state.yaml").read_text(encoding="utf-8")
        result = detect_mode("请做 Vue 组件化开发", registry)
        self.assertEqual(result["mode"], "frontend-development")
        self.assertEqual(result["confidence"], "medium")
        after = (self.root / ".aimes/project-state.yaml").read_text(encoding="utf-8")
        self.assertEqual(after, before)

    def test_state_path_symlink_escape_is_rejected(self):
        outside = self.root.parent / (self.root.name + "-outside")
        outside.mkdir()
        try:
            (self.root / ".aimes").rename(self.root / ".aimes-original")
            (self.root / ".aimes").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                read_project_state(self.root)
        finally:
            (self.root / ".aimes").unlink(missing_ok=True)
            (self.root / ".aimes-original").rename(self.root / ".aimes")
            outside.rmdir()

    def test_modes_are_listed(self):
        result = list_project_modes(self.root)
        ids = {item["id"] for item in result["modes"]}
        self.assertIn("frontend-optimization", ids)
        self.assertIn("engineering-audit", ids)\n        self.assertIn("ai-model-evaluation", ids)\n        self.assertIn("technical-debt", ids)


    def test_cli_state_commands_show_set_detect_and_list_modes(self):
        from aimes_cli.cli import main
        import io
        from contextlib import redirect_stdout
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["state", "set", "--root", str(self.root),
                         "--mode", "frontend-optimization", "--phase", "analysis",
                         "--lifecycle", "development", "--format", "json"])
        self.assertEqual(code, 0)
        saved = yaml.safe_load((self.root / ".aimes/project-state.yaml").read_text(encoding="utf-8"))
        self.assertEqual(saved["engineering_mode"], "frontend-optimization")
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["state", "show", "--root", str(self.root), "--format", "json"])
        self.assertEqual(code, 0)
        self.assertIn("vue-frontend-engineering", buffer.getvalue())
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["state", "detect", "--root", str(self.root),
                         "--task-text", "Vue组件化开发", "--format", "json"])
        self.assertEqual(code, 0)
        self.assertIn('"mode": "frontend-development"', buffer.getvalue())

    def test_state_show_reports_skill_mapping_health(self):
        result = set_project_state(self.root, mode="frontend-optimization")
        self.assertIn("vue-frontend-engineering", result["available_skills"])
        self.assertEqual(result["missing_skills"], [])

    def test_ascii_task_trigger_detection(self):
        registry = load_mode_registry(self.root)
        result = detect_mode("frontend optimization", registry)
        self.assertEqual(result["mode"], "frontend-optimization")

    def test_state_show_marks_missing_skill_file(self):
        skill_path = self.root / ".aimes/skills/vue-frontend-engineering/SKILL.md"
        skill_path.unlink()
        result = set_project_state(self.root, mode="frontend-optimization")
        self.assertNotIn("vue-frontend-engineering", result["available_skills"])
        self.assertIn("vue-frontend-engineering", result["missing_skills"])

    def test_lifecycle_can_be_set_without_initializing_skill_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            result = set_project_state(root, lifecycle="planning")
            self.assertEqual(result["state"]["project_lifecycle"], "planning")
            self.assertEqual(result["state"]["engineering_mode"], None)

if __name__ == "__main__":
    unittest.main()
