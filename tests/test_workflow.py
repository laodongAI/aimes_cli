import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from aimes_cli.cli import main
from aimes_cli.workflow import validate_workflow_definition


class WorkflowDefinitionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        repo_root = Path(__file__).resolve().parents[1]
        self.example = yaml.safe_load((repo_root / "examples" / "workflows" / "engineering-workflow.example.yaml").read_text(encoding="utf-8"))

    def tearDown(self):
        self.tmp.cleanup()

    def write_workflow(self, data):
        path = self.root / "workflow.yaml"
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return path

    def test_example_workflow_is_valid(self):
        result = validate_workflow_definition(self.write_workflow(self.example))
        self.assertTrue(result["ok"], result["findings"])
        self.assertEqual(result["checked_states"], 6)

    def test_unknown_transition_target_is_rejected(self):
        data = self.example
        data["transitions"][0]["to"] = "missing-state"
        result = validate_workflow_definition(self.write_workflow(data))
        self.assertIn("TRANSITION_TARGET", {item["code"] for item in result["findings"]})

    def test_unreachable_state_is_rejected(self):
        data = self.example
        data["states"].append({
            "state_id": "orphan", "name": "Orphan",
            "entry_conditions": ["never"], "required_artifacts": [],
            "completion_criteria": ["done"], "failure_recovery": ["stop"],
            "side_effects": ["none"], "approval_required": False,
            "retry_mode": "never", "max_attempts": 1, "terminal_outcome": None
        })
        result = validate_workflow_definition(self.write_workflow(data))
        self.assertIn("UNREACHABLE_STATE", {item["code"] for item in result["findings"]})

    def test_nonterminal_state_requires_failure_path(self):
        data = self.example
        data["transitions"] = [t for t in data["transitions"] if not (t["from"] == "intake" and t["on"] in {"failure", "blocked", "cancelled"})]
        result = validate_workflow_definition(self.write_workflow(data))
        self.assertIn("FAILURE_TRANSITION_REQUIRED", {item["code"] for item in result["findings"]})

    def test_retry_requires_explicit_retry_policy(self):
        data = self.example
        state = next(s for s in data["states"] if s["state_id"] == "implementation")
        state["retry_mode"] = "never"
        state["max_attempts"] = 1
        result = validate_workflow_definition(self.write_workflow(data))
        self.assertIn("RETRY_NOT_ALLOWED", {item["code"] for item in result["findings"]})

    def test_non_retry_cycle_is_rejected(self):
        data = self.example
        data["transitions"].append({"from": "verification", "to": "intake", "on": "success"})
        result = validate_workflow_definition(self.write_workflow(data))
        self.assertIn("WORKFLOW_CYCLE", {item["code"] for item in result["findings"]})

    def test_malformed_state_references_do_not_crash(self):
        data = self.example
        data["transitions"][0]["from"] = ["intake"]
        data["states"][0]["terminal_outcome"] = ["SUCCESS"]
        result = validate_workflow_definition(self.write_workflow(data))
        self.assertFalse(result["ok"])
        codes = {item["code"] for item in result["findings"]}
        self.assertIn("TRANSITION_SOURCE", codes)
        self.assertIn("TERMINAL_OUTCOME", codes)

    def test_cli_validates_workflow_example(self):
        repo_root = Path(__file__).resolve().parents[1]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["workflow", "validate", "examples/workflows/engineering-workflow.example.yaml", "--root", str(repo_root), "--format", "json"])
        self.assertEqual(code, 0, output.getvalue())

    def test_schema_copies_match(self):
        repo_root = Path(__file__).resolve().parents[1]
        root_schema = json.loads((repo_root / "schemas" / "workflow-definition.schema.json").read_text(encoding="utf-8"))
        package_schema = json.loads((repo_root / "src" / "aimes_cli" / "schemas" / "workflow-definition.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(root_schema, package_schema)


if __name__ == "__main__":
    unittest.main()
