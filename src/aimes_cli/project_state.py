from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
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
                pattern = r"\b" + r"\W+".join(re.escape(part) for part in trigger.split("_") if part) + r"\\b"
                if re.search(pattern, normalized):
                    matched.append(raw)
            elif trigger in normalized:
                matched.append(raw)
        if matched:
            matches.append({"mode": mode_id, "label": item.get("label", mode_id),
                            "matched_triggers": matched, "score": len(matched)})
    matches.sort(key=lambda x: (-x["score"], x["mode"]))
    if not matches:
        return {"mode": None, "confidence": "low", "matches": [],
                "note": "未发现明确工程模式；请显式指定，避免猜测。"}
    top = matches[0]
    tied = len(matches) > 1 and matches[0]["score"] == matches[1]["score"]
    confidence = "low" if tied else ("high" if top["score"] >= 2 else "medium")
    return {"mode": None if ambiguous else top["mode"], "confidence": confidence,
            "matches": matches[:5],
            "note": "关键词匹配仅提供候选；显式用户选择优先，不能替代对话语义判断。"}


def read_project_state(root: Path) -> dict[str, Any]:
    path = _safe_project_path(root, STATE_REL)
    if not path.is_file():
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
    payload = _read_yaml(path)
    _validate_state(payload)
    return payload


def _validate_state(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported project state schema_version")
    lifecycle = payload.get("project_lifecycle")
    if lifecycle not in LIFECYCLES:
        raise ValueError(f"Invalid project_lifecycle: {lifecycle}")
    phase = payload.get("task_phase")
    if phase is not None and phase not in PHASES:
        raise ValueError(f"Invalid task_phase: {phase}")
    confidence = payload.get("confidence", "low")
    if confidence not in CONFIDENCE:
        raise ValueError(f"Invalid confidence: {confidence}")
    mode = payload.get("engineering_mode")
    if mode is not None and (not isinstance(mode, str) or not mode.strip()):
        raise ValueError("engineering_mode must be a non-empty string or null")


def show_project_state(root: Path) -> dict[str, Any]:
    state = read_project_state(root)
    registry_path = _safe_project_path(root, MODE_REGISTRY_REL)
    registry = load_mode_registry(root) if registry_path.is_file() else {}
    mode = registry.get(state.get("engineering_mode"), {})
    return {
        "ok": True,
        "project": root.name,
        "state": state,
        "engineering_mode_label": mode.get("label"),
        "routed_skills": mode.get("skills", []),
        "workflow": mode.get("workflow"),
        "quality_profile": mode.get("quality_profile"),
        "note": "项目生命周期、当前工程模式和任务阶段分别维护；CLI 不读取 AI 对话内容。",
    }


def set_project_state(
    root: Path, *, lifecycle: str | None = None, mode: str | None = None,
    phase: str | None = None, task: str | None = None,
    confidence: str | None = None, source: str = "user",
) -> dict[str, Any]:
    root = root.resolve()
    state = read_project_state(root)
    registry = load_mode_registry(root)
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
    if task is not None:
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
    temp = path.with_suffix(".yaml.tmp")
    temp.write_text(serialized, encoding="utf-8")
    temp.replace(path)
    return show_project_state(root)


def list_project_modes(root: Path) -> dict[str, Any]:
    registry = load_mode_registry(root)
    return {"ok": True, "modes": [
        {"id": key, "label": value.get("label"), "skills": value.get("skills", []),
         "workflow": value.get("workflow"), "quality_profile": value.get("quality_profile")}
        for key, value in registry.items()
    ]}
