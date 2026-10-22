from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .adapters import ADAPTERS

VALID_EXECUTION_MODES = {"ide_extension", "cli", "desktop_app", "other"}
VALID_RUN_STATUSES = {"PASS", "FAIL", "BLOCKED", "CANCELLED", "UNKNOWN", "IN_PROGRESS"}
VALID_STEP_STATUSES = {"COMPLETED", "SKIPPED", "FAILED", "BLOCKED", "NOT_RUN"}
VALID_CHECK_STATUSES = {"PASS", "FAIL", "BLOCKED", "UNKNOWN"}


def _load_record(path: Path) -> Any:
    if not path.is_file():
        raise ValueError(f"Skill execution record does not exist or is not a file: {path}")
    try:
        raw = path.read_text(encoding="utf-8-sig")
        return json.loads(raw) if path.suffix.lower() == ".json" else yaml.safe_load(raw)
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"Cannot parse Skill execution record {path}: {exc}") from exc


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _time_is_valid(value: Any) -> bool:
    if not _nonempty(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return parsed.tzinfo is not None
    except ValueError:
        return False


def _add(findings: list[dict], level: str, code: str, message: str) -> None:
    findings.append({"level": level, "code": code, "message": message})


def validate_skill_execution(path: Path) -> dict:
    data = _load_record(path)
    findings: list[dict] = []
    if not isinstance(data, dict):
        _add(findings, "ERROR", "ROOT_TYPE", "Skill execution record must be an object")
        return _result(path, findings)
    allowed = {
        "schema_version", "run_id", "skill_id", "skill_version", "registry_version",
        "task_id", "project", "baseline_commit", "tool_id", "tool_version",
        "execution_mode", "model_id", "aimes_cli_version", "governance_version",
        "started_at", "finished_at", "status", "steps", "acceptance_checks",
        "outputs", "evidence_refs", "unresolved_items", "usage", "approval_refs",
    }
    for key in sorted(set(data) - allowed):
        _add(findings, "WARNING", "UNKNOWN_FIELD", f"Unrecognized execution record field: {key}")
    if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
        _add(findings, "ERROR", "SCHEMA_VERSION", "schema_version must be integer 1")
    required = (
        "run_id", "skill_id", "skill_version", "registry_version", "task_id",
        "baseline_commit", "tool_id", "tool_version", "execution_mode",
        "aimes_cli_version", "governance_version", "started_at", "status",
        "steps", "acceptance_checks", "outputs", "evidence_refs",
    )
    for key in required:
        if key not in data:
            _add(findings, "ERROR", "REQUIRED_FIELD", f"Missing required field: {key}")
    for key in (
        "run_id", "skill_id", "skill_version", "registry_version", "task_id",
        "baseline_commit", "tool_version", "aimes_cli_version", "governance_version",
    ):
        if key in data and not _nonempty(data[key]):
            _add(findings, "ERROR", "FIELD_VALUE", f"{key} must be a non-empty string")
    if not isinstance(data.get("tool_id"), str) or data.get("tool_id") not in ADAPTERS:
        _add(findings, "ERROR", "TOOL_ID", f"tool_id must be one of {sorted(ADAPTERS)}")
    if not isinstance(data.get("execution_mode"), str) or data.get("execution_mode") not in VALID_EXECUTION_MODES:
        _add(findings, "ERROR", "EXECUTION_MODE", f"execution_mode must be one of {sorted(VALID_EXECUTION_MODES)}")
    if not isinstance(data.get("status"), str) or data.get("status") not in VALID_RUN_STATUSES:
        _add(findings, "ERROR", "RUN_STATUS", f"status must be one of {sorted(VALID_RUN_STATUSES)}")
    if not _time_is_valid(data.get("started_at")):
        _add(findings, "ERROR", "STARTED_AT", "started_at must be an ISO-8601 timestamp with timezone")
    if data.get("finished_at") is not None and not _time_is_valid(data.get("finished_at")):
        _add(findings, "ERROR", "FINISHED_AT", "finished_at must be an ISO-8601 timestamp with timezone")
    if data.get("status") in {"PASS", "FAIL", "BLOCKED", "CANCELLED"} and not _time_is_valid(data.get("finished_at")):
        _add(findings, "ERROR", "FINISHED_AT_REQUIRED", "A terminal status requires finished_at")
    if data.get("model_id") is not None and not _nonempty(data.get("model_id")):
        _add(findings, "ERROR", "MODEL_ID", "model_id must be omitted or a non-empty string")

    steps = data.get("steps")
    if not isinstance(steps, list):
        _add(findings, "ERROR", "STEPS_TYPE", "steps must be a list")
        steps = []
    step_ids: set[str] = set()
    step_statuses: list[str] = []
    for i, step in enumerate(steps):
        loc = f"steps[{i}]"
        if not isinstance(step, dict):
            _add(findings, "ERROR", "STEP_TYPE", f"{loc} must be an object")
            continue
        sid = step.get("step_id")
        if not _nonempty(sid):
            _add(findings, "ERROR", "STEP_ID", f"{loc}.step_id is required")
        elif sid in step_ids:
            _add(findings, "ERROR", "DUPLICATE_STEP_ID", f"Duplicate step_id: {sid}")
        else:
            step_ids.add(sid)
        if not _nonempty(step.get("name")):
            _add(findings, "ERROR", "STEP_NAME", f"{loc}.name is required")
        status = step.get("status")
        if not isinstance(status, str) or status not in VALID_STEP_STATUSES:
            _add(findings, "ERROR", "STEP_STATUS", f"{loc}.status must be one of {sorted(VALID_STEP_STATUSES)}")
        else:
            step_statuses.append(status)
        if status == "SKIPPED" and not _nonempty(step.get("skip_reason")):
            _add(findings, "ERROR", "SKIP_REASON_REQUIRED", f"{loc}: SKIPPED steps require skip_reason")
        if "evidence_refs" in step and not isinstance(step.get("evidence_refs"), list):
            _add(findings, "ERROR", "STEP_EVIDENCE_TYPE", f"{loc}.evidence_refs must be a list")

    checks = data.get("acceptance_checks")
    if not isinstance(checks, list):
        _add(findings, "ERROR", "ACCEPTANCE_CHECKS_TYPE", "acceptance_checks must be a list")
        checks = []
    check_ids: set[str] = set()
    check_statuses: list[str] = []
    for i, check in enumerate(checks):
        loc = f"acceptance_checks[{i}]"
        if not isinstance(check, dict):
            _add(findings, "ERROR", "ACCEPTANCE_CHECK_TYPE", f"{loc} must be an object")
            continue
        cid = check.get("check_id")
        if not _nonempty(cid):
            _add(findings, "ERROR", "ACCEPTANCE_CHECK_ID", f"{loc}.check_id is required")
        elif cid in check_ids:
            _add(findings, "ERROR", "DUPLICATE_ACCEPTANCE_CHECK_ID", f"Duplicate check_id: {cid}")
        else:
            check_ids.add(cid)
        if not _nonempty(check.get("criterion")):
            _add(findings, "ERROR", "ACCEPTANCE_CRITERION", f"{loc}.criterion is required")
        status = check.get("status")
        if not isinstance(status, str) or status not in VALID_CHECK_STATUSES:
            _add(findings, "ERROR", "ACCEPTANCE_STATUS", f"{loc}.status must be one of {sorted(VALID_CHECK_STATUSES)}")
        else:
            check_statuses.append(status)
        if "evidence_refs" in check and not isinstance(check.get("evidence_refs"), list):
            _add(findings, "ERROR", "CHECK_EVIDENCE_TYPE", f"{loc}.evidence_refs must be a list")

    for key in ("outputs", "evidence_refs", "unresolved_items", "approval_refs"):
        if key in data and not isinstance(data.get(key), list):
            _add(findings, "ERROR", "FIELD_TYPE", f"{key} must be a list")
    for key in ("outputs", "evidence_refs"):
        if isinstance(data.get(key), list):
            for i, value in enumerate(data[key]):
                if not _nonempty(value):
                    _add(findings, "ERROR", "REFERENCE_VALUE", f"{key}[{i}] must be a non-empty string")

    if data.get("status") == "PASS":
        if not steps:
            _add(findings, "ERROR", "PASS_WITHOUT_STEPS", "PASS requires at least one recorded step")
        if not checks:
            _add(findings, "ERROR", "PASS_WITHOUT_ACCEPTANCE_CHECKS", "PASS requires at least one acceptance check")
        if not data.get("outputs"):
            _add(findings, "ERROR", "PASS_WITHOUT_OUTPUTS", "PASS requires at least one output reference")
        if not data.get("evidence_refs"):
            _add(findings, "ERROR", "PASS_WITHOUT_EVIDENCE", "PASS requires at least one evidence reference")
        if any(status in {"FAILED", "BLOCKED", "NOT_RUN"} for status in step_statuses):
            _add(findings, "ERROR", "PASS_WITH_INCOMPLETE_STEP", "PASS cannot include FAILED, BLOCKED or NOT_RUN steps")
        if any(status != "PASS" for status in check_statuses):
            _add(findings, "ERROR", "PASS_WITH_FAILED_ACCEPTANCE", "PASS requires every acceptance check to be PASS")
    usage = data.get("usage")
    if usage is not None:
        if not isinstance(usage, dict):
            _add(findings, "ERROR", "USAGE_TYPE", "usage must be an object")
        else:
            source = usage.get("source")
            if source not in {"tool_report", "provider_report", "unavailable"}:
                _add(findings, "ERROR", "USAGE_SOURCE", "usage.source must be tool_report, provider_report or unavailable")
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                value = usage.get(key)
                if value is not None and (type(value) is not int or value < 0):
                    _add(findings, "ERROR", "USAGE_TOKEN_VALUE", f"usage.{key} must be a non-negative integer or null")
                if source == "unavailable" and value is not None:
                    _add(findings, "ERROR", "USAGE_MUST_NOT_ESTIMATE", "Unavailable usage must use null token values; do not estimate")
    return _result(path, findings, run_id=data.get("run_id"), status=data.get("status"), checked_steps=len(steps), checked_acceptance_checks=len(checks))


def _result(path: Path, findings: list[dict], **extra) -> dict:
    errors = sum(item["level"] == "ERROR" for item in findings)
    warnings = sum(item["level"] == "WARNING" for item in findings)
    return {
        "schema_version": 1,
        "validator": "aimes-skill-execution-validator",
        "source": str(path),
        "ok": errors == 0,
        "summary": {"errors": errors, "warnings": warnings, "findings": len(findings)},
        "findings": findings,
        **extra,
        "note": "结构校验不证明 Skill 真实执行或业务结果正确；PASS 必须由引用的外部证据支持。未获取真实 usage 时应记录 unavailable 和 null，不得估算。",
    }
