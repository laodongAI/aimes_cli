from pathlib import Path
import unittest, yaml

ROOT = Path(__file__).resolve().parents[1]

class PromptAssetTests(unittest.TestCase):
    def test_seven_skills_have_required_sections(self):
        files = sorted((ROOT / "skills").glob("*/SKILL.md"))
        self.assertEqual(len(files), 7)
        required = ["## Purpose / 目标与边界", "## Trigger conditions / 触发条件", "## Required inputs / 必需输入", "## Preconditions / 前置条件", "## Workflow / 工作流程", "## Outputs / 输出契约", "## Safety and permissions / 安全与权限", "## Failure handling / 失败处理", "## Completion criteria / 完成判据", "## 通用执行协议（必须遵守）", "## 评测案例"]
        for path in files:
            body = path.read_text(encoding="utf-8")
            for section in required:
                self.assertIn(section, body, f"{path}: {section}")
            self.assertIn("NOT_RUN", body)
            self.assertIn("UNKNOWN", body)
    def test_registry_versions_and_validation_status(self):
        data = yaml.safe_load((ROOT / "skills/registry.yaml").read_text(encoding="utf-8"))
        self.assertEqual(len(data["skills"]), 7)
        self.assertTrue(all(x["version"] == "0.3.0" for x in data["skills"]))
        self.assertTrue(all(x["validation_status"] == "UNKNOWN" for x in data["skills"]))
    def test_prompt_suite_has_unique_cases_and_required_shape(self):
        data = yaml.safe_load((ROOT / "examples/evaluation/prompt-optimization-suite.yaml").read_text(encoding="utf-8"))
        ids = [x["case_id"] for x in data["cases"]]
        self.assertGreaterEqual(len(ids), 12)
        self.assertEqual(len(ids), len(set(ids)))
        for case in data["cases"]:
            for key in ("objective", "input", "expected", "scoring"):
                self.assertIn(key, case)
            self.assertTrue(case["scoring"]["hard_gates"])
    def test_contract_docs_exist(self):
        for rel in ["docs/PROMPT-SYSTEM-CONTRACT-V1.0.md", "docs/SKILL-CONTRACT-V2.md", "docs/SKILL-EXECUTION-RECORD-V1.md", "docs/SKILL-ORCHESTRATION-V1.0.md", "docs/PROMPT-AUDIT-AND-OPTIMIZATION-REPORT.md", "docs/PROMPT-OUTPUT-EXAMPLES-V1.0.md", "docs/CONTEXT-BUDGET-AND-FILE-PLAN-V1.0.md", "docs/TOOL-FAILURE-DEGRADATION-PROTOCOL-V1.0.md", "docs/AUDIT-TRAIL-V1.0.md"]:
            self.assertTrue((ROOT / rel).is_file(), rel)

if __name__ == "__main__":
    unittest.main()
