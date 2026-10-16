import json
import tempfile
import unittest
from pathlib import Path

from aimes_cli.validators import validate_requirement, validate_knowledge, validate_reuse, validate_skill_registry


class V02ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write_yaml(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_valid_requirement_record(self):
        path = self.write_yaml("requirement.yaml", '''schema_version: 1
record_id: RCN-T-001
source_task_id: TASK-T-001
status: DRAFT
business_goal: Test goal
scenarios:
  - id: SCN-001
requirements:
  - id: REQ-T-001
    statement: A testable requirement
    source_refs: [docs/req.md]
    acceptance_criteria: [criterion]
''')
        result = validate_requirement(path)
        self.assertTrue(result["ok"], result)

    def test_requirement_duplicate_id_and_missing_acceptance_fail(self):
        path = self.write_yaml("requirement.yaml", '''schema_version: 1
record_id: RCN-T-001
source_task_id: TASK-T-001
status: DRAFT
business_goal: Test goal
scenarios: [{id: SCN-001}, {id: SCN-001}]
requirements:
  - id: REQ-T-001
    statement: No acceptance
    source_refs: []
    acceptance_criteria: []
''')
        result = validate_requirement(path)
        codes = {f["code"] for f in result["findings"]}
        self.assertFalse(result["ok"])
        self.assertIn("DUPLICATE_ID", codes)
        self.assertIn("ACCEPTANCE_CRITERIA", codes)

    def test_malformed_status_type_is_reported_not_crashed(self):
        path = self.write_yaml("requirement.yaml", '''schema_version: 1
record_id: RCN-T-001
source_task_id: TASK-T-001
status: [APPROVED]
business_goal: Test goal
scenarios: []
requirements: []
''')
        result = validate_requirement(path)
        self.assertFalse(result["ok"])
        self.assertIn("INVALID_STATUS", {f["code"] for f in result["findings"]})

    def test_approved_requirement_requires_approval_evidence(self):
        path = self.write_yaml("approved.yaml", '''schema_version: 1
record_id: RCN-T-001
source_task_id: TASK-T-001
status: APPROVED
business_goal: Test goal
scenarios: []
requirements: []
''')
        result = validate_requirement(path)
        self.assertIn("APPROVAL_EVIDENCE", {f["code"] for f in result["findings"]})

    def test_candidate_knowledge_needs_source_and_path_escape_is_rejected(self):
        path = self.write_yaml("knowledge.yaml", '''schema_version: 1
knowledge_id: KNOW-T-001
title: Test
type: pattern
summary: Summary
source_refs: [../outside.md]
applicability_conditions: [condition]
constraints: []
exceptions: []
invalidating_conditions: []
verification_evidence: []
maturity: candidate
''')
        result = validate_knowledge(path, self.root)
        self.assertIn("PATH_ESCAPE", {f["code"] for f in result["findings"]})
        self.assertFalse(result["ok"])

    def test_reviewed_knowledge_requires_evidence(self):
        path = self.write_yaml("knowledge.yaml", '''schema_version: 1
knowledge_id: KNOW-T-001
title: Test
type: pattern
summary: Summary
source_refs: [docs/source.md]
applicability_conditions: [condition]
constraints: []
exceptions: []
invalidating_conditions: []
verification_evidence: []
maturity: reviewed
''')
        result = validate_knowledge(path, self.root)
        self.assertIn("MATURITY_EVIDENCE", {f["code"] for f in result["findings"]})

    def test_reuse_decision_requires_plan_and_asset_ref(self):
        path = self.write_yaml("reuse.yaml", '''schema_version: 1
reuse_decision_id: RUD-T-001
task_id: TASK-T-001
status: DRAFT
candidate_assets: [{}]
comparison: {}
decision: ADAPT
rationale: Adapt after comparison
verification_plan: []
''')
        result = validate_reuse(path)
        codes = {f["code"] for f in result["findings"]}
        self.assertIn("ASSET_REF", codes)
        self.assertIn("VERIFICATION_PLAN", codes)

    def test_skill_registry_checks_file_and_id(self):
        skill_file = self.write_yaml("skills/SKILL.md", '''---\nskill_id: SKL-T-001\n---\n# Purpose\nTrigger conditions\nRequired inputs\nPreconditions\nWorkflow\nOutputs\nSafety and permissions\nFailure handling\nCompletion criteria\n''')
        registry = self.write_yaml("registry.yaml", f'''schema_version: 1
skills:
  - id: SKL-T-001
    name: test-skill
    version: 0.1.0
    file: skills/SKILL.md
    purpose: Test skill
    triggers: [test]
    inputs: [task]
    outputs: [report]
    applies_to: [all]
    risk_level: low
    required_capabilities: []
    forbidden_actions: [overwrite_user_changes]
    prerequisites: []
    dependencies: []
    validation_status: UNKNOWN
    evaluation_suite: null
    evidence: []
''')
        result = validate_skill_registry(registry, self.root)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["checked_skills"], 1)

    def test_p0_skill_registry_validates(self):
        project_root = Path(__file__).resolve().parents[1]
        registry = project_root / "skills" / "registry.yaml"
        result = validate_skill_registry(registry, project_root)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["checked_skills"], 7)

    def test_skill_path_escape_is_rejected(self):
        registry = self.write_yaml("registry.yaml", '''schema_version: 1
skills:
  - id: SKL-T-001
    name: test-skill
    version: 0.1.0
    file: ../escape.md
    purpose: Test skill
    triggers: [test]
    inputs: [task]
    outputs: [report]
    applies_to: [all]
    risk_level: low
    required_capabilities: []
    forbidden_actions: []
    prerequisites: []
    dependencies: []
    validation_status: UNKNOWN
    evaluation_suite: null
    evidence: []
''')
        result = validate_skill_registry(registry, self.root)
        self.assertIn("PATH_ESCAPE", {f["code"] for f in result["findings"]})
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
