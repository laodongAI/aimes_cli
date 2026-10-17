from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import yaml

from .adapters import ADAPTERS

VALID_WRITER_STATES = {"ACTIVE", "RELEASED"}
CONTROL_PATH_PREFIXES = (".aimes/project-control/", "project-control/handoffs/")


def _finding(findings: list[dict[str, Any]], level: str, code: str, message: str, path: str | None = None) -> None:
    item: dict[str, Any] = {"level": level, "code": code, "message": message}
    if path:
        item["path"] = path
    findings.append(item)


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _safe_relative_path(value: Any) -> tuple[str | None, str | None]:
    if not isinstance(value, str) or not value.strip():
        return None, "path must be a non-empty string"
    normalized = value.strip().replace("\\", "/")
    posix = PurePosixPath(normalized)
    windows = PureWindowsPath(normalized)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        return None, "absolute paths are not allowed"
    if any(part == ".." for part in posix.parts):
        return None, "parent traversal ('..') is not allowed"
    if normalized in {"", "."}:
        return None, "path must identify a file or directory"
    return normalized, None


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def _git_context(root: Path, base_commit: str, findings: list[dict[str, Any]]) -> tuple[str | None, set[str] | None]:
    probe = _run_git(root, "rev-parse", "--show-toplevel")
    if probe.returncode != 0:
        _finding(findings, "WARNING", "GIT_UNAVAILABLE", "Git repository not detected; branch/base/scope checks were skipped.")
        return None, None
    repo_root = Path(probe.stdout.strip()).resolve()
    try:
        project_prefix = root.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        _finding(findings, "ERROR", "PROJECT_OUTSIDE_REPOSITORY", "Project root is not inside the detected Git repository.")
        return None, None
    pathspec = project_prefix if project_prefix != "." else "."

    branch_result = _run_git(root, "branch", "--show-current")
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None

    commit_result = _run_git(root, "cat-file", "-e", f"{base_commit}^{{commit}}")
    if commit_result.returncode != 0:
        _finding(findings, "ERROR", "BASE_COMMIT_NOT_FOUND", f"base_commit does not resolve to a Git commit: {base_commit}")

    changed: set[str] = set()
    if commit_result.returncode == 0:
        diff = _run_git(root, "diff", "--name-only", base_commit, "--", pathspec)
        if diff.returncode == 0:
            for line in diff.stdout.splitlines():
                normalized = line.replace("\\", "/")
                if project_prefix != "." and normalized.startswith(project_prefix + "/"):
                    normalized = normalized[len(project_prefix) + 1:]
                if normalized:
                    changed.add(normalized)
        untracked = _run_git(root, "ls-files", "--others", "--exclude-standard", "--", pathspec)
        if untracked.returncode == 0:
            for line in untracked.stdout.splitlines():
                normalized = line.replace("\\", "/")
                if project_prefix != "." and normalized.startswith(project_prefix + "/"):
                    normalized = normalized[len(project_prefix) + 1:]
                if normalized:
                    changed.add(normalized)
    return branch, changed


