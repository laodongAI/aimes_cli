"""Git branch inventory and conservative local cleanup planning.

This module never deletes remote branches. Cleanup is local-only, limited to
branches already merged into the detected origin default branch, and protects
the current branch plus common default/protected branch names.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

PROTECTED_NAMES = {"main", "master", "develop", "development", "trunk"}


def _git(root: Path, *args: str, timeout: int = 10) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if proc.returncode:
        detail = (proc.stderr or proc.stdout).strip()
        raise ValueError(f"git {' '.join(args)} failed (exit {proc.returncode}): {detail}")
    return proc.stdout.strip()


def _default_remote_ref(root: Path) -> str | None:
    try:
        ref = _git(root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
        if ref.startswith("origin/"):
            return ref
    except (ValueError, OSError, subprocess.TimeoutExpired):
        pass
    for candidate in ("origin/main", "origin/master"):
        try:
            _git(root, "rev-parse", "--verify", "--quiet", candidate)
            return candidate
        except (ValueError, OSError, subprocess.TimeoutExpired):
            continue
    return None


def inspect_branches(root: Path) -> dict[str, Any]:
    """Read-only inventory of local and remote-tracking refs."""
    root = root.resolve()
    inside = _git(root, "rev-parse", "--is-inside-work-tree")
    if inside != "true":
        raise ValueError(f"Not a Git working tree: {root}")
    current = _git(root, "branch", "--show-current")
    default_ref = _default_remote_ref(root)
    local_raw = _git(root, "for-each-ref", "--format=%(refname:short)|%(objectname:short)", "refs/heads")
    remote_raw = _git(root, "for-each-ref", "--format=%(refname:short)|%(objectname:short)", "refs/remotes")
    local = []
    for line in local_raw.splitlines():
        name, _, sha = line.partition("|")
        merged = False
        if default_ref and name != current:
            try:
                _git(root, "merge-base", "--is-ancestor", name, default_ref)
                merged = True
            except ValueError:
                merged = False
        local.append({
            "name": name,
            "commit": sha,
            "current": name == current,
            "protected": name.casefold() in PROTECTED_NAMES,
            "merged_into_default": merged if default_ref else None,
        })
    remote = []
    for line in remote_raw.splitlines():
        name, _, sha = line.partition("|")
        if name.endswith("/HEAD"):
            continue
        remote.append({"name": name, "commit": sha, "is_origin": name.startswith("origin/")})
    candidates = [
        item["name"] for item in local
        if item["merged_into_default"] is True
        and not item["current"]
        and not item["protected"]
    ]
    return {
        "ok": True,
        "root": str(root),
        "current_branch": current,
        "default_remote_ref": default_ref,
        "local_branches": local,
        "remote_tracking_branches": remote,
        "local_cleanup_candidates": candidates,
        "remote_cleanup": "not-performed; remote branches are inventory-only",
        "safety_notes": [
            "Read-only inventory; no branch was deleted.",
            "Only branches proven merged into the detected origin default branch can be local cleanup candidates.",
            "Current and common protected branches are excluded.",
            "Remote-tracking refs are listed for visibility only; this command never deletes remote branches.",
            "Refresh remote-tracking refs with git fetch --prune before relying on the inventory.",
        ],
    }


def cleanup_merged_local_branches(
    root: Path, *, apply: bool = False, confirm: str | None = None
) -> dict[str, Any]:
    """Preview or delete local branches that are already merged into origin default."""
    report = inspect_branches(root)
    candidates = report["local_cleanup_candidates"]
    if not apply:
        return {
            "ok": True,
            "mode": "preview",
            "root": report["root"],
            "default_remote_ref": report["default_remote_ref"],
            "candidates": candidates,
            "deleted": [],
            "message": "Preview only. Re-run with --apply --confirm DELETE-BRANCHES to delete listed local branches.",
            "remote_branches_deleted": False,
        }
    if (confirm or "").strip().casefold() != "delete-branches":
        raise ValueError("Applying local branch cleanup requires --confirm DELETE-BRANCHES (case-insensitive)")
    if not report["default_remote_ref"]:
        raise ValueError("Cannot safely clean branches: origin default branch was not detected")
    deleted = []
    failures = []
    for name in candidates:
        try:
            _git(root, "branch", "-d", name)
            deleted.append(name)
        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
            failures.append({"branch": name, "error": str(exc)})
    return {
        "ok": not failures,
        "mode": "apply",
        "root": report["root"],
        "default_remote_ref": report["default_remote_ref"],
        "candidates": candidates,
        "deleted": deleted,
        "failures": failures,
        "remote_branches_deleted": False,
        "message": "Only merged local branches were targeted; remote branches were not deleted.",
    }
