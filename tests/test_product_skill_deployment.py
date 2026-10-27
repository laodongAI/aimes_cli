from pathlib import Path
import unittest

import yaml

from aimes_cli.core import init_project, validate_project


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
                "project-onboarding",
                "project-knowledge-reuse",
                "change-impact-analysis",
                "architecture-contract-review",
                "controlled-implementation",
                "requirement-driven-testing",
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


    def test_every_canonical_skill_is_packaged_and_registered(self):
        repository_root = Path(__file__).resolve().parents[1]
        canonical = yaml.safe_load((repository_root / "skills/registry.yaml").read_text(encoding="utf-8"))
        deployable = yaml.safe_load((repository_root / "src/aimes_cli/templates/skills/registry.yaml").read_text(encoding="utf-8"))
        deployable_names = {item["name"] for item in deployable["skills"]}

        for skill in canonical["skills"]:
            self.assertIn(skill["name"], deployable_names, f"not registered for deployment: {skill['name']}")
            self.assertTrue((repository_root / skill["file"]).is_file(), skill["file"])
            packaged = repository_root / "src/aimes_cli/templates/skills" / skill["name"] / "SKILL.md"
            self.assertTrue(packaged.is_file(), f"not packaged: {skill['name']}")

    def test_validate_fails_when_registered_skill_file_is_missing(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root, ["zcode"], dry_run=False)
            registry_path = root / ".aimes/skills/registry.yaml"
            registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
            registry["skills"][0]["file"] = ".aimes/skills/not-installed/SKILL.md"
            registry_path.write_text(yaml.safe_dump(registry, allow_unicode=True, sort_keys=False), encoding="utf-8")

            result = validate_project(root)

            self.assertFalse(result["ok"])
            self.assertTrue(any(item["code"] == "SKILL_FILE_MISSING" for item in result["findings"]))

    def test_validate_rejects_skill_path_outside_project(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root, ["zcode"], dry_run=False)
            registry_path = root / ".aimes/skills/registry.yaml"
            registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
            registry["skills"][0]["file"] = "../../outside/SKILL.md"
            registry_path.write_text(yaml.safe_dump(registry, allow_unicode=True, sort_keys=False), encoding="utf-8")

            result = validate_project(root)

            self.assertFalse(result["ok"])
            self.assertTrue(any(item["code"] == "SKILL_PATH_UNSAFE" for item in result["findings"]))


    def test_template_skills_have_native_discoverable_frontmatter(self):
        repository_root = Path(__file__).resolve().parents[1]
        template_root = repository_root / "src/aimes_cli/templates/skills"
        registry = yaml.safe_load((template_root / "registry.yaml").read_text(encoding="utf-8"))
        names = {item["name"] for item in registry["skills"]}
        self.assertIn("project-onboarding", names)
        for name in sorted(names):
            path = template_root / name / "SKILL.md"
            self.assertTrue(path.is_file(), name)
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), f"{name}: missing frontmatter")
            frontmatter = yaml.safe_load(text.split("---\n", 2)[1])
            self.assertEqual(frontmatter.get("name"), name, f"{name}: frontmatter name must match directory")
            description = frontmatter.get("description")
            self.assertIsInstance(description, str)
            self.assertTrue(description.strip(), f"{name}: empty description")

    def test_registry_triggers_include_chinese_aliases(self):
        repository_root = Path(__file__).resolve().parents[1]
        registry = yaml.safe_load((repository_root / "src/aimes_cli/templates/skills/registry.yaml").read_text(encoding="utf-8"))
        routes = {item["name"]: item for item in registry["skills"]}
        self.assertIn("新功能", routes["requirement-cognition"]["triggers"])
        self.assertIn("引导词", routes["product-manager"]["triggers"])
        self.assertIn("变更影响", routes["change-impact-analysis"]["triggers"])

    def test_claude_skill_mirror_deployed_only_for_claude_family_tools(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root, ["claude-code"], dry_run=False)
            mirror = root / ".claude/skills/project-onboarding/SKILL.md"
            self.assertTrue(mirror.is_file())
            frontmatter = yaml.safe_load(mirror.read_text(encoding="utf-8").split("---\n", 2)[1])
            self.assertEqual(frontmatter["name"], "project-onboarding")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root, ["codex-cli"], dry_run=False)
            self.assertFalse((root / ".claude").exists())

    def test_claude_skill_mirror_is_manifest_managed(self):
        import tempfile
        import json

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            init_project(root, ["vscode-claude-code"], dry_run=False)
            manifest = json.loads((root / ".aimes/manifest.json").read_text(encoding="utf-8"))
            managed = {item["path"] for item in manifest["managed_files"]}
            self.assertIn(".claude/skills/product-manager/SKILL.md", managed)


if __name__ == "__main__":
    unittest.main()
