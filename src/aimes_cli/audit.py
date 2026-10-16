from __future__ import annotations
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SENSITIVE_KEY = re.compile(r"(api.?key|token|password|secret|cookie|authorization|credential|private.?key)", re.I)

def redact(value: Any, key: str = "") -> Any:
    """Recursively redact likely secret-bearing fields before audit serialization."""
    if SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        # Redact common inline credential assignments in free-form summaries.
        value = re.sub(r"(?i)(api[_-]?key|access[_-]?token|password|secret|authorization)\s*[:=]\s*(?:bearer\s+)?[^\s,;]+(?:\s+[^\s,;]+)?", r"\1=[REDACTED]", value)
    return value

def append_event(path: Path, *, run_id: str, event_type: str, status: str, actor: str = "aimes-cli", details: dict | None = None, parent_event_id: str | None = None) -> dict:
    if not run_id.strip() or not event_type.strip() or not status.strip():
        raise ValueError("run_id, event_type and status are required")
    event = {
        "schema_version": 1,
        "run_id": run_id,
        "event_id": f"evt-{uuid.uuid4().hex[:16]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "status": status,
        "actor": actor,
        "details": redact(details or {}),
    }
    if parent_event_id:
        event["parent_event_id"] = parent_event_id
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event

def validate_audit(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"Audit log does not exist or is not a file: {path}")
    findings = []
    count = 0
    seen = set()
    required = ("schema_version", "run_id", "event_id", "timestamp", "event_type", "status", "actor", "details")
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        count += 1
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            findings.append({"level": "ERROR", "code": "AUDIT_JSONL_INVALID", "message": f"第 {line_no} 行不是有效 JSON：{exc.msg}"})
            continue
        if not isinstance(event, dict):
            findings.append({"level": "ERROR", "code": "AUDIT_EVENT_TYPE", "message": f"第 {line_no} 行必须是 JSON 对象"})
            continue
        for key in required:
            if key not in event:
                findings.append({"level": "ERROR", "code": "AUDIT_FIELD_REQUIRED", "message": f"第 {line_no} 行缺少字段 {key}"})
        eid = event.get("event_id")
        if isinstance(eid, str):
            if eid in seen:
                findings.append({"level": "ERROR", "code": "AUDIT_EVENT_ID_DUPLICATE", "message": f"第 {line_no} 行 event_id 重复：{eid}"})
            seen.add(eid)
        if event.get("schema_version") != 1:
            findings.append({"level": "ERROR", "code": "AUDIT_SCHEMA_VERSION", "message": f"第 {line_no} 行 schema_version 必须为 1"})
    errors = sum(x["level"] == "ERROR" for x in findings)
    return {"schema_version": 1, "validator": "aimes-audit-jsonl", "source": str(path), "ok": errors == 0,
            "summary": {"events": count, "errors": errors}, "findings": findings,
            "note": "结构校验不证明日志防篡改，也不证明记录内容真实。"}
