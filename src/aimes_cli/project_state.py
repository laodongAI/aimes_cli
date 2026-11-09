from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
from typing import Any

import yaml

STATE_REL = Path(".aimes/project-state.yaml")
MODE_REGISTRY_REL = Path(".aimes/project-state/engineering-modes.yaml")

LIFECYCLES = {
    "unknown", "new", "planning", "design", "development", "testing",
    "release", "operation", "paused", "archived",
}
PHASES = {
    "analysis", "clarification", "design", "review",
    "implementation", "testing", "acceptance", "delivery",
}
CONFIDENCE = {"high", "medium", "low"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise ValueError(f"Expected a YAML mapping: {path}")
    return value


def _safe_project_path(root: Path, relative: Path) -> Path:
    resolved_root = root.resolve()
    target = (resolved_root / relative).resolve()
    try:
        target.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"State path escapes project root: {relative}") from exc
    return target


def load_mode_registry(root: Path) -> dict[str, dict[str, Any]]:
    path = _safe_project_path(root, MODE_REGISTRY_REL)
    payload = _read_yaml(path)
    modes = payload.get("modes")
    if not isinstance(modes, list):
        raise ValueError(f"Engineering mode registry is missing a modes list: {path}")
    result: dict[str, dict[str, Any]] = {}
    for item in modes:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError("Each engineering mode must be a mapping with a string id")
        mode_id = item["id"]
        if mode_id in result:
            raise ValueError(f"Duplicate engineering mode: {mode_id}")
        triggers = item.get("triggers", [])
        skills = item.get("skills", [])
        if not isinstance(triggers, list) or not all(isinstance(x, str) for x in triggers):
            raise ValueError(f"Invalid triggers for engineering mode: {mode_id}")
        if not isinstance(skills, list) or not all(isinstance(x, str) for x in skills):
            raise ValueError(f"Invalid skills for engineering mode: {mode_id}")
        result[mode_id] = item
    return result


