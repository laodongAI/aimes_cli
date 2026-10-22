from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

VALID_TERMINAL_OUTCOMES = {"SUCCESS", "FAILURE", "BLOCKED", "CANCELLED"}
VALID_RETRY_MODES = {"idempotent", "guarded", "never"}
VALID_TRANSITION_EVENTS = {"success", "failure", "blocked", "cancelled", "retry", "approval_granted", "approval_denied"}


def _load(path: Path) -> Any:
    if not path.is_file():
        raise ValueError(f"Workflow definition does not exist or is not a file: {path}")
    try:
        raw = path.read_text(encoding="utf-8-sig")
        return json.loads(raw) if path.suffix.lower() == ".json" else yaml.safe_load(raw)
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"Cannot parse workflow definition {path}: {exc}") from exc


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _add(findings: list[dict], level: str, code: str, message: str) -> None:
    findings.append({"level": level, "code": code, "message": message})


def validate_workflow_definition(path: Path) -> dict:
    data = _load(path)
    findings: list[dict] = []
    if not isinstance(data, dict):
        _add(findings, "ERROR", "ROOT_TYPE", "Workflow definition must be an object")
        return _result(path, findings)
    allowed_root = {"schema_version", "workflow_id", "version", "name", "purpose", "entry_state", "states", "transitions"}
    for key in sorted(set(data) - allowed_root):
        _add(findings, "WARNING", "UNKNOWN_FIELD", f"Unrecognized workflow field: {key}")
    if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
        _add(findings, "ERROR", "SCHEMA_VERSION", "schema_version must be integer 1")
    for key in ("workflow_id", "version", "name", "purpose", "entry_state"):
        if not _nonempty(data.get(key)):
            _add(findings, "ERROR", "REQUIRED_FIELD", f"{key} must be a non-empty string")

    states = data.get("states")
    if not isinstance(states, list) or not states:
        _add(findings, "ERROR", "STATES_REQUIRED", "states must be a non-empty list")
        states = []
    state_by_id: dict[str, dict] = {}
    allowed_state = {
        "state_id", "name", "entry_conditions", "required_artifacts", "completion_criteria",
        "failure_recovery", "side_effects", "approval_required", "retry_mode", "max_attempts",
        "retry_guard", "terminal_outcome",
    }
    for i, state in enumerate(states):
        loc = f"states[{i}]"
        if not isinstance(state, dict):
            _add(findings, "ERROR", "STATE_TYPE", f"{loc} must be an object")
            continue
        for key in sorted(set(state) - allowed_state):
            _add(findings, "WARNING", "UNKNOWN_STATE_FIELD", f"{loc}: unrecognized field '{key}'")
        sid = state.get("state_id")
        if not _nonempty(sid):
            _add(findings, "ERROR", "STATE_ID", f"{loc}.state_id is required")
            continue
        if sid in state_by_id:
            _add(findings, "ERROR", "DUPLICATE_STATE_ID", f"Duplicate state_id: {sid}")
            continue
        state_by_id[sid] = state
        if not _nonempty(state.get("name")):
            _add(findings, "ERROR", "STATE_NAME", f"{loc}.name is required")
        for key in ("entry_conditions", "completion_criteria", "failure_recovery", "side_effects"):
            value = state.get(key)
            if not isinstance(value, list) or not value or any(not _nonempty(x) for x in value):
                _add(findings, "ERROR", "STATE_CONTRACT_LIST", f"{loc}.{key} must be a non-empty list of strings")
        if not isinstance(state.get("required_artifacts"), list):
            _add(findings, "ERROR", "REQUIRED_ARTIFACTS_TYPE", f"{loc}.required_artifacts must be a list")
        elif any(not _nonempty(value) for value in state["required_artifacts"]):
            _add(findings, "ERROR", "REQUIRED_ARTIFACT_VALUE", f"{loc}.required_artifacts entries must be non-empty strings")
        if type(state.get("approval_required")) is not bool:
            _add(findings, "ERROR", "APPROVAL_REQUIRED_TYPE", f"{loc}.approval_required must be a boolean")
        retry_mode = state.get("retry_mode")
        if not isinstance(retry_mode, str) or retry_mode not in VALID_RETRY_MODES:
            _add(findings, "ERROR", "RETRY_MODE", f"{loc}.retry_mode must be one of {sorted(VALID_RETRY_MODES)}")
        attempts = state.get("max_attempts")
        if type(attempts) is not int or attempts < 1:
            _add(findings, "ERROR", "MAX_ATTEMPTS", f"{loc}.max_attempts must be an integer >= 1")
            attempts = 1
        if retry_mode == "never" and attempts > 1:
            _add(findings, "ERROR", "RETRY_POLICY_CONTRADICTION", f"{loc}: retry_mode=never requires max_attempts=1")
        if retry_mode == "guarded" and attempts > 1 and not _nonempty(state.get("retry_guard")):
            _add(findings, "ERROR", "RETRY_GUARD_REQUIRED", f"{loc}: guarded retries require retry_guard")
        outcome = state.get("terminal_outcome")
        if outcome is not None and (not isinstance(outcome, str) or outcome not in VALID_TERMINAL_OUTCOMES):
            _add(findings, "ERROR", "TERMINAL_OUTCOME", f"{loc}.terminal_outcome must be null or one of {sorted(VALID_TERMINAL_OUTCOMES)}")
        if outcome is not None and (retry_mode != "never" or attempts != 1):
            _add(findings, "ERROR", "TERMINAL_RETRY_FORBIDDEN", f"{loc}: terminal states must use retry_mode=never and max_attempts=1")

    entry = data.get("entry_state")
    if isinstance(entry, str) and entry not in state_by_id:
        _add(findings, "ERROR", "ENTRY_STATE_UNKNOWN", f"entry_state does not exist: {entry}")
    terminal_success = [sid for sid, state in state_by_id.items() if state.get("terminal_outcome") == "SUCCESS"]
    if not terminal_success:
        _add(findings, "ERROR", "SUCCESS_TERMINAL_REQUIRED", "At least one terminal state with terminal_outcome=SUCCESS is required")

    transitions = data.get("transitions")
    if not isinstance(transitions, list):
        _add(findings, "ERROR", "TRANSITIONS_TYPE", "transitions must be a list")
        transitions = []
    allowed_transition = {"from", "to", "on", "guard"}
    seen_transitions: set[tuple[str, str, str]] = set()
    outgoing: dict[str, list[dict]] = {sid: [] for sid in state_by_id}
    adjacency: dict[str, set[str]] = {sid: set() for sid in state_by_id}
    for i, transition in enumerate(transitions):
        loc = f"transitions[{i}]"
        if not isinstance(transition, dict):
            _add(findings, "ERROR", "TRANSITION_TYPE", f"{loc} must be an object")
            continue
        for key in sorted(set(transition) - allowed_transition):
            _add(findings, "WARNING", "UNKNOWN_TRANSITION_FIELD", f"{loc}: unrecognized field '{key}'")
        source, target, event = transition.get("from"), transition.get("to"), transition.get("on")
        if not isinstance(source, str) or source not in state_by_id:
            _add(findings, "ERROR", "TRANSITION_SOURCE", f"{loc}.from references an unknown state")
            continue
        if not isinstance(target, str) or target not in state_by_id:
            _add(findings, "ERROR", "TRANSITION_TARGET", f"{loc}.to references an unknown state")
            continue
        if not isinstance(event, str) or event not in VALID_TRANSITION_EVENTS:
            _add(findings, "ERROR", "TRANSITION_EVENT", f"{loc}.on must be one of {sorted(VALID_TRANSITION_EVENTS)}")
            continue
        signature = (source, target, event)
        if signature in seen_transitions:
            _add(findings, "ERROR", "DUPLICATE_TRANSITION", f"Duplicate transition: {source} -> {target} on {event}")
        seen_transitions.add(signature)
        if state_by_id[source].get("terminal_outcome") is not None:
            _add(findings, "ERROR", "TERMINAL_HAS_OUTGOING", f"Terminal state {source} cannot have outgoing transitions")
        if source == target and event != "retry":
            _add(findings, "ERROR", "SELF_TRANSITION_NOT_RETRY", f"{loc}: self transitions must be explicit retry transitions")
        if event == "retry":
            source_state = state_by_id[source]
            if source != target:
                _add(findings, "ERROR", "RETRY_TARGET", f"{loc}: retry transition must return to the same state")
            source_attempts = source_state.get("max_attempts", 1)
            if source_state.get("retry_mode") == "never" or type(source_attempts) is not int or source_attempts <= 1:
                _add(findings, "ERROR", "RETRY_NOT_ALLOWED", f"{loc}: state retry policy does not allow retries")
        outgoing[source].append(transition)
        if event != "retry":
            adjacency[source].add(target)

    for sid, state in state_by_id.items():
        if state.get("terminal_outcome") is not None:
            continue
        events = {t.get("on") for t in outgoing[sid]}
        if "success" not in events:
            _add(findings, "ERROR", "SUCCESS_TRANSITION_REQUIRED", f"Non-terminal state {sid} needs an on=success transition")
        if not events.intersection({"failure", "blocked", "cancelled"}):
            _add(findings, "ERROR", "FAILURE_TRANSITION_REQUIRED", f"Non-terminal state {sid} needs a failure/blocked/cancelled transition")

    if isinstance(entry, str) and entry in state_by_id:
        reachable: set[str] = set()
        stack = [entry]
        while stack:
            current = stack.pop()
            if current in reachable:
                continue
            reachable.add(current)
            stack.extend(adjacency.get(current, set()) - reachable)
        for sid in sorted(set(state_by_id) - reachable):
            _add(findings, "ERROR", "UNREACHABLE_STATE", f"State is unreachable from entry_state: {sid}")
        indegree = {sid: 0 for sid in state_by_id}
        for source, targets in adjacency.items():
            for target in targets:
                indegree[target] += 1
        queue = [sid for sid, degree in indegree.items() if degree == 0]
        visited = 0
        while queue:
            current = queue.pop()
            visited += 1
            for target in adjacency[current]:
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
        if visited != len(state_by_id):
            _add(findings, "ERROR", "WORKFLOW_CYCLE", "Workflow has a non-retry cycle; V1 requires acyclic transitions outside explicit retry self-loops")
    return _result(path, findings, workflow_id=data.get("workflow_id"), checked_states=len(state_by_id), checked_transitions=len(transitions))


def _result(path: Path, findings: list[dict], **extra) -> dict:
    errors = sum(item["level"] == "ERROR" for item in findings)
    warnings = sum(item["level"] == "WARNING" for item in findings)
    return {
        "schema_version": 1,
        "validator": "aimes-workflow-validator",
        "source": str(path),
        "ok": errors == 0,
        "summary": {"errors": errors, "warnings": warnings, "findings": len(findings)},
        "findings": findings,
        **extra,
        "note": "定义校验不执行工作流，不持久化运行状态，也不证明外部步骤已完成。",
    }
