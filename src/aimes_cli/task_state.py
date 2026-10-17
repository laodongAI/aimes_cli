from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import yaml

from .adapters import ADAPTERS

HANDOFF_REQUIRED_HEADINGS = (
    "## 1. Goal and acceptance criteria",
    "## 2. Repository state at handoff",
    "## 3. Changes made",
    "## 4. Verification evidence",
    "## 5. Open issues, risks and decisions",
    "## 6. Next steps",
    "## 7. Incoming tool checklist",
)

VALID_WRITER_STATES = {"ACTIVE", "RELEASED"}
CONTROL_PATH_PREFIXES = (".aimes/project-control/", "project-control/")


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


def _handoff_content_errors(path: Path, task_id: str, base_commit: str) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        return [f"Cannot read handoff file: {exc}"]
    errors = [f"Missing required handoff section: {heading}" for heading in HANDOFF_REQUIRED_HEADINGS if heading not in content]
    if task_id not in content:
        errors.append(f"Handoff file does not mention task ID {task_id!r}.")
    if base_commit not in content:
        errors.append("Handoff file does not record the active declaration's base_commit.")
    for field in ("Task ID:", "Baseline commit:", "Task status:", "Evidence status:"):
        if field not in content:
            errors.append(f"Handoff file is missing required metadata field: {field}")
    if "TASK-ID" in content or "<full commit SHA>" in content:
        errors.append("Handoff file still contains template placeholders.")
    return errors


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
    if status == "RELEASED":
        released_at = _parse_time(data.get("released_at"))
        if released_at is None:
            _finding(findings, "ERROR", "RELEASED_AT_INVALID", "RELEASED declarations require released_at as an ISO-8601 timestamp with timezone.")
        if not isinstance(data.get("handoff_file"), str) or not data.get("handoff_file").strip():
            _finding(findings, "ERROR", "HANDOFF_REQUIRED", "RELEASED declarations require a handoff_file.")

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
                elif status == "RELEASED":
                    for error in _handoff_content_errors(handoff_path, str(data.get("task_id", "")), str(data.get("base_commit", ""))):
                        _finding(findings, "ERROR", "HANDOFF_INCOMPLETE", error, normalized_handoff)

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


def _acquire_writer_lock(root: Path) -> tuple[Path | None, str | None]:
    root = root.resolve()
    raw_lock_path = root / ".aimes" / "project-control" / "active-writer.lock"
    lock_parent = raw_lock_path.parent.resolve()
    try:
        lock_parent.relative_to(root)
    except ValueError:
        return None, "Writer control directory resolves outside the project root; refusing to write through a symlink."
    lock_parent.mkdir(parents=True, exist_ok=True)
    lock_path = lock_parent / raw_lock_path.name
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(f"pid={os.getpid()}\\n")
        return lock_path, None
    except FileExistsError:
        return None, f"Writer control lock already exists: {lock_path}. Verify no AIMES task operation is still running before manual recovery."
    except OSError as exc:
        return None, f"Cannot acquire writer control lock: {exc}"


