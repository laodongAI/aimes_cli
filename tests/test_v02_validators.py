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
        self.assertEqual(result["checked_skills"], len(__import__("yaml").safe_load(registry.read_text(encoding="utf-8"))["skills"]))

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


    def _skill_registry_record(self, **overrides):
        skill_file = self.write_yaml("skills/SKILL.md", '''---
skill_id: SKL-T-001
---
# Skill
## Purpose
Test purpose
## Trigger conditions
test
## Required inputs
task
## Preconditions
ready
## Workflow
do work
## Outputs
report
## Safety and permissions
no unsafe writes
## Failure handling
stop and report
## Completion criteria
criteria met
''')
        item = {
            "id": "SKL-T-001", "name": "test-skill", "version": "0.1.0",
            "file": "skills/SKILL.md", "purpose": "Test skill",
            "triggers": ["test"], "inputs": ["task"], "outputs": ["report"],
            "applies_to": ["all"], "risk_level": "low",
            "required_capabilities": ["read_project_files"],
            "forbidden_actions": ["overwrite_user_changes"], "prerequisites": ["baseline_checked"],
            "dependencies": [], "validation_status": "UNKNOWN",
            "evaluation_suite": None, "evidence": [],
            "lifecycle_stage": "proposed", "stop_conditions": ["required input missing"],
            "failure_recovery": ["preserve draft and report blocker"],
            "completion_criteria": ["output report exists"],
            "approval_required": True, "side_effects": ["writes report only"],
            "idempotency": "guarded"
        }
        item.update(overrides)
        return self.write_yaml("registry.yaml", "schema_version: 2\nskills:\n" + __import__("yaml").safe_dump([item], sort_keys=False, allow_unicode=True, indent=2))

    def test_skill_registry_v2_contract_is_valid(self):
        path = self._skill_registry_record()
        result = validate_skill_registry(path, self.root)
        self.assertTrue(result["ok"], result["findings"])

    def test_skill_registry_v2_requires_stop_failure_and_completion_contracts(self):
        path = self._skill_registry_record(stop_conditions=[], failure_recovery=[], completion_criteria=[])
        result = validate_skill_registry(path, self.root)
        self.assertFalse(result["ok"])
        self.assertGreaterEqual(
            len([f for f in result["findings"] if f["code"] == "CONTRACT_LIST_REQUIRED"]), 3
        )

    def test_skill_registry_v2_verified_requires_suite_and_evidence(self):
        path = self._skill_registry_record(validation_status="VERIFIED", evaluation_suite=None, evidence=[])
        result = validate_skill_registry(path, self.root)
        self.assertFalse(result["ok"])
        self.assertIn("VERIFIED_EVIDENCE_REQUIRED", {f["code"] for f in result["findings"]})

    def test_skill_registry_v1_remains_compatible(self):
        skill_file = self.write_yaml("skills/SKILL.md", '''---
skill_id: SKL-T-OLD
---
Purpose
Trigger conditions
Required inputs
Preconditions
Workflow
Outputs
Safety and permissions
Failure handling
Completion criteria
''')
        registry = self.write_yaml("registry-v1.yaml", '''schema_version: 1
skills:
  - id: SKL-T-OLD
    name: old-skill
    version: 0.1.0
    file: skills/SKILL.md
    purpose: Legacy skill
    triggers: [test]
    inputs: [task]
    outputs: [report]
    applies_to: [all]
    risk_level: low
    required_capabilities: []
    forbidden_actions: [unsafe_write]
    prerequisites: []
    dependencies: []
    validation_status: UNKNOWN
    evaluation_suite: null
    evidence: []
''')
        result = validate_skill_registry(registry, self.root)
        self.assertTrue(result["ok"], result["findings"])

    def test_skill_registry_schema_copies_match_and_support_v2(self):
        repo_root = Path(__file__).resolve().parents[1]
        root_schema = json.loads((repo_root / "schemas" / "skill-registry.schema.json").read_text(encoding="utf-8"))
        package_schema = json.loads((repo_root / "src" / "aimes_cli" / "schemas" / "skill-registry.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(root_schema, package_schema)
        self.assertEqual(root_schema["properties"]["schema_version"]["enum"], [1, 2])

if __name__ == "__main__":
    unittest.main()
