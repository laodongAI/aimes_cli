from __future__ import annotations

from pathlib import Path
from typing import Any

from .project_state import load_mode_registry
from .workflow import validate_workflow_definition
from .quality_profiles import resolve_quality_profile

SKILL_REGISTRY = Path(".aimes/skills/registry.yaml")
QUALITY_GATE_CANDIDATES = (Path(".aimes/quality-gates.yaml"), Path(".aimes/skills/quality-gates.yaml"))
WORKFLOW_DIRS = (Path(".aimes/workflows"), Path("workflows"), Path("examples/workflows"))

PHASE_PLANS = {
    "project-bootstrap": ["analysis", "design", "implementation", "testing", "delivery"],
    "product-discovery": ["analysis", "clarification", "design", "review"],
    "architecture-design": ["analysis", "design", "review"],
    "feature-design": ["analysis", "clarification", "design", "review"],
    "testing-validation": ["analysis", "testing", "acceptance", "delivery"],
    "release-delivery": ["analysis", "testing", "acceptance", "delivery"],
    "engineering-audit": ["analysis", "review", "delivery"],
}


def _safe(root: Path, relative: Path) -> Path:
    base = root.resolve()
    target = (base / relative).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"Mode route path escapes project root: {relative}") from exc
    return target


def _skill_inventory(root: Path, names: list[str]) -> list[dict[str, str]]:
    registry_path = _safe(root, SKILL_REGISTRY)
    entries: dict[str, str] = {}
    if registry_path.is_file():
        import yaml
        payload = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict) or not isinstance(payload.get("skills", []), list):
            raise ValueError(f"Invalid Skill registry: {registry_path}")
        for item in payload.get("skills", []):
            if isinstance(item, dict) and isinstance(item.get("name"), str) and isinstance(item.get("file"), str):
                entries[item["name"]] = item["file"]
    result = []
    for name in names:
        relative = entries.get(name)
        if relative is None:
            result.append({"name": name, "status": "NOT_REGISTERED"})
            continue
        path = _safe(root, Path(relative))
        result.append({"name": name, "path": path.relative_to(root.resolve()).as_posix(),
                       "status": "AVAILABLE" if path.is_file() else "MISSING_FILE"})
    return result


def _workflow_inventory(root: Path, workflow_id: str | None) -> dict[str, Any]:
    if not workflow_id:
        return {"id": None, "status": "NOT_MAPPED"}
    candidates = []
    for directory in WORKFLOW_DIRS:
        for suffix in (".yaml", ".yml", ".json"):
            candidates.append(directory / f"{workflow_id}{suffix}")
    for relative in candidates:
        path = _safe(root, relative)
        if not path.is_file():
            continue
        validation = validate_workflow_definition(path)
        return {
            "id": workflow_id,
            "path": relative.as_posix(),
            "status": "AVAILABLE" if validation.get("ok") else "INVALID",
            "validation": validation,
        }
    return {"id": workflow_id, "status": "NOT_CONFIGURED",
            "expected_locations": [path.as_posix() for path in candidates]}


def explain_mode(root: Path, mode: str | None = None) -> dict[str, Any]:
    """Explain a mode's declared route and verify local assets without executing them."""
    root = root.resolve()
    registry = load_mode_registry(root)
    if mode is None:
        from .project_state import read_project_state
        mode = read_project_state(root).get("engineering_mode")
    if not isinstance(mode, str) or not mode.strip():
        raise ValueError("No engineering mode selected; pass --mode or set the current mode first")
    item = registry.get(mode)
    if item is None:
        raise ValueError(f"Unknown engineering mode: {mode}")
    skill_names = item.get("skills", [])
    if not isinstance(skill_names, list) or not all(isinstance(name, str) for name in skill_names):
        raise ValueError(f"Invalid Skill mapping for engineering mode: {mode}")
    workflow_id = item.get("workflow")
    if workflow_id is not None and (not isinstance(workflow_id, str) or not workflow_id.strip()):
        raise ValueError(f"Invalid workflow mapping for engineering mode: {mode}")
    quality_profile = item.get("quality_profile")
    if quality_profile is not None and (not isinstance(quality_profile, str) or not quality_profile.strip()):
        raise ValueError(f"Invalid quality_profile mapping for engineering mode: {mode}")
    quality_gate = next((path for path in QUALITY_GATE_CANDIDATES if _safe(root, path).is_file()), None)
    try:
        resolved_profile = resolve_quality_profile(root, quality_profile) if quality_profile else None
        profile_status = "AVAILABLE" if resolved_profile else "NOT_MAPPED"
        profile_detail = resolved_profile
    except (OSError, ValueError) as exc:
        profile_status = "INVALID"
        profile_detail = {"error": str(exc)}
    phases = PHASE_PLANS.get(mode, ["analysis", "clarification", "design", "implementation", "testing", "acceptance", "delivery"])
    skills = _skill_inventory(root, skill_names)
    return {
        "ok": True,
        "mode": {"id": mode, "label": item.get("label", mode)},
        "route": {
            "skills": skills,
            "workflow": _workflow_inventory(root, workflow_id),
            "quality": {
                "profile_id": quality_profile,
                "profile_status": profile_status,
                "profile": profile_detail,
                "global_gate_config": quality_gate.as_posix() if quality_gate else None,
                "global_gate_status": "AVAILABLE" if quality_gate else "NOT_CONFIGURED",
                "note": "AVAILABLE 仅表示 profile 定义可解析；不代表质量检查已经执行。项目 quality-gates.yaml 中的显式规则覆盖 profile 默认值。",
            },
            "recommended_phases": phases,
        },
        "execution": {
            "automatic": False,
            "side_effects": False,
            "enforcement": "ADVISORY_ONLY",
            "next_actions": [
                "按顺序读取所有 AVAILABLE Skill 的完整 SKILL.md；缺失项先修复或明确降级。",
                "工作流为 AVAILABLE 时，先审阅定义并按项目审批规则显式启动；未配置时按推荐阶段人工执行。",
                "执行全局质量检查，并结合任务风险补充专项测试；不得将质量配置存在等同于检查通过。",
            ],
        },
        "limitations": [
            "本命令只解释路由并检查本地文件，不调用模型、不执行工作流、不修改任务或项目状态。",
            "推荐阶段是指导，不是自动强制状态机；具体验收标准以需求、项目规范和批准设计为准。",
            "质量配置目前只有全局门禁文件检查，模式级 quality_profile 尚未绑定独立阈值策略。",
        ],
    }
