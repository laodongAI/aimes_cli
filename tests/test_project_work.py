import tempfile
import unittest
from pathlib import Path

from aimes_cli.core import init_project
from aimes_cli.project_state import read_project_state, set_project_state
from aimes_cli.project_work import (
    assess_project_lifecycle, bind_session_task, list_tasks, show_session,
    show_task, start_task, update_task,
)


class ProjectWorkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        init_project(self.root, ["codex-cli"])

    def tearDown(self):
        self.tmp.cleanup()

    def test_tasks_are_isolated_by_session_and_can_be_rebound(self):
        first = start_task(self.root, "优化前端页面", session_id="codex", task_id="task-front")
        second = start_task(self.root, "修复接口缺陷", session_id="claude", task_id="task-api")
        self.assertEqual(first["session"]["current_task_id"], "task-front")
        self.assertEqual(second["session"]["current_task_id"], "task-api")
        self.assertEqual(show_session(self.root, "codex")["current_task"]["task_id"], "task-front")
        self.assertEqual(show_session(self.root, "claude")["current_task"]["task_id"], "task-api")
        self.assertEqual(len(list_tasks(self.root)["tasks"]), 2)
        self.assertEqual([x["task_id"] for x in list_tasks(self.root, session_id="codex")["tasks"]],
                         ["task-front"])
        rebound = bind_session_task(self.root, "codex", "task-api")
        self.assertEqual(rebound["session"]["current_task_id"], "task-api")

    def test_task_phase_and_status_are_independently_updated(self):
        start_task(self.root, "实现用户资料页", task_id="profile-ui")
        result = update_task(self.root, "profile-ui", phase="testing", status="blocked")
        self.assertEqual(result["task"]["phase"], "testing")
        self.assertEqual(result["task"]["status"], "blocked")
        self.assertEqual(show_task(self.root, "profile-ui")["task"]["title"], "实现用户资料页")

    def test_task_validation_rejects_empty_updates_and_path_traversal(self):
        start_task(self.root, "安全任务", task_id="safe-task")
        with self.assertRaises(ValueError):
            update_task(self.root, "safe-task")
        with self.assertRaises(ValueError):
            show_task(self.root, "../outside")

    def test_task_start_rejects_unknown_mode_and_invalid_session(self):
        with self.assertRaises(ValueError):
            start_task(self.root, "未知模式", mode="not-registered")
        (self.root / ".aimes/sessions").mkdir(parents=True, exist_ok=True)
        (self.root / ".aimes/sessions/broken.yaml").write_text(
            "schema_version: 99\nsession_id: broken\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            start_task(self.root, "坏会话", session_id="broken")

    def test_task_listing_rejects_symlink_escape(self):
        outside = self.root.parent / (self.root.name + "-outside-tasks")
        outside.mkdir()
        try:
            tasks = self.root / ".aimes/tasks"
            tasks.mkdir(parents=True, exist_ok=True)
            (tasks / "external.yaml").symlink_to(outside / "external.yaml")
            with self.assertRaises(ValueError):
                list_tasks(self.root)
        finally:
            (self.root / ".aimes/tasks/external.yaml").unlink(missing_ok=True)
            outside.rmdir()

    def test_task_listing_rejects_malformed_record_types(self):
        tasks = self.root / ".aimes/tasks"
        tasks.mkdir(parents=True, exist_ok=True)
        (tasks / "malformed.yaml").write_text(
            "schema_version: 1\ntask_id: malformed\ntitle: broken\nstatus: [active]\nphase: analysis\nsession_id: default\n",
            encoding="utf-8")
        with self.assertRaises(ValueError):
            list_tasks(self.root)

    def test_lifecycle_assessment_is_read_only_and_reports_evidence(self):
        set_project_state(self.root, lifecycle="development")
        before = read_project_state(self.root)
        (self.root / "tests").mkdir()
        result = assess_project_lifecycle(self.root)
        after = read_project_state(self.root)
        self.assertEqual(before, after)
        self.assertEqual(result["current_lifecycle"], "development")
        self.assertTrue(any(item["source"] == "tests" and item["signal"] == "testing" and item["weight"] == 2 for item in result["evidence"]))
        self.assertIn("candidate", result)
        self.assertIn("limitations", result)

    def test_lifecycle_assessment_uses_multiple_independent_development_signals(self):
        (self.root / "src").mkdir()
        (self.root / "pyproject.toml").write_text("[project]\nname = 'sample'\n", encoding="utf-8")
        result = assess_project_lifecycle(self.root)
        self.assertEqual(result["candidate"], "development")
        self.assertEqual(result["confidence"], "medium")
        self.assertGreaterEqual(result["signals"]["development"], 3)

    def test_lifecycle_assessment_does_not_infer_new_from_aimes_init(self):
        result = assess_project_lifecycle(self.root)
        self.assertNotEqual(result["candidate"], "new")
        self.assertEqual(result["current_lifecycle"], "unknown")

    def test_cli_exposes_task_session_and_lifecycle_assessment(self):
        from aimes_cli.cli import main
        import io
        from contextlib import redirect_stdout

        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["task", "start", "--root", str(self.root),
                         "--title", "CLI任务", "--session-id", "vscode", "--id", "cli-task",
                         "--format", "json"])
        self.assertEqual(code, 0)
        self.assertIn('"task_id": "cli-task"', output.getvalue())

        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["session", "show", "--root", str(self.root),
                         "--id", "vscode", "--format", "json"])
        self.assertEqual(code, 0)
        self.assertIn('"current_task_id": "cli-task"', output.getvalue())

        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["state", "assess-lifecycle", "--root", str(self.root), "--format", "json"])
        self.assertEqual(code, 0)
        self.assertIn('"evidence"', output.getvalue())


if __name__ == "__main__":
    unittest.main()
