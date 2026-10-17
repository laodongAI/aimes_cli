from __future__ import annotations

import fnmatch
import os
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import yaml

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".aimes", "build", "dist"}
TEMP_DIR_PATTERNS = (
    ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "pip-build-tracker-*", "pip-ephem-wheel-cache-*", "pip-install-*",
)
TEMP_FILE_SUFFIXES = (".tmp", ".temp", ".pyc")
VALID_CLASSES = {"A", "B", "C"}
VALID_STATUSES = {"ACTIVE", "KEEP", "CLEANUP_CANDIDATE", "REMOVED"}


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


def _safe_path(root: Path, value: Any) -> tuple[str | None, Path | None, str | None]:
    if not isinstance(value, str) or not value.strip():
        return None, None, "path must be a non-empty string"
    normalized = value.strip().replace("\\", "/")
    posix, windows = PurePosixPath(normalized), PureWindowsPath(normalized)
    if posix.is_absolute() or windows.is_absolute() or windows.drive or any(part == ".." for part in posix.parts):
        return None, None, "path must be relative and cannot contain '..'"
    candidate = (root / normalized).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None, None, "path resolves outside project root"
    return normalized, candidate, None


def _size_bytes(path: Path) -> int:
    try:
        if path.is_symlink():
            return 0
        if path.is_file():
            return path.stat().st_size
        if path.is_dir():
            total = 0
            for current, dirs, files in os.walk(path, followlinks=False):
                dirs[:] = [name for name in dirs if not (Path(current) / name).is_symlink()]
                for name in files:
                    item = Path(current) / name
                    if not item.is_symlink():
                        try:
                            total += item.stat().st_size
                        except OSError:
                            pass
            return total
    except OSError:
        return 0
    return 0


def _is_temp_candidate(path: Path) -> tuple[bool, str, str]:
    name = path.name
    for pattern in TEMP_DIR_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            return True, "A", f"known regenerable temporary/cache directory ({pattern})"
    if name.endswith(".pyc"):
        return True, "A", "Python bytecode cache file"
    if name.endswith(TEMP_FILE_SUFFIXES):
        return True, "B", "temporary file suffix; inspect before cleanup"
    return False, "", ""


