from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .workflow import validate_workflow_definition

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _add(findings: list[dict], level: str, code: str, message: str) -> None:
    findings.append({"level": level, "code": code, "message": message})


def _load(path: Path) -> Any:
    if not path.is_file():
        raise ValueError(f"Workflow file does not exist or is not a file: {path}")
    try:
        raw = path.read_text(encoding="utf-8-sig")
        return json.loads(raw) if path.suffix.lower() == ".json" else yaml.safe_load(raw)
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"Cannot parse {path}: {exc}") from exc


def _within_root(path: Path, root: Path) -> tuple[Path | None, str | None]:
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None, "path must remain inside the project root"
    return resolved, None


def _definition_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _result(path: Path, findings: list[dict], **extra) -> dict:
    errors = sum(item["level"] == "ERROR" for item in findings)
    warnings = sum(item["level"] == "WARNING" for item in findings)
    return {
        "schema_version": 1,
        "validator": "aimes-workflow-run",
        "source": str(path),
        "ok": errors == 0,
        "summary": {"errors": errors, "warnings": warnings, "findings": len(findings)},
        "findings": findings,
        **extra,
        "note": "本地运行记录可被修改；校验不提供签名或防篡改保证，也不证明外部动作真实完成。",
    }


def validate_workflow_run(definition_path: Path, record_path: Path, root: Path) -> dict:
    findings: list[dict] = []
    definition_result = validate_workflow_definition(definition_path)
    if not definition_result["ok"]:
        _add(findings, "ERROR", "WORKFLOW_DEFINITION_INVALID", "Workflow definition failed validation; run record cannot be trusted against it.")
        for item in definition_result.get("findings", []):
            if item.get("level") == "ERROR":
                _add(findings, "ERROR", f"DEFINITION_{item.get('code', 'ERROR')}", item.get("message", "Workflow definition invalid"))
    try:
        definition = _load(definition_path)
        data = _load(record_path)
    except ValueError as exc:
        _add(findings, "ERROR", "RUN_UNREADABLE", str(exc))
        return _result(record_path, findings)
    if not isinstance(data, dict):
        _add(findings, "ERROR", "RUN_ROOT_TYPE", "Workflow run record must be an object")
        return _result(record_path, findings)
    if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
        _add(findings, "ERROR", "RUN_SCHEMA_VERSION", "Workflow run schema_version must be integer 1")
    required = ("run_id", "workflow_id", "workflow_version", "definition_sha256", "task_id", "baseline_commit", "current_state", "status", "attempts", "history", "created_at", "updated_at")
    for key in required:
        if key not in data:
            _add(findings, "ERROR", "RUN_FIELD_REQUIRED", f"Missing run record field: {key}")
    for key in ("run_id", "workflow_id", "workflow_version", "definition_sha256", "task_id", "baseline_commit", "current_state"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            _add(findings, "ERROR", "RUN_FIELD_VALUE", f"{key} must be a non-empty string")
    if not isinstance(data.get("run_id"), str) or not RUN_ID_PATTERN.fullmatch(data.get("run_id", "")) or data.get("run_id") in {".", ".."}:
        _add(findings, "ERROR", "RUN_ID_INVALID", "run_id must use only letters, digits, dot, underscore or hyphen and cannot traverse paths")
    if data.get("workflow_id") != definition.get("workflow_id") or data.get("workflow_version") != definition.get("version"):
        _add(findings, "ERROR", "WORKFLOW_IDENTITY_MISMATCH", "Run record workflow ID/version does not match the supplied definition")
    try:
        expected_hash = _definition_hash(definition_path)
        if data.get("definition_sha256") != expected_hash:
            _add(findings, "ERROR", "WORKFLOW_DEFINITION_CHANGED", "Workflow definition changed after this run started; review before resuming")
    except OSError as exc:
        _add(findings, "ERROR", "WORKFLOW_HASH_UNREADABLE", str(exc))
    states = {state.get("state_id"): state for state in definition.get("states", []) if isinstance(state, dict) and isinstance(state.get("state_id"), str)}
    current = data.get("current_state")
    if isinstance(current, str) and current not in states:
        _add(findings, "ERROR", "CURRENT_STATE_UNKNOWN", f"current_state does not exist in definition: {current}")
    status = data.get("status")
    if not isinstance(status, str) or status not in {"IN_PROGRESS", "SUCCESS", "FAILURE", "BLOCKED", "CANCELLED"}:
        _add(findings, "ERROR", "RUN_STATUS", "status must be IN_PROGRESS or a terminal workflow outcome")
    elif isinstance(current, str) and current in states:
        expected_status = states[current].get("terminal_outcome") or "IN_PROGRESS"
        if status != expected_status:
            _add(findings, "ERROR", "RUN_STATUS_MISMATCH", f"Run status {status} does not match current state outcome {expected_status}")
    attempts = data.get("attempts")
    if not isinstance(attempts, dict) or any(not isinstance(k, str) or type(v) is not int or v < 1 for k, v in (attempts.items() if isinstance(attempts, dict) else [])):
        _add(findings, "ERROR", "ATTEMPTS_SHAPE", "attempts must map state IDs to positive integer attempt counts")
    elif any(state_id not in states for state_id in attempts):
        _add(findings, "ERROR", "ATTEMPTS_UNKNOWN_STATE", "attempts contains a state ID not present in the workflow definition")
    history = data.get("history")
    if not isinstance(history, list) or not history:
        _add(findings, "ERROR", "HISTORY_REQUIRED", "history must be a non-empty list")
    else:
        for i, event in enumerate(history):
            if not isinstance(event, dict):
                _add(findings, "ERROR", "HISTORY_EVENT_TYPE", f"history[{i}] must be an object")
                continue
            for key in ("event_id", "event", "to", "timestamp", "actor"):
                if not isinstance(event.get(key), str) or not event[key].strip():
                    _add(findings, "ERROR", "HISTORY_FIELD_REQUIRED", f"history[{i}].{key} must be a non-empty string")
        last = history[-1]
        if isinstance(last, dict) and last.get("to") != current:
            _add(findings, "ERROR", "HISTORY_CURRENT_STATE_MISMATCH", "The last history event target does not match current_state")
    for key in ("created_at", "updated_at"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            _add(findings, "ERROR", "RUN_TIMESTAMP_REQUIRED", f"{key} must be a non-empty timestamp")
    return _result(record_path, findings, run_id=data.get("run_id"), current_state=current, status=status, history_events=len(history) if isinstance(history, list) else 0)


def start_workflow_run(
    definition_path: Path, record_path: Path, root: Path, *, run_id: str,
    task_id: str, baseline_commit: str, actor: str = "local-user",
    approval_ref: str | None = None, confirm: str = "",
) -> dict:
    findings: list[dict] = []
    if confirm.strip().upper() != "START":
        _add(findings, "ERROR", "CONFIRMATION_REQUIRED", "Starting a workflow run requires --confirm START")
        return _result(record_path, findings)
    if not RUN_ID_PATTERN.fullmatch(run_id or "") or run_id in {".", ".."}:
        _add(findings, "ERROR", "RUN_ID_INVALID", "run_id must use only letters, digits, dot, underscore or hyphen and cannot traverse paths")
    for name, value in (("task_id", task_id), ("baseline_commit", baseline_commit), ("actor", actor)):
        if not isinstance(value, str) or not value.strip():
            _add(findings, "ERROR", "FIELD_REQUIRED", f"{name} must be a non-empty string")
    safe_definition, definition_error = _within_root(definition_path, root)
    safe_record, record_error = _within_root(record_path, root)
    if definition_error:
        _add(findings, "ERROR", "DEFINITION_PATH_ESCAPE", definition_error)
    if record_error:
        _add(findings, "ERROR", "RUN_PATH_ESCAPE", record_error)
    if findings:
        return _result(record_path, findings)
    assert safe_definition is not None and safe_record is not None
    definition_validation = validate_workflow_definition(safe_definition)
    if not definition_validation["ok"]:
        _add(findings, "ERROR", "WORKFLOW_DEFINITION_INVALID", "Workflow definition failed validation")
        return _result(safe_record, findings, definition_validation=definition_validation)
    definition = _load(safe_definition)
    states = {state["state_id"]: state for state in definition["states"]}
    entry_state = definition["entry_state"]
    if states[entry_state].get("terminal_outcome") is not None:
        _add(findings, "ERROR", "ENTRY_STATE_TERMINAL", "Workflow entry_state cannot be terminal")
        return _result(safe_record, findings)
    if states[entry_state].get("approval_required") and not (isinstance(approval_ref, str) and approval_ref.strip()):
        _add(findings, "ERROR", "APPROVAL_REQUIRED", "Entry state requires an approval reference")
        return _result(safe_record, findings)
    if safe_record.exists():
        _add(findings, "ERROR", "RUN_FILE_EXISTS", f"Refusing to overwrite existing workflow run record: {safe_record}")
        return _result(safe_record, findings)
    now = _now()
    record = {
        "schema_version": 1,
        "run_id": run_id,
        "workflow_id": definition["workflow_id"],
        "workflow_version": definition["version"],
        "definition_sha256": _definition_hash(safe_definition),
        "task_id": task_id,
        "baseline_commit": baseline_commit,
        "current_state": entry_state,
        "status": "IN_PROGRESS",
        "attempts": {entry_state: 1},
        "created_at": now,
        "updated_at": now,
        "history": [{
            "event_id": f"evt-{uuid.uuid4().hex[:16]}",
            "event": "START",
            "from": "",
            "to": entry_state,
            "timestamp": now,
            "actor": actor,
            "evidence_refs": [],
            "approval_ref": approval_ref or "",
        }],
    }
    safe_record.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(safe_record), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except FileExistsError:
        _add(findings, "ERROR", "RUN_FILE_EXISTS", f"Refusing to overwrite existing workflow run record: {safe_record}")
    except OSError as exc:
        _add(findings, "ERROR", "RUN_WRITE_FAILED", f"Could not create workflow run record: {exc}")
    return _result(safe_record, findings, run_id=run_id, current_state=entry_state, status="IN_PROGRESS")


def transition_workflow_run(
    definition_path: Path, record_path: Path, root: Path, *, event: str,
    actor: str = "local-user", evidence_refs: list[str] | None = None,
    approval_ref: str | None = None, guard_evidence: str | None = None,
    confirm: str = "",
) -> dict:
    findings: list[dict] = []
    if confirm.strip().upper() != "TRANSITION":
        _add(findings, "ERROR", "CONFIRMATION_REQUIRED", "Workflow state changes require --confirm TRANSITION")
        return _result(record_path, findings)
    safe_definition, definition_error = _within_root(definition_path, root)
    safe_record, record_error = _within_root(record_path, root)
    if definition_error:
        _add(findings, "ERROR", "DEFINITION_PATH_ESCAPE", definition_error)
    if record_error:
        _add(findings, "ERROR", "RUN_PATH_ESCAPE", record_error)
    if findings:
        return _result(record_path, findings)
    assert safe_definition is not None and safe_record is not None
    validation = validate_workflow_run(safe_definition, safe_record, root)
    if not validation["ok"]:
        return validation
    definition = _load(safe_definition)
    record = _load(safe_record)
    if record.get("status") != "IN_PROGRESS":
        _add(findings, "ERROR", "RUN_ALREADY_TERMINAL", "Terminal workflow runs cannot transition")
        return _result(safe_record, findings, run_id=record.get("run_id"), current_state=record.get("current_state"), status=record.get("status"))
    current = record["current_state"]
    state_by_id = {state["state_id"]: state for state in definition["states"]}
    if not isinstance(event, str) or not event.strip():
        _add(findings, "ERROR", "EVENT_REQUIRED", "event must be a non-empty string")
        return _result(safe_record, findings)
    if not isinstance(actor, str) or not actor.strip():
        _add(findings, "ERROR", "ACTOR_REQUIRED", "actor must be a non-empty string")
        return _result(safe_record, findings)
    matches = [item for item in definition["transitions"] if item.get("from") == current and item.get("on") == event]
    if not matches:
        _add(findings, "ERROR", "TRANSITION_NOT_ALLOWED", f"No transition from {current} on event {event}")
        return _result(safe_record, findings, current_state=current)
    if len(matches) != 1:
        _add(findings, "ERROR", "TRANSITION_AMBIGUOUS", f"More than one transition from {current} on event {event}; use unique event routes")
        return _result(safe_record, findings, current_state=current)
    transition = matches[0]
    target = transition["to"]
    current_state = state_by_id[current]
    target_state = state_by_id[target]
    attempts = record["attempts"]
    current_attempts = attempts.get(current, 1)
    if event == "retry":
        if current_state.get("retry_mode") == "never" or current_attempts >= current_state.get("max_attempts", 1):
            _add(findings, "ERROR", "RETRY_NOT_ALLOWED", f"Retry limit reached or retry is forbidden for state {current}")
        if current_state.get("retry_mode") == "guarded" and not (isinstance(guard_evidence, str) and guard_evidence.strip()):
            _add(findings, "ERROR", "RETRY_GUARD_EVIDENCE_REQUIRED", "Guarded retries require --guard-evidence")
    if transition.get("guard") and not (isinstance(guard_evidence, str) and guard_evidence.strip()):
        _add(findings, "ERROR", "TRANSITION_GUARD_EVIDENCE_REQUIRED", "This transition has a guard; provide --guard-evidence")
    if target_state.get("approval_required") and target != current and not (isinstance(approval_ref, str) and approval_ref.strip()):
        _add(findings, "ERROR", "APPROVAL_REQUIRED", f"Target state {target} requires --approval-ref")
    if event == "approval_denied" and target_state.get("terminal_outcome") not in {"BLOCKED", "CANCELLED"}:
        _add(findings, "ERROR", "APPROVAL_DENIAL_TARGET", "approval_denied must transition to a BLOCKED or CANCELLED terminal state")
    if findings:
        return _result(safe_record, findings, run_id=record.get("run_id"), current_state=current, status=record.get("status"))

    now = _now()
    backup_dir = root.resolve() / ".aimes" / "backups" / "workflow-runs" / record["run_id"]
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{_timestamp_slug()}.json"
    shutil.copy2(safe_record, backup_path)
    if event == "retry":
        attempts[current] = current_attempts + 1
    else:
        attempts.setdefault(target, 1)
    record["current_state"] = target
    record["status"] = target_state.get("terminal_outcome") or "IN_PROGRESS"
    record["updated_at"] = now
    record["history"].append({
        "event_id": f"evt-{uuid.uuid4().hex[:16]}",
        "event": event,
        "from": current,
        "to": target,
        "timestamp": now,
        "actor": actor,
        "evidence_refs": evidence_refs or [],
        "approval_ref": approval_ref or "",
        "guard_evidence": guard_evidence or "",
        "attempt": attempts.get(target, attempts.get(current, 1)),
        "backup_path": backup_path.relative_to(root.resolve()).as_posix(),
    })
    fd, temp_name = tempfile.mkstemp(prefix=f".{safe_record.name}.", suffix=".tmp", dir=str(safe_record.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, safe_record)
    except OSError as exc:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        _add(findings, "ERROR", "RUN_UPDATE_FAILED", f"Could not update workflow run record: {exc}; backup preserved at {backup_path}")
        return _result(safe_record, findings, backup_path=str(backup_path))
    return _result(safe_record, findings, run_id=record["run_id"], current_state=target, status=record["status"], backup_path=str(backup_path), history_events=len(record["history"]))