def validate_task_state(
    path: Path,
    root: Path,
    *,
    require_active: bool = False,
    check_scope: bool = True,
) -> dict[str, Any]:
    """Read-only validation of the active-writer declaration and task change scope."""
    root = root.resolve()
    path = path.resolve()
    findings: list[dict[str, Any]] = []
    try:
        path.relative_to(root)
    except ValueError:
        _finding(findings, "ERROR", "STATE_PATH_ESCAPE", "Active-writer state path must be inside the project root.", str(path))
        return _result(path, root, findings, None, [])

    if not path.is_file():
        level = "ERROR" if require_active else "WARNING"
        code = "ACTIVE_WRITER_REQUIRED" if require_active else "NO_ACTIVE_WRITER"
        message = "No active-writer declaration exists; claim a task before making governed changes." if require_active else "No active-writer declaration exists; no task is currently claimed."
        _finding(findings, level, code, message, path.relative_to(root).as_posix())
        return _result(path, root, findings, None, [])

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except (OSError, yaml.YAMLError) as exc:
        _finding(findings, "ERROR", "STATE_READ", f"Cannot read active-writer declaration: {exc}", path.relative_to(root).as_posix())
        return _result(path, root, findings, None, [])

    if not isinstance(data, dict):
        _finding(findings, "ERROR", "STATE_ROOT_TYPE", "Active-writer declaration must be a YAML mapping.", path.relative_to(root).as_posix())
        return _result(path, root, findings, None, [])

    required = ("schema_version", "task_id", "tool_id", "branch", "base_commit", "started_at", "lease_expires_at", "allowed_paths", "status")
    for field in required:
        if field not in data:
            _finding(findings, "ERROR", "REQUIRED_FIELD", f"Missing required field: {field}", path.relative_to(root).as_posix())
    if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
        _finding(findings, "ERROR", "SCHEMA_VERSION", "schema_version must be integer 1.")
    for field in ("task_id", "branch", "base_commit"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            _finding(findings, "ERROR", "FIELD_VALUE", f"{field} must be a non-empty string.")
    base_commit_value = data.get("base_commit")
    if isinstance(base_commit_value, str) and base_commit_value.strip() and not re.fullmatch(r"[0-9a-fA-F]{7,40}", base_commit_value.strip()):
        _finding(findings, "ERROR", "BASE_COMMIT_FORMAT", "base_commit must be a 7-40 character hexadecimal Git commit SHA.")
    tool_id = data.get("tool_id")
    if tool_id not in ADAPTERS:
        _finding(findings, "ERROR", "UNKNOWN_TOOL", f"tool_id is not a supported AIMES tool ID: {tool_id!r}")

    status = data.get("status")
    if status not in VALID_WRITER_STATES:
        _finding(findings, "ERROR", "INVALID_WRITER_STATUS", f"status must be one of {sorted(VALID_WRITER_STATES)}.")

    started = _parse_time(data.get("started_at"))
    expires = _parse_time(data.get("lease_expires_at"))
    if started is None:
        _finding(findings, "ERROR", "STARTED_AT_INVALID", "started_at must be an ISO-8601 timestamp with timezone.")
    if expires is None:
        _finding(findings, "ERROR", "LEASE_EXPIRY_INVALID", "lease_expires_at must be an ISO-8601 timestamp with timezone.")
    if started and expires and expires <= started:
        _finding(findings, "ERROR", "LEASE_RANGE_INVALID", "lease_expires_at must be later than started_at.")

    lease_expired = bool(expires and expires <= datetime.now(timezone.utc))
    if status == "ACTIVE" and lease_expired:
        _finding(findings, "WARNING", "LEASE_EXPIRED", "Writer lease has expired; confirm ownership before continuing.")

    raw_paths = data.get("allowed_paths")
    allowed_paths: list[str] = []
    if not isinstance(raw_paths, list) or not raw_paths:
        _finding(findings, "ERROR", "ALLOWED_PATHS_REQUIRED", "allowed_paths must be a non-empty list.")
    else:
        for item in raw_paths:
            normalized, error = _safe_relative_path(item)
            if error:
                _finding(findings, "ERROR", "ALLOWED_PATH_INVALID", f"Invalid allowed_paths entry {item!r}: {error}")
            elif normalized and normalized not in allowed_paths:
                allowed_paths.append(normalized.rstrip("/"))

    handoff_file = data.get("handoff_file")
    if handoff_file is not None:
        normalized_handoff, error = _safe_relative_path(handoff_file)
        if error:
            _finding(findings, "ERROR", "HANDOFF_PATH_INVALID", f"Invalid handoff_file: {error}")
        else:
            handoff_path = (root / normalized_handoff).resolve()
            try:
                handoff_path.relative_to(root)
            except ValueError:
                _finding(findings, "ERROR", "HANDOFF_PATH_ESCAPE", "handoff_file escapes project root.")
            else:
                if not handoff_path.is_file():
                    _finding(findings, "ERROR", "HANDOFF_FILE_MISSING", f"handoff_file does not exist: {normalized_handoff}")

    actual_branch = None
    changed_paths: set[str] = set()
    if status == "ACTIVE" and isinstance(data.get("base_commit"), str) and data["base_commit"].strip():
        actual_branch, changed = _git_context(root, data["base_commit"], findings)
        if changed is not None:
            changed_paths = changed
        if actual_branch and isinstance(data.get("branch"), str) and actual_branch != data["branch"]:
            _finding(findings, "ERROR", "BRANCH_MISMATCH", f"Declaration branch {data['branch']!r} does not match current branch {actual_branch!r}.")
        if check_scope and changed is not None:
            for changed_path in sorted(changed_paths):
                if changed_path.startswith(CONTROL_PATH_PREFIXES):
                    continue
                if not any(changed_path == allowed or changed_path.startswith(allowed.rstrip("/") + "/") for allowed in allowed_paths):
                    _finding(findings, "ERROR", "CHANGE_OUTSIDE_SCOPE", f"Changed path is outside allowed_paths: {changed_path}", changed_path)

    if require_active and (status != "ACTIVE" or lease_expired):
        _finding(findings, "ERROR", "WRITER_NOT_ACTIVE", "An unexpired ACTIVE writer declaration is required.")

    return _result(path, root, findings, data, sorted(changed_paths))


def _result(path: Path, root: Path, findings: list[dict[str, Any]], data: dict[str, Any] | None, changed_paths: list[str]) -> dict[str, Any]:
    errors = sum(item["level"] == "ERROR" for item in findings)
    warnings = sum(item["level"] == "WARNING" for item in findings)
    expires = _parse_time(data.get("lease_expires_at")) if data else None
    status = data.get("status") if data else None
    return {
        "schema_version": 1,
        "validator": "aimes-task-state-validator",
        "root": str(root),
        "source": str(path),
        "ok": errors == 0,
        "writer_active": status == "ACTIVE" and bool(expires and expires > datetime.now(timezone.utc)),
        "task_id": data.get("task_id") if data else None,
        "tool_id": data.get("tool_id") if data else None,
        "branch": data.get("branch") if data else None,
        "allowed_paths": data.get("allowed_paths", []) if data else [],
        "changed_paths": changed_paths,
        "summary": {"errors": errors, "warnings": warnings, "findings": len(findings)},
        "findings": findings,
        "note": "This is a read-only declaration/scope check, not an atomic filesystem lock. Coordinate writers through one shared workspace or isolated worktrees.",
    }