def _write_state_atomically(state_path: Path, data: dict[str, Any]) -> None:
    temp_path = state_path.with_name(f".{state_path.name}.{os.getpid()}.tmp")
    try:
        with temp_path.open("x", encoding="utf-8") as stream:
            yaml.safe_dump(data, stream, allow_unicode=True, sort_keys=False)
        os.replace(temp_path, state_path)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def claim_task_state(
    root: Path,
    *,
    task_id: str,
    tool_id: str,
    branch: str,
    base_commit: str,
    allowed_paths: list[str],
    lease_hours: int = 8,
    confirm: str = "",
    takeover: bool = False,
) -> dict[str, Any]:
    """Atomically claim the local writer declaration; never silently steal a live lease."""
    root = root.resolve()
    state_path = root / ".aimes" / "project-control" / "active-writer.yaml"
    findings: list[dict[str, Any]] = []
    if not root.is_dir():
        _finding(findings, "ERROR", "ROOT_NOT_DIRECTORY", f"Project root is not a directory: {root}")
        return _result(state_path, root, findings, None, [])
    if _run_git(root, "rev-parse", "--show-toplevel").returncode != 0:
        _finding(findings, "ERROR", "GIT_REQUIRED", "Claiming a writer lease requires a Git repository.")
        return _result(state_path, root, findings, None, [])
    if (confirm or "").strip().casefold() != "claim":
        _finding(findings, "ERROR", "CONFIRMATION_REQUIRED", "Claim requires --confirm CLAIM (case-insensitive).")
        return _result(state_path, root, findings, None, [])
    if not isinstance(task_id, str) or not task_id.strip():
        _finding(findings, "ERROR", "TASK_ID_REQUIRED", "task_id must be non-empty.")
    if tool_id not in ADAPTERS:
        _finding(findings, "ERROR", "UNKNOWN_TOOL", f"tool_id is not a supported AIMES tool ID: {tool_id!r}")
    if not isinstance(branch, str) or not branch.strip():
        _finding(findings, "ERROR", "BRANCH_REQUIRED", "branch must be non-empty.")
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", str(base_commit or "").strip()):
        _finding(findings, "ERROR", "BASE_COMMIT_FORMAT", "base_commit must be a 7-40 character hexadecimal Git commit SHA.")
    if type(lease_hours) is not int or not 1 <= lease_hours <= 168:
        _finding(findings, "ERROR", "LEASE_HOURS_RANGE", "lease_hours must be an integer from 1 to 168.")
    if not isinstance(allowed_paths, list) or not allowed_paths:
        _finding(findings, "ERROR", "ALLOWED_PATHS_REQUIRED", "Provide one or more --allowed-path entries.")
    else:
        for item in allowed_paths:
            _, error = _safe_relative_path(item)
            if error:
                _finding(findings, "ERROR", "ALLOWED_PATH_INVALID", f"Invalid allowed path {item!r}: {error}")
    if any(item["level"] == "ERROR" for item in findings):
        return _result(state_path, root, findings, None, [])

    lock_path, lock_error = _acquire_writer_lock(root)
    if lock_error:
        _finding(findings, "ERROR", "WRITER_LOCK_BUSY", lock_error, str(lock_path) if lock_path else None)
        return _result(state_path, root, findings, None, [])

    try:
        now = datetime.now(timezone.utc)
        existing: dict[str, Any] | None = None
        if state_path.exists():
            try:
                loaded = yaml.safe_load(state_path.read_text(encoding="utf-8-sig"))
            except (OSError, yaml.YAMLError) as exc:
                _finding(findings, "ERROR", "EXISTING_STATE_INVALID", f"Cannot safely replace existing writer declaration: {exc}")
                return _result(state_path, root, findings, None, [])
            if not isinstance(loaded, dict):
                _finding(findings, "ERROR", "EXISTING_STATE_INVALID", "Existing writer declaration is not a YAML mapping.")
                return _result(state_path, root, findings, None, [])
            existing = loaded
            if existing.get("status") not in VALID_WRITER_STATES:
                _finding(findings, "ERROR", "EXISTING_STATE_INVALID", "Existing writer declaration has an unknown status; review it manually before replacing.")
                return _result(state_path, root, findings, existing, [])
            existing_expiry = _parse_time(existing.get("lease_expires_at"))
            if existing.get("status") == "ACTIVE" and existing_expiry and existing_expiry > now:
                _finding(findings, "ERROR", "WRITER_ALREADY_ACTIVE", f"Task {existing.get('task_id')!r} already owns an unexpired writer lease.")
                return _result(state_path, root, findings, existing, [])
            if existing.get("status") == "ACTIVE" and (not existing_expiry or existing_expiry <= now):
                if not takeover or (confirm or "").strip().casefold() != "claim":
                    _finding(findings, "ERROR", "TAKEOVER_REQUIRED", "Existing writer lease is expired/invalid. Confirm ownership and use --takeover --confirm CLAIM; no automatic takeover occurs.")
                    return _result(state_path, root, findings, existing, [])
                _finding(findings, "WARNING", "EXPIRED_LEASE_TAKEOVER", "Expired writer lease is being replaced after explicit takeover confirmation.")
            elif takeover:
                _finding(findings, "WARNING", "UNNECESSARY_TAKEOVER", "The previous declaration is not an expired ACTIVE lease; --takeover was not needed.")

        git_probe = _run_git(root, "rev-parse", "--show-toplevel")
        if git_probe.returncode != 0:
            _finding(findings, "ERROR", "GIT_REQUIRED", "Claiming a writer lease requires a Git repository.")
            return _result(state_path, root, findings, None, [])
        actual_branch = _run_git(root, "branch", "--show-current").stdout.strip()
        if actual_branch and actual_branch != branch:
            _finding(findings, "ERROR", "BRANCH_MISMATCH", f"Requested branch {branch!r} does not match current branch {actual_branch!r}.")
            return _result(state_path, root, findings, None, [])
        if _run_git(root, "cat-file", "-e", f"{base_commit}^{{commit}}").returncode != 0:
            _finding(findings, "ERROR", "BASE_COMMIT_NOT_FOUND", f"base_commit does not resolve to a Git commit: {base_commit}")
            return _result(state_path, root, findings, None, [])

        data = {
            "schema_version": 1,
            "task_id": task_id.strip(),
            "tool_id": tool_id,
            "branch": branch.strip(),
            "base_commit": base_commit.strip(),
            "started_at": now.isoformat(),
            "lease_expires_at": (now + timedelta(hours=lease_hours)).isoformat(),
            "allowed_paths": list(dict.fromkeys(item.strip().replace("\\\\", "/").rstrip("/") for item in allowed_paths)),
            "status": "ACTIVE",
        }
        temp_path = state_path.with_name(f".{state_path.name}.{os.getpid()}.pending")
        try:
            with temp_path.open("x", encoding="utf-8") as stream:
                yaml.safe_dump(data, stream, allow_unicode=True, sort_keys=False)
            validation = validate_task_state(temp_path, root, require_active=True, check_scope=True)
            if not validation["ok"]:
                findings.extend(validation["findings"])
                _finding(findings, "ERROR", "CLAIM_SCOPE_REJECTED", "Writer claim rejected because current changed files violate the declared scope.")
                return _result(state_path, root, findings, data, validation.get("changed_paths", []))
            os.replace(temp_path, state_path)
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
        findings.append({"level": "INFO", "code": "WRITER_CLAIMED", "message": "Writer declaration created. This claim coordinates AIMES-aware tools on this filesystem; it cannot prevent editors that ignore the declaration from writing."})
        return _result(state_path, root, findings, data, validation.get("changed_paths", []))
    finally:
        if lock_path:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass


