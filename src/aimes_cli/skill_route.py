from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .validators import _load


ASCII_TRIGGER = re.compile(r"^[ -~]+$")


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def match_skill(triggers: list[Any], task_text: str) -> tuple[int, list[str]]:
    """Score how many registry triggers appear in the task text.

    ASCII triggers use word-boundary matching (``new_feature`` also matches
    ``new feature``); non-ASCII triggers (Chinese aliases) use substring
    matching. Returns the match count and the matched trigger terms.
    """
    haystack = _normalize(task_text)
    matched: list[str] = []
    for raw in triggers:
        if not isinstance(raw, str) or not raw.strip():
            continue
        trigger = raw.strip().lower()
        if ASCII_TRIGGER.match(trigger):
            pattern = r"\b" + r"\W+".join(re.escape(part) for part in trigger.split("_") if part) + r"\b"
            if re.search(pattern, haystack):
                matched.append(raw.strip())
        elif trigger in haystack or raw.strip() in task_text:
            matched.append(raw.strip())
    return len(matched), matched


def route_skills(registry_path: Path, task_text: str, top: int = 3) -> dict[str, Any]:
    registry = _load(registry_path)
    if not isinstance(registry, dict) or not isinstance(registry.get("skills"), list):
        raise ValueError(f"Registry must be a mapping with a skills list: {registry_path}")
    ranked: list[dict[str, Any]] = []
    for skill in registry["skills"]:
        if not isinstance(skill, dict):
            continue
        triggers = skill.get("triggers") if isinstance(skill.get("triggers"), list) else []
        score, matched = match_skill(triggers, task_text)
        if score == 0:
            continue
        ranked.append({
            "id": skill.get("id"),
            "name": skill.get("name"),
            "version": skill.get("version"),
            "file": skill.get("file"),
            "purpose": skill.get("purpose"),
            "risk_level": skill.get("risk_level"),
            "inputs": skill.get("inputs", []),
            "outputs": skill.get("outputs", []),
            "prerequisites": skill.get("prerequisites", []),
            "dependencies": skill.get("dependencies", []),
            "matched_triggers": matched,
            "score": score,
        })
    ranked.sort(key=lambda item: (-item["score"], str(item.get("name"))))
    return {
        "registry": str(registry_path),
        "task_text": task_text,
        "top": top,
        "matches": ranked[: max(top, 0)],
        "checked_skills": len(registry["skills"]),
        "note": "Deterministic trigger matching; it does not prove the skill file was read or executed by a tool.",
    }


def load_skill_body(root: Path, registry_path: Path, skill_name: str) -> dict[str, Any]:
    """Return the authoritative SKILL.md content for one registered skill."""
    registry = _load(registry_path)
    skills = registry.get("skills") if isinstance(registry, dict) else None
    if not isinstance(skills, list):
        raise ValueError(f"Registry must be a mapping with a skills list: {registry_path}")
    for skill in skills:
        if isinstance(skill, dict) and skill.get("name") == skill_name:
            rel = skill.get("file")
            if not isinstance(rel, str) or not rel.strip():
                raise ValueError(f"Skill {skill_name} has no file path in the registry.")
            target = (root / rel).resolve()
            try:
                target.relative_to(root.resolve())
            except ValueError as exc:
                raise ValueError(f"Skill path must remain inside project root: {rel}") from exc
            if not target.is_file():
                raise FileNotFoundError(f"Skill file not found: {rel}")
            return {"skill": skill, "path": str(target), "content": target.read_text(encoding="utf-8")}
    raise ValueError(f"Skill not registered: {skill_name}")
