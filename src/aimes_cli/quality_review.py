from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SEVERITIES = {"INFO", "WARNING"}


def validate_ai_review_report(report_path: Path, root: Path) -> dict[str, Any]:
    """Validate an externally produced AI review report; never executes a model or blocks a gate."""
    root = root.resolve()
    report_path = report_path.resolve()
    try:
        report_path.relative_to(root)
    except ValueError:
        return {"ok": False, "status": "INVALID_REPORT", "errors": ["Report file must be inside the project root."]}
    try:
        raw = json.loads(report_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"ok": False, "status": "INVALID_REPORT", "errors": [f"Cannot read JSON report: {exc}"]}
    errors: list[str] = []
    if not isinstance(raw, dict) or raw.get("schema_version") != 1 or not isinstance(raw.get("findings"), list):
        return {"ok": False, "status": "INVALID_REPORT", "errors": ["Report must be an object with schema_version=1 and a findings array."]}
    findings = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw["findings"]):
        prefix = f"findings[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object.")
            continue
        required = ("id", "category", "severity", "message", "recommendation", "confidence", "evidence")
        missing = [key for key in required if key not in item]
        if missing:
            errors.append(f"{prefix} missing fields: {', '.join(missing)}.")
            continue
        finding_id = item["id"]
        if not isinstance(finding_id, str) or not finding_id.strip() or finding_id in seen_ids:
            errors.append(f"{prefix}.id must be a unique non-empty string.")
            continue
        seen_ids.add(finding_id)
        if item["severity"] not in SEVERITIES:
            errors.append(f"{prefix}.severity must be INFO or WARNING; AI findings cannot declare blocking ERROR.")
            continue
        if not isinstance(item["category"], str) or not item["category"].strip():
            errors.append(f"{prefix}.category must be a non-empty string.")
            continue
        if not isinstance(item["message"], str) or not item["message"].strip() or not isinstance(item["recommendation"], str) or not item["recommendation"].strip():
            errors.append(f"{prefix}.message and recommendation must be non-empty strings.")
            continue
        confidence = item["confidence"]
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            errors.append(f"{prefix}.confidence must be a number from 0 to 1.")
            continue
        evidence = item["evidence"]
        if not isinstance(evidence, dict) or not isinstance(evidence.get("path"), str) or not isinstance(evidence.get("line_start"), int) or not isinstance(evidence.get("line_end"), int) or not isinstance(evidence.get("excerpt"), str) or not evidence["excerpt"].strip():
            errors.append(f"{prefix}.evidence requires path, integer line_start/line_end, and non-empty excerpt.")
            continue
        if evidence["line_start"] < 1 or evidence["line_end"] < evidence["line_start"]:
            errors.append(f"{prefix}.evidence line range is invalid.")
            continue
        source = (root / evidence["path"]).resolve()
        try:
            source.relative_to(root)
        except ValueError:
            errors.append(f"{prefix}.evidence path escapes project root.")
            continue
        if not source.is_file():
            errors.append(f"{prefix}.evidence source file does not exist: {evidence['path']}.")
            continue
        try:
            source_lines = source.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError):
            errors.append(f"{prefix}.evidence source file cannot be read.")
            continue
        if evidence["line_end"] > len(source_lines):
            errors.append(f"{prefix}.evidence line range exceeds source file length.")
            continue
        excerpt = "\n".join(source_lines[evidence["line_start"] - 1:evidence["line_end"]])
        if evidence["excerpt"].strip() not in excerpt:
            errors.append(f"{prefix}.evidence excerpt does not match the referenced source lines.")
            continue
        findings.append({
            "severity": item["severity"],
            "code": "AI_REVIEW_" + str(item["category"]).upper().replace("-", "_").replace(" ", "_"),
            "id": finding_id,
            "origin": "ai",
            "category": item["category"],
            "path": evidence["path"],
            "line": evidence["line_start"],
            "line_end": evidence["line_end"],
            "evidence": evidence["excerpt"],
            "confidence": float(confidence),
            "message": item["message"],
            "recommendation": item["recommendation"],
            "blocking": False,
        })
    if errors:
        return {"ok": False, "status": "INVALID_REPORT", "errors": errors, "findings": []}
    return {
        "ok": True,
        "status": "VALID_ADVISORY_REPORT",
        "schema_version": 1,
        "root": str(root),
        "summary": {"findings": len(findings), "warnings": sum(x["severity"] == "WARNING" for x in findings), "info": sum(x["severity"] == "INFO" for x in findings)},
        "findings": findings,
        "gate_policy": {"ai_findings_blocking": False, "note": "AI-origin findings are advisory only and cannot fail deterministic quality gates."},
        "limitations": ["This command validates an externally generated report; it does not call an AI model, prove the model's reasoning, or establish that the finding is correct."],
    }
