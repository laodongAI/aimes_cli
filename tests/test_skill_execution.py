import tempfile
import unittest
from pathlib import Path

import yaml

from aimes_cli.skill_execution import validate_skill_execution


class SkillExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write_record(self, data):
        path = self.root / "run.yaml"
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return path

    def record(self, **overrides):
        data = {
            "schema_version": 1,
            "run_id": "RUN-001",
            "skill_id": "SKL-CORE-REQ-001",
            "skill_version": "0.3.0",
            "registry_version": "1",
            "task_id": "TASK-001",
            "baseline_commit": "abc1234",
            "tool_id": "codex-cli",
            "tool_version": "1.2.3",
            "execution_mode": "cli",
            "aimes_cli_version": "0.8.0",
            "governance_version": "1.2",
            "started_at": "2026-10-22T00:00:00Z",
            "finished_at": "2026-10-22T00:01:00Z",
            "status": "PASS",
            "steps": [{
                "step_id": "S1", "name": "Analyze requirement",
                "status": "COMPLETED", "evidence_refs": ["LOG-1"]
            }],
            "acceptance_checks": [{
                "check_id": "AC1", "criterion": "Output is reviewable",
                "status": "PASS", "evidence_refs": ["REVIEW-1"]
            }],
            "outputs": ["docs/requirement-record.md"],
            "evidence_refs": ["LOG-1", "REVIEW-1"],
            "usage": {
                "source": "unavailable",
                "input_tokens": None, "output_tokens": None, "total_tokens": None
            }
        }
        data.update(overrides)
        return data

    def test_valid_pass_record(self):
        result = validate_skill_execution(self.write_record(self.record()))
        self.assertTrue(result["ok"], result["findings"])
        self.assertEqual(result["checked_steps"], 1)
        self.assertEqual(result["checked_acceptance_checks"], 1)

    def test_pass_requires_finished_output_evidence_and_all_checks(self):
        data = self.record(finished_at=None, outputs=[], evidence_refs=[])
        data["acceptance_checks"][0]["status"] = "UNKNOWN"
        result = validate_skill_execution(self.write_record(data))
        codes = {item["code"] for item in result["findings"]}
        self.assertFalse(result["ok"])
        self.assertIn("FINISHED_AT_REQUIRED", codes)
        self.assertIn("PASS_WITHOUT_OUTPUTS", codes)
        self.assertIn("PASS_WITHOUT_EVIDENCE", codes)
        self.assertIn("PASS_WITH_FAILED_ACCEPTANCE", codes)

    def test_skipped_step_requires_reason(self):
        data = self.record()
        data["steps"][0] = {"step_id": "S1", "name": "Optional analysis", "status": "SKIPPED"}
        result = validate_skill_execution(self.write_record(data))
        self.assertIn("SKIP_REASON_REQUIRED", {item["code"] for item in result["findings"]})

    def test_unavailable_token_usage_must_not_be_estimated(self):
        data = self.record()
        data["usage"] = {
            "source": "unavailable", "input_tokens": 120,
            "output_tokens": None, "total_tokens": 120
        }
        result = validate_skill_execution(self.write_record(data))
        self.assertIn("USAGE_MUST_NOT_ESTIMATE", {item["code"] for item in result["findings"]})

    def test_duplicate_step_and_acceptance_ids_are_rejected(self):
        data = self.record()
        data["steps"].append(dict(data["steps"][0]))
        data["acceptance_checks"].append(dict(data["acceptance_checks"][0]))
        result = validate_skill_execution(self.write_record(data))
        codes = {item["code"] for item in result["findings"]}
        self.assertIn("DUPLICATE_STEP_ID", codes)
        self.assertIn("DUPLICATE_ACCEPTANCE_CHECK_ID", codes)

    def test_demo_example_is_explicitly_unknown_and_valid(self):
        repo_root = Path(__file__).resolve().parents[1]
        result = validate_skill_execution(repo_root / "examples" / "skills" / "execution-record.example.yaml")
        self.assertTrue(result["ok"], result["findings"])
        self.assertEqual(result["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
