from pathlib import Path
import unittest

import yaml

from aimes_cli.core import init_project


class ProductSkillDeploymentTests(unittest.TestCase):
    def test_init_deploys_product_and_requirement_skills_and_registry_routes(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = init_project(root, ["zcode"], dry_run=False)
            self.assertTrue(result["ok"])

            registry_path = root / ".aimes/skills/registry.yaml"
            core_path = root / "docs/_governance/AIMES-CORE-V1.2.md"
            self.assertTrue(core_path.is_file())
            registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
            routes = {item["name"]: item for item in registry["skills"]}

            expected = {
                "requirement-cognition",
                "product-analysis",
                "market-analysis",
                "financial-evaluation",
                "strategic-positioning",
                "opportunity-solution-tree",
                "customer-journey-mapping",
            }
            self.assertTrue(expected.issubset(routes))
            for route in routes.values():
                self.assertTrue((root / route["file"]).is_file(), route["file"])

            core = core_path.read_text(encoding="utf-8")
            self.assertIn("强制路由", core)
            self.assertIn("宿主级 Skill", core)

    def test_init_rerun_preserves_user_modified_skill_registry(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root, ["zcode"], dry_run=False)
            registry_path = root / ".aimes/skills/registry.yaml"
            custom = registry_path.read_text(encoding="utf-8") + "\n# user customization\n"
            registry_path.write_text(custom, encoding="utf-8")

            result = init_project(root, ["zcode"], dry_run=False)

            self.assertEqual(registry_path.read_text(encoding="utf-8"), custom)
            self.assertTrue(any(item["path"] == ".aimes/skills/registry.yaml" for item in result["conflicts"]))
            proposal = root / ".aimes/proposed/.aimes/skills/registry.yaml.proposed"
            self.assertTrue(proposal.is_file())


if __name__ == "__main__":
    unittest.main()
