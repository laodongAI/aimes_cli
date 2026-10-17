from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from . import __version__, GOVERNANCE_VERSION
from .core import (
    CONFIG_REL,
    MANIFEST_REL,
    _manifest_for,
    is_unchanged_managed,
    load_config,
    previous_manifest,
    proposed_files,
    sha256_text,
)


def _project_version(root: Path) -> str:
    path = root / MANIFEST_REL
    if not path.is_file():
        return "unknown (manifest missing)"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return str(data.get("aimes_cli_version", "unknown"))
    except (OSError, ValueError, TypeError):
        return "unknown (manifest invalid)"


def plan_upgrade(root: Path) -> dict[str, Any]:
    """Build a read-only upgrade plan; no project file is modified."""
    root = root.resolve()
    config = load_config(root)
    if config is None:
        return {
            "ok": False,
            "root": str(root),
            "installed_cli_version": __version__,
            "project_cli_version": _project_version(root),
            "actions": [],
            "message": "No AIMES project configuration found. This command upgrades existing projects only; it will not initialize one.",
        }

    tools = [
        item.get("id")
        for item in config.get("tools", [])
        if isinstance(item, dict) and item.get("id")
    ]
    scope = config.get("project", {}).get("scope", "project")
    try:
        proposed = proposed_files(root, tools, scope)
    except (OSError, ValueError, TypeError) as exc:
        return {
            "ok": False,
            "root": str(root),
            "installed_cli_version": __version__,
            "project_cli_version": _project_version(root),
            "actions": [],
            "message": f"Unable to build upgrade plan: {exc}",
        }

    old_hashes = previous_manifest(root)
    actions: list[dict[str, Any]] = []
    conflicts: list[str] = []
    for rel, content in sorted(proposed.items()):
        if rel == MANIFEST_REL.as_posix():
            continue
        target = root / rel
        if not target.exists():
            actions.append({"path": rel, "action": "add", "safe": True})
            continue
        if not target.is_file():
            actions.append({"path": rel, "action": "conflict-preserve", "safe": False, "reason": "path exists but is not a file"})
            conflicts.append(rel)
            continue
        try:
            current = target.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            actions.append({"path": rel, "action": "conflict-preserve", "safe": False, "reason": "file cannot be read as UTF-8"})
            conflicts.append(rel)
            continue
        if current == content:
            actions.append({"path": rel, "action": "unchanged", "safe": True})
        elif is_unchanged_managed(root, rel, old_hashes):
            actions.append({"path": rel, "action": "update-managed", "safe": True})
        else:
            actions.append({
                "path": rel,
                "action": "conflict-preserve",
                "safe": False,
                "reason": "file is not proven unchanged by the previous AIMES manifest; it may contain project-specific edits",
                "proposal_path": f".aimes/proposed-upgrade/{rel}.proposed",
            })
            conflicts.append(rel)

    return {
        "ok": True,
        "root": str(root),
        "installed_cli_version": __version__,
        "project_cli_version": _project_version(root),
        "governance_target_version": GOVERNANCE_VERSION,
        "tools": tools,
        "actions": actions,
        "conflicts": conflicts,
        "message": "Read-only plan. Existing untracked or user-modified files are never overwritten.",
    }


def apply_upgrade(root: Path, selected_paths: list[str] | None = None) -> dict[str, Any]:
    """Apply safe upgrades with timestamped backups and preserved conflict proposals."""
    root = root.resolve()
    plan = plan_upgrade(root)
    if not plan["ok"]:
        return plan

    config = load_config(root) or {}
    tools = list(plan.get("tools", []))
    scope = config.get("project", {}).get("scope", "project")
    proposed = proposed_files(root, tools, scope)
    selected = set(selected_paths) if selected_paths is not None else None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = root / ".aimes" / "backups" / "upgrades" / stamp
    old_hashes = previous_manifest(root)
    written: list[dict[str, Any]] = []
    preserved: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    actual_managed: dict[str, str] = {}

    # Back up and stage safe changes first. Never delete a project file.
    for item in plan["actions"]:
        rel = item["path"]
        action = item["action"]
        target = root / rel
        content = proposed.get(rel)
        if action == "unchanged":
            if target.is_file():
                try:
                    actual_managed[rel] = target.read_text(encoding="utf-8")
                except (OSError, UnicodeError):
                    pass
            continue
        if action == "conflict-preserve":
            proposal_rel = item.get("proposal_path", f".aimes/proposed-upgrade/{rel}.proposed")
            proposal = root / proposal_rel
            if selected is not None and rel not in selected:
                preserved.append({"path": rel, "reason": "not selected; original retained"})
                continue
            try:
                proposal.parent.mkdir(parents=True, exist_ok=True)
                if proposal.exists():
                    proposal = proposal.with_name(proposal.name + f".{stamp}")
                    proposal_rel = proposal.relative_to(root).as_posix()
                proposal.write_text(content or "", encoding="utf-8")
                preserved.append({"path": rel, "reason": item.get("reason", "conflict"), "proposal_path": proposal_rel})
            except OSError as exc:
                errors.append({"path": rel, "error": str(exc)})
            continue
        if selected is not None and rel not in selected:
            if target.is_file():
                try:
                    actual_managed[rel] = target.read_text(encoding="utf-8")
                except (OSError, UnicodeError):
                    pass
            continue
        if content is None:
            continue
        try:
            if target.exists():
                if not target.is_file():
                    errors.append({"path": rel, "error": "target is not a regular file"})
                    continue
                backup = backup_root / rel
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written.append({"path": rel, "action": action, "sha256": sha256_text(content)})
            actual_managed[rel] = content
        except OSError as exc:
            errors.append({"path": rel, "error": str(exc)})

    # A valid existing manifest is backed up before replacement. The new manifest only
    # claims files whose resulting content is known; conflicts are intentionally excluded.
    manifest_path = root / MANIFEST_REL
    try:
        if manifest_path.is_file():
            try:
                old_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest_valid = isinstance(old_manifest, dict) and isinstance(old_manifest.get("managed_files"), list)
            except (OSError, ValueError, TypeError):
                manifest_valid = False
            if manifest_valid:
                backup = backup_root / MANIFEST_REL
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(manifest_path, backup)
                manifest_tools = tools
                config_path = root / CONFIG_REL
                if config_path.is_file():
                    parsed = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
                    manifest_tools = [
                        t.get("id") for t in parsed.get("tools", [])
                        if isinstance(t, dict) and t.get("id")
                    ]
                manifest = _manifest_for(actual_managed, manifest_tools)
                manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            else:
                preserved.append({"path": MANIFEST_REL.as_posix(), "reason": "invalid manifest; preserved"})
        else:
            preserved.append({"path": MANIFEST_REL.as_posix(), "reason": "manifest missing; no automatic manifest creation during upgrade"})
    except (OSError, ValueError, TypeError) as exc:
        errors.append({"path": MANIFEST_REL.as_posix(), "error": str(exc)})

    backup_exists = backup_root.exists()
    return {
        "ok": not errors,
        "root": str(root),
        "installed_cli_version": __version__,
        "project_cli_version_before": plan.get("project_cli_version"),
        "backup_dir": str(backup_root) if backup_exists else None,
        "written": written,
        "preserved": preserved,
        "errors": errors,
        "message": "Upgrade changes applied. Review conflicts and validate the project." if not errors else "Upgrade encountered errors; inspect the backup and error list before retrying.",
    }
