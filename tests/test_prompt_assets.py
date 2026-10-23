from pathlib import Path
import unittest, yaml

ROOT = Path(__file__).resolve().parents[1]

class PromptAssetTests(unittest.TestCase):
    def test_all_skills_have_required_sections(self):
        files = sorted((ROOT / "skills").glob("*/SKILL.md"))
        self.assertEqual(len(files), 11)
        required = ["## Purpose / 目标与边界", "## Trigger conditions / 触发条件", "## Required inputs / 必需输入", "## Preconditions / 前置条件", "## Workflow / 工作流程", "## Outputs / 输出契约", "## Safety and permissions / 安全与权限", "## Failure handling / 失败处理", "## Completion criteria / 完成判据", "## 通用执行协议（必须遵守）", "## 评测案例"]
        for path in files:
            body = path.read_text(encoding="utf-8")
            for section in required:
                self.assertIn(section, body, f"{path}: {section}")
            self.assertIn("NOT_RUN", body)
            self.assertIn("UNKNOWN", body)
    def test_registry_versions_and_validation_status(self):
        data = yaml.safe_load((ROOT / "skills/registry.yaml").read_text(encoding="utf-8"))
        self.assertEqual(len(data["skills"]), 11)
        versions = {x["name"]: x["version"] for x in data["skills"]}
        self.assertEqual(versions["ui-quality-review"], "1.0.0")
        self.assertEqual(versions["frontend-design"], "1.0.0")
        self.assertEqual(versions["design-system-governance"], "1.0.0")
        self.assertEqual(versions["ui-implementation-validation"], "1.0.0")
        self.assertTrue(all(x["validation_status"] == "UNKNOWN" for x in data["skills"]))
        ui_skill = next(x for x in data["skills"] if x["name"] == "ui-quality-review")
        self.assertEqual(ui_skill["evaluation_suite"], "AIMES-UI-QUALITY-GOVERNANCE")
    def test_prompt_suite_has_unique_cases_and_required_shape(self):
        data = yaml.safe_load((ROOT / "examples/evaluation/prompt-optimization-suite.yaml").read_text(encoding="utf-8"))
        ids = [x["case_id"] for x in data["cases"]]
        self.assertGreaterEqual(len(ids), 12)
        self.assertEqual(len(ids), len(set(ids)))
        for case in data["cases"]:
            for key in ("objective", "input", "expected", "scoring"):
                self.assertIn(key, case)
            self.assertTrue(case["scoring"]["hard_gates"])
    def test_ui_quality_suite_has_required_cases(self):
        data = yaml.safe_load((ROOT / "examples/evaluation/ui-quality-governance-suite.yaml").read_text(encoding="utf-8"))
        self.assertEqual(data["suite_id"], "AIMES-UI-QUALITY-GOVERNANCE")
        ids = [case["case_id"] for case in data["cases"]]
        self.assertGreaterEqual(len(ids), 6)
        self.assertEqual(len(ids), len(set(ids)))
        for case in data["cases"]:
            self.assertTrue(case["scoring"]["hard_gates"], case["case_id"])
            self.assertIn("required_findings", case["expected"], case["case_id"])

    def test_ui_skills_are_registered_and_routed_from_core(self):
        data = yaml.safe_load((ROOT / "skills/registry.yaml").read_text(encoding="utf-8"))
        names = {item["name"] for item in data["skills"]}
        self.assertTrue({"ui-quality-review", "frontend-design", "design-system-governance", "ui-implementation-validation"} <= names)
        core = (ROOT / "src/aimes_cli/templates/core/AIMES-CORE-V1.2.md").read_text(encoding="utf-8")
        for rel in [".aimes/skills/registry.yaml", ".aimes/skills/frontend-design/SKILL.md", ".aimes/skills/design-system-governance/SKILL.md", ".aimes/skills/ui-quality-review/SKILL.md", ".aimes/skills/ui-implementation-validation/SKILL.md"]:
            self.assertIn(rel, core)
        from aimes_cli.core import proposed_files
        deployed = proposed_files(ROOT, ["codex-cli"], "project")
        self.assertIn(".aimes/skills/registry.yaml", deployed)
        for name in ["frontend-design", "design-system-governance", "ui-quality-review", "ui-implementation-validation"]:
            self.assertIn(f".aimes/skills/{name}/SKILL.md", deployed)
            self.assertIn("## Workflow / 工作流程", deployed[f".aimes/skills/{name}/SKILL.md"])

    def test_contract_docs_exist(self):
        for rel in ["docs/PROMPT-SYSTEM-CONTRACT-V1.0.md", "skills/ui-quality-review/SKILL.md", "skills/frontend-design/SKILL.md", "skills/design-system-governance/SKILL.md", "skills/ui-implementation-validation/SKILL.md", "docs/UI-DESIGN-GOVERNANCE.md", "examples/evaluation/ui-quality-governance-suite.yaml", "docs/SKILL-CONTRACT-V2.md", "docs/SKILL-EXECUTION-RECORD-V1.md", "docs/WORKFLOW-STATE-MACHINE-V1.md", "docs/SKILL-ORCHESTRATION-V1.0.md", "docs/PROMPT-AUDIT-AND-OPTIMIZATION-REPORT.md", "docs/PROMPT-OUTPUT-EXAMPLES-V1.0.md", "docs/CONTEXT-BUDGET-AND-FILE-PLAN-V1.0.md", "docs/TOOL-FAILURE-DEGRADATION-PROTOCOL-V1.0.md", "docs/AUDIT-TRAIL-V1.0.md"]:
            self.assertTrue((ROOT / rel).is_file(), rel)

if __name__ == "__main__":
    unittest.main()
