import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from aimes_cli.cli import main
from aimes_cli.core import init_project
from aimes_cli.skill_route import load_skill_body, match_skill, route_skills

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_REGISTRY = REPO_ROOT / "src/aimes_cli/templates/skills/registry.yaml"


class SkillRouteTests(unittest.TestCase):
    def test_ascii_trigger_matches_spaced_variant(self):
        score, matched = match_skill(["new_feature", "bug_fix"], "Implement a NEW feature today")
        self.assertEqual(score, 1)
        self.assertEqual(matched, ["new_feature"])

    def test_chinese_trigger_matches_substring(self):
        score, matched = match_skill(["变更影响", "回滚风险"], "请先做变更影响分析，评估回滚风险")
        self.assertEqual(score, 2)
        self.assertIn("变更影响", matched)

    def test_route_prefers_best_matching_skill(self):
        result = route_skills(TEMPLATE_REGISTRY, "帮我做变更影响分析，确认回归范围和回滚风险")
        self.assertTrue(result["matches"])
        self.assertEqual(result["matches"][0]["name"], "change-impact-analysis")
        self.assertTrue(result["matches"][0]["file"].startswith(".aimes/skills/"))

    def test_route_for_guidance_prompt_hits_product_manager(self):
        result = route_skills(TEMPLATE_REGISTRY, "根据项目知识帮我出引导词")
        self.assertIn("product-manager", [item["name"] for item in result["matches"]])

    def test_route_without_match_returns_empty_list(self):
        result = route_skills(TEMPLATE_REGISTRY, "请解释这台咖啡机的工作原理")
        self.assertEqual(result["matches"], [])

    def test_load_skill_body_rejects_path_outside_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root, ["codex-cli"], dry_run=False)
            registry = root / ".aimes/skills/registry.yaml"
            skill_doc = load_skill_body(root, registry, "project-onboarding")
            self.assertIn("name: project-onboarding", skill_doc["content"])
            registry_text = registry.read_text(encoding="utf-8")
            registry.write_text(registry_text.replace(
                "file: .aimes/skills/project-onboarding/SKILL.md",
                "file: ../escape/SKILL.md"), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_skill_body(root, registry, "project-onboarding")

    def test_cli_skill_route_reports_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root, ["codex-cli"], dry_run=False)
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["skill", "route", "实现新功能前先做需求分析并确定验收标准",
                             "--root", str(root), "--format", "json"])
            self.assertEqual(code, 0)
            payload = json.loads(buffer.getvalue())
            names = [item["name"] for item in payload["matches"]]
            self.assertIn("requirement-cognition", names)

    def test_cli_skill_route_text_mode_lists_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root, ["codex-cli"], dry_run=False)
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main(["skill", "route", "UI 审查这个表单交互样式", "--root", str(root)])
            self.assertEqual(code, 0)
            output = buffer.getvalue()
            self.assertIn("ui-quality-review", output)
            self.assertIn("matched triggers", output)


if __name__ == "__main__":
    unittest.main()
