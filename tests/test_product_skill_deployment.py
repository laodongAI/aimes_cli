from pathlib import Path

import yaml

from aimes_cli.core import init_project


def test_init_deploys_product_and_requirement_skills_and_registry_routes(tmp_path: Path):
    result = init_project(tmp_path, ["zcode"], dry_run=False)
    assert result["ok"] is True

    req = tmp_path / ".aimes/skills/requirement-cognition/SKILL.md"
    product = tmp_path / ".aimes/skills/product-analysis/SKILL.md"
    registry_path = tmp_path / ".aimes/skills/registry.yaml"
    core = tmp_path / "docs/_governance/AIMES-CORE-V1.2.md"

    assert req.is_file()
    assert product.is_file()
    assert core.is_file()
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    routes = {item["name"]: item for item in registry["skills"]}
    assert routes["requirement-cognition"]["file"] == ".aimes/skills/requirement-cognition/SKILL.md"
    assert routes["product-analysis"]["file"] == ".aimes/skills/product-analysis/SKILL.md"
    expected_specialists = {"market-analysis", "financial-evaluation", "strategic-positioning", "opportunity-solution-tree", "customer-journey-mapping"}
    assert expected_specialists.issubset(routes)
    for route in routes.values():
        assert (tmp_path / route["file"]).is_file()
    assert "强制路由" in core.read_text(encoding="utf-8")
    assert "宿主级 Skill" in core.read_text(encoding="utf-8")


def test_init_rerun_preserves_user_modified_skill_registry(tmp_path: Path):
    init_project(tmp_path, ["zcode"], dry_run=False)
    registry_path = tmp_path / ".aimes/skills/registry.yaml"
    custom = registry_path.read_text(encoding="utf-8") + "\n# user customization\n"
    registry_path.write_text(custom, encoding="utf-8")

    result = init_project(tmp_path, ["zcode"], dry_run=False)

    assert registry_path.read_text(encoding="utf-8") == custom
    assert any(item["path"] == ".aimes/skills/registry.yaml" for item in result["conflicts"])
    proposal = tmp_path / ".aimes/proposed/.aimes/skills/registry.yaml.proposed"
    assert proposal.is_file()