def audit_temp_registry(root: Path, registry_path: Path | None = None, *, max_scan_entries: int = 10000) -> dict[str, Any]:
    root = root.resolve()
    registry_path = (registry_path or Path(".aimes/temp-registry.yaml"))
    registry_path = (root / registry_path).resolve() if not registry_path.is_absolute() else registry_path.resolve()
    findings: list[dict[str, Any]] = []
    try:
        registry_path.relative_to(root)
    except ValueError:
        _finding(findings, "ERROR", "REGISTRY_PATH_ESCAPE", "Temporary registry must be inside the project root.")
        return _result(root, registry_path, findings, [], 0)

    entries: list[Any] = []
    registry_exists = registry_path.is_file()
    if registry_exists:
        try:
            data = yaml.safe_load(registry_path.read_text(encoding="utf-8-sig"))
        except (OSError, yaml.YAMLError) as exc:
            _finding(findings, "ERROR", "REGISTRY_READ", f"Cannot read temporary registry: {exc}", registry_path.relative_to(root).as_posix())
            data = None
        if not isinstance(data, dict):
            _finding(findings, "ERROR", "REGISTRY_ROOT_TYPE", "Temporary registry must be a YAML mapping.", registry_path.relative_to(root).as_posix())
        else:
            if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
                _finding(findings, "ERROR", "SCHEMA_VERSION", "schema_version must be integer 1.", registry_path.relative_to(root).as_posix())
            entries_value = data.get("entries", [])
            if not isinstance(entries_value, list):
                _finding(findings, "ERROR", "ENTRIES_TYPE", "entries must be a list.", registry_path.relative_to(root).as_posix())
            else:
                entries = entries_value
    else:
        _finding(findings, "WARNING", "REGISTRY_MISSING", "Temporary registry is missing; audit is scanning for common unregistered candidates.", ".aimes/temp-registry.yaml")

    seen_ids: set[str] = set()
    registered: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for index, entry in enumerate(entries):
        loc = f"entries[{index}]"
        if not isinstance(entry, dict):
            _finding(findings, "ERROR", "ENTRY_TYPE", f"{loc} must be a mapping.")
            continue
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not entry_id.strip():
            _finding(findings, "ERROR", "ID_REQUIRED", f"{loc}.id is required.")
        elif entry_id in seen_ids:
            _finding(findings, "ERROR", "DUPLICATE_ID", f"Duplicate temporary registry ID: {entry_id}")
        else:
            seen_ids.add(entry_id)
        rel, path, path_error = _safe_path(root, entry.get("path"))
        if path_error or not rel or path is None:
            _finding(findings, "ERROR", "PATH_INVALID", f"{loc}.path: {path_error}")
            continue
        if entry.get("classification") not in VALID_CLASSES:
            _finding(findings, "ERROR", "CLASSIFICATION_INVALID", f"{loc}.classification must be A, B or C.", rel)
        if entry.get("status") not in VALID_STATUSES:
            _finding(findings, "ERROR", "STATUS_INVALID", f"{loc}.status must be one of {sorted(VALID_STATUSES)}.", rel)
        if not isinstance(entry.get("purpose"), str) or not entry.get("purpose", "").strip():
            _finding(findings, "ERROR", "PURPOSE_REQUIRED", f"{loc}.purpose is required.", rel)
        created = _parse_time(entry.get("created_at"))
        if created is None:
            _finding(findings, "ERROR", "CREATED_AT_INVALID", f"{loc}.created_at is required and must be ISO-8601 with timezone.", rel)
        expires = _parse_time(entry.get("expires_at"))
        if entry.get("expires_at") is not None and expires is None:
            _finding(findings, "ERROR", "EXPIRY_INVALID", f"{loc}.expires_at must be ISO-8601 with timezone.", rel)
        status = entry.get("status")
        if status in {"ACTIVE", "CLEANUP_CANDIDATE"} and expires is None:
            _finding(findings, "WARNING", "TEMP_EXPIRY_UNKNOWN", "Active/candidate temporary items need an expiry time.", rel)
        exists = path.exists()
        if status == "REMOVED" and exists:
            _finding(findings, "WARNING", "REMOVED_PATH_STILL_EXISTS", "Entry is marked REMOVED but the path still exists.", rel)
        elif status != "REMOVED" and not exists:
            _finding(findings, "WARNING", "REGISTERED_PATH_MISSING", "Registered temporary path does not exist.", rel)
        if status not in {"KEEP", "REMOVED"} and expires and expires <= now:
            _finding(findings, "WARNING", "TEMP_EXPIRED", "Registered temporary item has passed its expiry time.", rel)
        registered.append({
            "id": entry_id,
            "path": rel,
            "classification": entry.get("classification"),
            "status": status,
            "exists": exists,
            "expired": bool(expires and expires <= now and status not in {"KEEP", "REMOVED"}),
            "expiry_known": expires is not None,
            "size_bytes": _size_bytes(path) if exists else 0,
        })

    registered_paths = [item["path"].rstrip("/") for item in registered]
    candidates: list[dict[str, Any]] = []
    scanned = 0
    scan_limited = False
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        try:
            current_rel = current_path.relative_to(root)
        except ValueError:
            dirs[:] = []
            continue
        if current_rel.parts and current_rel.parts[0] in SKIP_DIRS:
            dirs[:] = []
            continue
        filtered_dirs = []
        for name in dirs:
            child = current_path / name
            if child.is_symlink():
                continue
            is_candidate, risk, reason = _is_temp_candidate(child)
            rel = child.relative_to(root).as_posix()
            scanned += 1
            if is_candidate:
                is_registered = any(rel == item or rel.startswith(item + "/") for item in registered_paths)
                candidates.append({"path": rel, "kind": "directory", "risk_class": risk, "reason": reason, "registered": is_registered, "size_bytes": _size_bytes(child)})
                if not is_registered:
                    _finding(findings, "WARNING", "UNREGISTERED_TEMP_CANDIDATE", f"Unregistered temporary candidate: {reason}", rel)
                continue
            filtered_dirs.append(name)
            if scanned >= max_scan_entries:
                scan_limited = True
                break
        dirs[:] = filtered_dirs
        if scan_limited:
            break
        for name in files:
            child = current_path / name
            if child.is_symlink():
                continue
            is_candidate, risk, reason = _is_temp_candidate(child)
            scanned += 1
            if is_candidate:
                rel = child.relative_to(root).as_posix()
                is_registered = any(rel == item or rel.startswith(item + "/") for item in registered_paths)
                candidates.append({"path": rel, "kind": "file", "risk_class": risk, "reason": reason, "registered": is_registered, "size_bytes": _size_bytes(child)})
                if not is_registered:
                    _finding(findings, "WARNING", "UNREGISTERED_TEMP_CANDIDATE", f"Unregistered temporary candidate: {reason}", rel)
            if scanned >= max_scan_entries:
                scan_limited = True
                break
        if scan_limited:
            break
    if scan_limited:
        _finding(findings, "WARNING", "SCAN_LIMIT", f"Scan stopped at max_scan_entries={max_scan_entries}; report is partial.")

    return _result(root, registry_path, findings, registered + candidates, scanned, registry_exists, candidates)


def _result(root: Path, registry_path: Path, findings: list[dict[str, Any]], items: list[dict[str, Any]], scanned: int, registry_exists: bool = False, candidates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    errors = sum(item["level"] == "ERROR" for item in findings)
    warnings = sum(item["level"] == "WARNING" for item in findings)
    registered = [item for item in items if "id" in item]
    candidates = candidates or []
    compliant = sum(
        (item.get("status") in {"KEEP", "REMOVED"} and (item.get("status") == "KEEP" and item.get("exists") or item.get("status") == "REMOVED" and not item.get("exists")))
        or (item.get("status") in {"ACTIVE", "CLEANUP_CANDIDATE"} and item.get("exists") and item.get("expiry_known") and not item.get("expired"))
        for item in registered
    )
    total = len(registered) + sum(not item.get("registered") for item in candidates)
    rate = compliant / total if total else None
    return {
        "schema_version": 1,
        "validator": "aimes-cleanup-audit",
        "root": str(root),
        "registry": str(registry_path),
        "ok": errors == 0,
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "findings": len(findings),
            "registry_exists": registry_exists,
            "registered_entries": len(registered),
            "scanned_entries": scanned,
            "candidate_count": len(candidates),
            "unregistered_candidates": sum(not item.get("registered") for item in candidates),
            "expired_registered_entries": sum(bool(item.get("expired")) for item in registered),
            "candidate_bytes": sum(item.get("size_bytes", 0) for item in candidates),
            "compliant_items": compliant,
            "total_temp_items": total,
            "temp_file_compliance_rate": rate,
        },
        "registered_entries": registered,
        "candidates": candidates,
        "findings": findings,
        "note": "Read-only audit. No files are deleted or modified. Classification A is only a candidate category, not automatic deletion permission.",
    }