def release_task_state(
    root: Path,
    *,
    task_id: str,
    tool_id: str,
    handoff_file: str,
    confirm: str = "",
) -> dict[str, Any]:
    """Release the active writer declaration only after a task handoff file exists."""
    root = root.resolve()
    state_path = root / ".aimes" / "project-control" / "active-writer.yaml"
    findings: list[dict[str, Any]] = []
    if not root.is_dir():
        _finding(findings, "ERROR", "ROOT_NOT_DIRECTORY", f"Project root is not a directory: {root}")
        return _result(state_path, root, findings, None, [])
    if (confirm or "").strip().casefold() != "release":
        _finding(findings, "ERROR", "CONFIRMATION_REQUIRED", "Release requires --confirm RELEASE (case-insensitive).")
        return _result(state_path, root, findings, None, [])
    normalized_handoff, path_error = _safe_relative_path(handoff_file)
    if path_error or not normalized_handoff:
        _finding(findings, "ERROR", "HANDOFF_PATH_INVALID", f"Invalid handoff file path: {path_error or handoff_file!r}")
        return _result(state_path, root, findings, None, [])
    handoff_path = (root / normalized_handoff).resolve()
    try:
        handoff_path.relative_to(root)
    except ValueError:
        _finding(findings, "ERROR", "HANDOFF_PATH_ESCAPE", "handoff file escapes project root.")
        return _result(state_path, root, findings, None, [])
    if not handoff_path.is_file():
        _finding(findings, "ERROR", "HANDOFF_FILE_MISSING", f"Handoff file must exist before releasing the writer: {normalized_handoff}")
        return _result(state_path, root, findings, None, [])

    lock_path, lock_error = _acquire_writer_lock(root)
    if lock_error:
        _finding(findings, "ERROR", "WRITER_LOCK_BUSY", lock_error)
        return _result(state_path, root, findings, None, [])
    try:
        if not state_path.is_file():
            _finding(findings, "ERROR", "ACTIVE_WRITER_MISSING", "No active-writer declaration exists.")
            return _result(state_path, root, findings, None, [])
        try:
            data = yaml.safe_load(state_path.read_text(encoding="utf-8-sig"))
        except (OSError, yaml.YAMLError) as exc:
            _finding(findings, "ERROR", "STATE_READ", f"Cannot read active-writer declaration: {exc}")
            return _result(state_path, root, findings, None, [])
        if not isinstance(data, dict):
            _finding(findings, "ERROR", "STATE_ROOT_TYPE", "Active-writer declaration must be a YAML mapping.")
            return _result(state_path, root, findings, None, [])
        if data.get("status") != "ACTIVE" or data.get("task_id") != task_id or data.get("tool_id") != tool_id:
            _finding(findings, "ERROR", "WRITER_IDENTITY_MISMATCH", "Only the matching active task/tool may release this writer declaration.")
            return _result(state_path, root, findings, data, [])
        handoff_errors = _handoff_content_errors(handoff_path, task_id, str(data.get("base_commit", "")))
        if handoff_errors:
            for error in handoff_errors:
                _finding(findings, "ERROR", "HANDOFF_INCOMPLETE", error, normalized_handoff)
            return _result(state_path, root, findings, data, [])
        data["status"] = "RELEASED"
        data["released_at"] = datetime.now(timezone.utc).isoformat()
        data["handoff_file"] = normalized_handoff
        _write_state_atomically(state_path, data)
        findings.append({"level": "INFO", "code": "WRITER_RELEASED", "message": "Writer declaration released after verifying the handoff file exists."})
        return _result(state_path, root, findings, data, [])
    finally:
        if lock_path:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