def detect_mode(task_text: str, registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Deterministic keyword matching only; it never claims to understand a live conversation."""
    normalized = " ".join(task_text.lower().split())
    matches: list[dict[str, Any]] = []
    for mode_id, item in registry.items():
        matched = []
        for raw in item.get("triggers", []):
            trigger = raw.lower().strip()
            if not trigger:
                continue
            if trigger.isascii() and all(ord(ch) >= 32 for ch in trigger):
                import re
                pattern = r"\b" + r"\W+".join(re.escape(part) for part in trigger.split("_") if part) + r"\b"
                if re.search(pattern, normalized):
                    matched.append(raw)
            elif trigger in normalized:
                matched.append(raw)
        # A short trigger contained inside a longer matched trigger is not independent evidence.
        deduplicated: list[str] = []
        for trigger_text in sorted(matched, key=len, reverse=True):
            lowered = trigger_text.lower()
            if not any(lowered in existing.lower() or existing.lower() in lowered
                       for existing in deduplicated):
                deduplicated.append(trigger_text)
        matched = deduplicated
        if matched:
            matches.append({"mode": mode_id, "label": item.get("label", mode_id),
                            "matched_triggers": matched, "score": len(matched)})
    matches.sort(key=lambda x: (-x["score"], x["mode"]))
    if not matches:
        return {"mode": None, "confidence": "low", "matches": [],
                "note": "未发现明确工程模式；请显式指定，避免猜测。"}
    top = matches[0]
    ambiguous = len(matches) > 1
    confidence = "low" if ambiguous else ("high" if top["score"] >= 2 else "medium")
    return {"mode": None if ambiguous else top["mode"], "confidence": confidence,
            "matches": matches[:5],
            "note": "关键词匹配仅提供候选；显式用户选择优先，不能替代对话语义判断。"}


def read_project_state(root: Path) -> dict[str, Any]:
    path = _safe_project_path(root, STATE_REL)
    if not path.exists():
        return {
            "schema_version": 1,
            "project_lifecycle": "unknown",
            "engineering_mode": None,
            "task_phase": None,
            "task": None,
            "mode_source": "unset",
            "confidence": "low",
            "updated_at": None,
        }
    if not path.is_file():
        raise ValueError(f"Project state path exists but is not a regular file: {path}")
    payload = _read_yaml(path)
    _validate_state(payload)
    return payload


def _validate_state(payload: dict[str, Any]) -> None:
    if type(payload.get("schema_version")) is not int or payload.get("schema_version") != 1:
        raise ValueError("Unsupported project state schema_version")
    lifecycle = payload.get("project_lifecycle")
    if not isinstance(lifecycle, str) or lifecycle not in LIFECYCLES:
        raise ValueError(f"Invalid project_lifecycle: {lifecycle}")
    phase = payload.get("task_phase")
    if phase is not None and (not isinstance(phase, str) or phase not in PHASES):
        raise ValueError(f"Invalid task_phase: {phase}")
    confidence = payload.get("confidence", "low")
    if not isinstance(confidence, str) or confidence not in CONFIDENCE:
        raise ValueError(f"Invalid confidence: {confidence}")
    task = payload.get("task")
    if task is not None and not isinstance(task, str):
        raise ValueError("task must be a string or null")
    if not isinstance(payload.get("mode_source", "unset"), str):
        raise ValueError("mode_source must be a string")
    mode = payload.get("engineering_mode")
    if mode is not None and (not isinstance(mode, str) or not mode.strip()):
        raise ValueError("engineering_mode must be a non-empty string or null")


def show_project_state(root: Path) -> dict[str, Any]:
    state = read_project_state(root)
    registry_path = _safe_project_path(root, MODE_REGISTRY_REL)
    registry = load_mode_registry(root) if registry_path.is_file() else {}
    mode = registry.get(state.get("engineering_mode"), {})
    skill_registry_path = _safe_project_path(root, Path(".aimes/skills/registry.yaml"))
    registered_skills: set[str] = set()
    if skill_registry_path.is_file():
        skill_payload = _read_yaml(skill_registry_path)
        for item in skill_payload.get("skills", []) if isinstance(skill_payload.get("skills"), list) else []:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                continue
            relative_skill = item.get("file")
            if not isinstance(relative_skill, str) or not relative_skill.strip():
                continue
            try:
                skill_path = _safe_project_path(root, Path(relative_skill))
            except ValueError:
                continue
            if skill_path.is_file():
                registered_skills.add(item["name"])
    routed_skills = mode.get("skills", [])
    available_skills = [name for name in routed_skills if name in registered_skills]
    missing_skills = [name for name in routed_skills if name not in registered_skills]
    next_actions: list[str] = []
    if state.get("project_lifecycle") == "unknown":
        next_actions.append("检查项目目标、代码、设计文档、测试和发布记录，确认项目生命周期")
    if not state.get("engineering_mode"):
        next_actions.append("结合当前任务描述识别工程模式；存在歧义时先向用户确认")
    elif not mode:
        next_actions.append("当前工程模式未在注册表中定义；检查模式 ID 或更新工程模式目录")
    elif missing_skills:
        next_actions.append("补齐或修复当前工程模式映射的缺失 Skill 文件")
    phase_actions = {
        "analysis": "完成现状分析、证据收集和影响范围识别",
        "clarification": "澄清阻断级歧义并确认范围与验收标准",
        "design": "形成实现设计、模块边界、复用决策和验证方案",
        "review": "完成方案评审并记录决策与遗留风险",
        "implementation": "按批准设计实施，复用既有资产并补充测试",
        "testing": "执行项目真实测试/构建命令并记录结果",
        "acceptance": "逐项验证验收标准并处理未通过项",
        "delivery": "整理变更摘要、验证证据、风险和交付报告",
    }
    if state.get("task_phase") in phase_actions:
        next_actions.append(phase_actions[state["task_phase"]])
    elif state.get("engineering_mode"):
        next_actions.append("确认当前任务阶段并更新 task_phase")
    return {
        "ok": True,
        "project": root.name,
        "state": state,
        "engineering_mode_label": mode.get("label"),
        "routed_skills": routed_skills,
        "available_skills": available_skills,
        "missing_skills": missing_skills,
        "unknown_mode": bool(state.get("engineering_mode") and not mode),
        "next_actions": next_actions,
        "workflow": mode.get("workflow"),
        "quality_profile": mode.get("quality_profile"),
        "note": "项目生命周期、当前工程模式和任务阶段分别维护；CLI 不读取 AI 对话内容。工作流和质量配置当前为路由元数据。",
    }


def set_project_state(
    root: Path, *, lifecycle: str | None = None, mode: str | None = None,
    phase: str | None = None, task: str | None = None,
    confidence: str | None = None, source: str = "user",
) -> dict[str, Any]:
    root = root.resolve()
    if task is not None and not isinstance(task, str):
        raise ValueError("task must be a string")
    for field_name, field_value in (("lifecycle", lifecycle), ("mode", mode), ("phase", phase),
                                    ("confidence", confidence), ("source", source)):
        if field_value is not None and not isinstance(field_value, str):
            raise ValueError(f"{field_name} must be a string")
    if lifecycle is None and mode is None and phase is None and task is None:
        raise ValueError("Specify at least one of lifecycle, mode, phase or task")
    state = read_project_state(root)
    mode_changed = mode is not None and mode != state.get("engineering_mode")
    task_changed = task is not None and (task.strip() or None) != state.get("task")
    if mode is None and (confidence is not None or source != "user"):
        raise ValueError("--source and --confidence can only be used together with --mode")
    if source not in {"user", "ai", "import"}:
        raise ValueError(f"Invalid mode source: {source}")
    if source == "ai" and confidence == "low":
        raise ValueError("Low-confidence AI mode guesses must be confirmed before persistence")
    registry = load_mode_registry(root) if mode is not None else {}
    if lifecycle is not None:
        if lifecycle not in LIFECYCLES:
            raise ValueError(f"Invalid lifecycle '{lifecycle}'. Choose from: {', '.join(sorted(LIFECYCLES))}")
        state["project_lifecycle"] = lifecycle
    if mode is not None:
        if mode not in registry:
            raise ValueError(f"Unknown engineering mode '{mode}'. Use 'aimes state modes' to list modes.")
        state["engineering_mode"] = mode
        state["mode_source"] = source
    if phase is not None:
        if phase not in PHASES:
            raise ValueError(f"Invalid task phase '{phase}'. Choose from: {', '.join(sorted(PHASES))}")
        state["task_phase"] = phase
    elif mode_changed or task_changed:
        state["task_phase"] = "analysis"
    if task is not None:
        if len(task) > 500:
            raise ValueError("task summary must be 500 characters or fewer")
        state["task"] = task.strip() or None
    if confidence is not None:
        if confidence not in CONFIDENCE:
            raise ValueError(f"Invalid confidence: {confidence}")
        state["confidence"] = confidence
    elif mode is not None:
        state["confidence"] = "high" if source == "user" else "medium"
    state["schema_version"] = 1
    state["updated_at"] = _now()
    path = _safe_project_path(root, STATE_REL)
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = yaml.safe_dump(state, allow_unicode=True, sort_keys=False)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=".project-state-", suffix=".tmp", delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(serialized)
            handle.flush()
        Path(temp_name).replace(path)
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)
    return show_project_state(root)


def list_project_modes(root: Path) -> dict[str, Any]:
    registry = load_mode_registry(root)
    return {"ok": True, "modes": [
        {"id": key, "label": value.get("label"), "skills": value.get("skills", []),
         "workflow": value.get("workflow"), "quality_profile": value.get("quality_profile")}
        for key, value in registry.items()
    ]}
