import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from aimes_cli.workflow_run import start_workflow_run, transition_workflow_run, validate_workflow_run
from aimes_cli.cli import main


class WorkflowRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.definition = self.root / "workflow.yaml"
        repo_root = Path(__file__).resolve().parents[1]
        example = repo_root / "examples" / "workflows" / "engineering-workflow.example.yaml"
        self.definition.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        self.record = self.root / ".aimes" / "workflows" / "runs" / "RUN-001.json"

    def tearDown(self):
        self.tmp.cleanup()

    def start(self, **overrides):
        args = {
            "run_id": "RUN-001",
            "task_id": "TASK-001",
            "baseline_commit": "abc1234",
            "actor": "test-runner",
            "confirm": "start",
        }
        args.update(overrides)
        return start_workflow_run(self.definition, self.record, self.root, **args)

    def transition(self, event, **overrides):
        args = {"event": event, "actor": "test-runner", "confirm": "transition"}
        args.update(overrides)
        return transition_workflow_run(self.definition, self.record, self.root, **args)

    def test_start_and_validate_run_record(self):
        started = self.start()
        self.assertTrue(started["ok"], started["findings"])
        result = validate_workflow_run(self.definition, self.record, self.root)
        self.assertTrue(result["ok"], result["findings"])
        self.assertEqual(result["current_state"], "intake")
        record = json.loads(self.record.read_text(encoding="utf-8"))
        self.assertEqual(record["attempts"], {"intake": 1})

    def test_start_requires_confirmation_and_never_overwrites(self):
        result = self.start(confirm="no")
        self.assertFalse(result["ok"])
        self.assertFalse(self.record.exists())
        self.assertTrue(self.start()["ok"])
        second = self.start()
        self.assertFalse(second["ok"])
        self.assertIn("RUN_FILE_EXISTS", {item["code"] for item in second["findings"]})

    def test_transition_requires_approval_for_approval_gated_state_and_backups(self):
        self.assertTrue(self.start()["ok"])
        denied = self.transition("success")
        self.assertFalse(denied["ok"])
        self.assertIn("APPROVAL_REQUIRED", {item["code"] for item in denied["findings"]})
        moved = self.transition("success", approval_ref="APR-001", evidence_refs=["REQ-REVIEW-001"])
        self.assertTrue(moved["ok"], moved["findings"])
        self.assertEqual(moved["current_state"], "implementation")
        self.assertTrue(Path(moved["backup_path"]).is_file())
        result = validate_workflow_run(self.definition, self.record, self.root)
        self.assertTrue(result["ok"], result["findings"])

    def test_guarded_retry_requires_evidence_and_obeys_attempt_limit(self):
        self.assertTrue(self.start()["ok"])
        self.assertTrue(self.transition("success", approval_ref="APR-001")["ok"])
        missing = self.transition("retry")
        self.assertFalse(missing["ok"])
        self.assertIn("RETRY_GUARD_EVIDENCE_REQUIRED", {item["code"] for item in missing["findings"]})
        retried = self.transition("retry", guard_evidence="Reviewed diff; previous attempt did not duplicate changes.")
        self.assertTrue(retried["ok"], retried["findings"])
        record = json.loads(self.record.read_text(encoding="utf-8"))
        self.assertEqual(record["attempts"]["implementation"], 2)
        blocked = self.transition("retry", guard_evidence="Reviewed diff again.")
        self.assertFalse(blocked["ok"])
        self.assertIn("RETRY_NOT_ALLOWED", {item["code"] for item in blocked["findings"]})

    def test_workflow_definition_change_blocks_transition(self):
        self.assertTrue(self.start()["ok"])
        with self.definition.open("a", encoding="utf-8") as stream:
            stream.write("\n# changed after run start\n")
        result = self.transition("success")
        self.assertFalse(result["ok"])
        self.assertIn("WORKFLOW_DEFINITION_CHANGED", {item["code"] for item in result["findings"]})

    def test_run_and_definition_paths_cannot_escape_project_root(self):
        result = start_workflow_run(
            self.definition, self.root.parent / "outside-run.json", self.root,
            run_id="RUN-ESCAPE", task_id="TASK-1", baseline_commit="abc",
            confirm="START"
        )
        self.assertFalse(result["ok"])
        self.assertIn("RUN_PATH_ESCAPE", {item["code"] for item in result["findings"]})

    def test_invalid_run_id_cannot_be_used_for_backup_path(self):
        result = self.start(run_id="../escape")
        self.assertFalse(result["ok"])
        self.assertIn("RUN_ID_INVALID", {item["code"] for item in result["findings"]})


    def test_cli_start_transition_and_validate(self):
        record = Path(".aimes/workflows/runs/CLI-RUN-001.json")
        args = [
            "workflow", "run", "start", str(self.definition),
            "--record", str(record), "--run-id", "CLI-RUN-001",
            "--task-id", "CLI-TASK-001", "--baseline-commit", "abc1234",
            "--confirm", "START", "--root", str(self.root), "--format", "json"
        ]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(args)
        self.assertEqual(code, 0, output.getvalue())
        transition_args = [
            "workflow", "run", "transition", str(self.definition), str(record),
            "--event", "success", "--approval-ref", "APR-CLI-001",
            "--confirm", "TRANSITION", "--root", str(self.root), "--format", "json"
        ]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(transition_args)
        self.assertEqual(code, 0, output.getvalue())
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["workflow", "run", "validate", str(self.definition), str(record), "--root", str(self.root), "--format", "json"])
        self.assertEqual(code, 0, output.getvalue())

    def test_run_schema_copies_match(self):
        repo_root = Path(__file__).resolve().parents[1]
        root_schema = json.loads((repo_root / "schemas" / "workflow-run.schema.json").read_text(encoding="utf-8"))
        package_schema = json.loads((repo_root / "src" / "aimes_cli" / "schemas" / "workflow-run.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(root_schema, package_schema)

if __name__ == "__main__":
    unittest.main()
