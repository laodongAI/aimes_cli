from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .validators import _finding, _result

CORE_SECTION = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
KEY_VALUE = re.compile(r"^\s*-?\s*([A-Za-z_][\w-]*)\s*:\s*(.*)$")

REQUIRED_SECTIONS_R0 = ["DELIVERY", "FILES", "VERIFICATION", "UNRESOLVED / RISKS", "GIT_STATUS", "NEXT"]
ALL_SECTIONS = REQUIRED_SECTIONS_R0 + ["TRACEABILITY_UPDATED", "TEMP_CLEANUP"]
RESULT_STATUSES = {"VERIFIED", "IMPLEMENTED_UNVERIFIED", "FAILED", "BLOCKED", "UNKNOWN"}
CHECK_STATUSES = {"PASS", "FAIL", "NOT_RUN", "BLOCKED", "PARTIAL"}
REPORT_LEVELS = {"R0", "R1", "R2"}
LEVEL_ORDER = {"R0": 0, "R1": 1, "R2": 2}
EMPTY_VALUES = {"", "n/a", "na", "null", "none", "-"}


def split_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(CORE_SECTION.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1).strip().upper()] = text[match.end():end].strip()
    return sections


def parse_delivery_fields(section_text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in section_text.splitlines():
        match = KEY_VALUE.match(line)
        if match:
            fields.setdefault(match.group(1).strip().lower(), match.group(2).strip())
    return fields


def parse_verification_entries(section_text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in section_text.splitlines():
        match = KEY_VALUE.match(line)
        if not match:
            continue
        key, value = match.group(1).strip().lower(), match.group(2).strip()
        if key == "check":
            if current:
                entries.append(current)
            current = {"check": value}
        elif current is not None:
            current[key] = value
        else:
            current = {key: value}
    if current:
        entries.append(current)
    return entries


def _has_value(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() not in EMPTY_VALUES


def validate_delivery_text(text: str, source: Path | str, root: Path | None = None) -> dict[str, Any]:
    """Validate an AIMES Core 8.3 fixed-heading delivery report (read-only)."""
    source_label = str(source)
    findings: list[dict[str, Any]] = []
    sections = split_sections(text)
    delivery = parse_delivery_fields(sections.get("DELIVERY", ""))
    verifications = parse_verification_entries(sections.get("VERIFICATION", ""))

    task_id = delivery.get("task_id", "")
    if not _has_value(task_id):
        _finding(findings, "ERROR", "TASK_ID_MISSING", "DELIVERY section must record a non-empty task_id.", source_label)
    result = delivery.get("result", "")
    risk_level = (delivery.get("risk_level") or "").strip().upper()
    report_level = (delivery.get("report_level") or "").strip().upper()
    if not _has_value(result):
        _finding(findings, "ERROR", "RESULT_MISSING", "DELIVERY.result must be one of " + ", ".join(sorted(RESULT_STATUSES)) + ".", source_label)
    elif result.strip().upper() not in RESULT_STATUSES:
        _finding(findings, "ERROR", "RESULT_INVALID", f"DELIVERY.result is not a valid AIMES status: {result!r}.", source_label)
    result = result.strip().upper()
    for field_name, value in (("risk_level", risk_level), ("report_level", report_level)):
        if value and value not in REPORT_LEVELS:
            _finding(findings, "ERROR", "REPORT_LEVEL_INVALID", f"DELIVERY.{field_name} must be R0, R1 or R2: {value!r}.", source_label)
    if risk_level in REPORT_LEVELS and report_level in REPORT_LEVELS and LEVEL_ORDER[report_level] < LEVEL_ORDER[risk_level]:
        _finding(findings, "ERROR", "REPORT_LEVEL_BELOW_RISK",
                 f"report_level={report_level} is below task risk_level={risk_level}; risk cannot be downgraded by the report.", source_label)
    elif not report_level:
        _finding(findings, "ERROR", "REPORT_LEVEL_MISSING", "DELIVERY.report_level is required (R0/R1/R2).", source_label)

    required = REQUIRED_SECTIONS_R0
    if report_level in {"R1", "R2"} or risk_level == "R2":
        required = ALL_SECTIONS
    for section in required:
        if section not in sections or not sections[section]:
            _finding(findings, "ERROR", "SECTION_MISSING", f"Required delivery section missing or empty: ## {section}", source_label)

    for entry in verifications:
        status = (entry.get("status") or "").strip().upper()
        check = entry.get("check") or entry.get("name") or "<unnamed>"
        if status not in CHECK_STATUSES:
            _finding(findings, "ERROR", "CHECK_STATUS_INVALID",
                     f"VERIFICATION entry {check!r} status must be one of {', '.join(sorted(CHECK_STATUSES))}: {status!r}.", source_label)
        if status == "PASS":
            if not _has_value(entry.get("command_or_test_id")):
                _finding(findings, "ERROR", "PASS_WITHOUT_COMMAND", f"PASS check {check!r} must record the real command or test ID.", source_label)
            if not _has_value(entry.get("exit_code_or_result")):
                _finding(findings, "ERROR", "PASS_WITHOUT_RESULT", f"PASS check {check!r} must record the exit code or observed result.", source_label)
            if not _has_value(entry.get("evidence_path")):
                _finding(findings, "ERROR", "PASS_WITHOUT_EVIDENCE", f"PASS check {check!r} must record an evidence location.", source_label)
            evidence = (entry.get("evidence_path") or "").strip()
            if root is not None and evidence and "/" in evidence.replace("\\", "/"):
                candidate = (root / evidence.replace("\\", "/")).resolve()
                if candidate.is_file() is False and str(candidate).lower() not in {"", "null"}:
                    _finding(findings, "WARNING", "EVIDENCE_PATH_NOT_FOUND", f"Evidence path recorded by check {check!r} was not found: {evidence}.", source_label)

    if result == "VERIFIED":
        if not verifications:
            _finding(findings, "ERROR", "VERIFIED_WITHOUT_EVIDENCE", "result=VERIFIED requires at least one VERIFICATION entry.", source_label)
        elif not any((entry.get("status") or "").strip().upper() == "PASS" for entry in verifications):
            _finding(findings, "ERROR", "VERIFIED_WITHOUT_PASS",
                     "result=VERIFIED requires at least one PASS check with command, result and evidence; NOT_RUN/BLOCKED cannot be upgraded to PASS.", source_label)
    if verifications and not any(_has_value(entry.get("status")) for entry in verifications):
        _finding(findings, "WARNING", "CHECK_STATUS_MISSING", "Every VERIFICATION entry should record an explicit status (PASS/FAIL/NOT_RUN/BLOCKED/PARTIAL).", source_label)

    extra = {"report": {"task_id": task_id, "risk_level": risk_level, "report_level": report_level,
                         "result": result, "sections": sorted(sections), "verifications": verifications}}
    return _result("delivery-report", Path(str(source)), findings, extra)


def validate_delivery_report(path: Path, root: Path | None = None) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Input file does not exist or is not a file: {path}")
    return validate_delivery_text(path.read_text(encoding="utf-8-sig"), path, root)
