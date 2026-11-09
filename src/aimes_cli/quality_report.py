from __future__ import annotations

from pathlib import Path
from typing import Any

from .quality_check import inspect_project_quality
from .quality_review import validate_ai_review_report


def build_quality_report(root: Path, ai_report_path: Path | None = None) -> dict[str, Any]:
    """Combine deterministic and validated AI findings without changing gate semantics."""
    root = root.resolve()
    static_result = inspect_project_quality(root)
    ai_result = None
    if ai_report_path is not None:
        candidate = ai_report_path if ai_report_path.is_absolute() else root / ai_report_path
        ai_result = validate_ai_review_report(candidate, root)
        if not ai_result.get("ok"):
            return {
                "ok": False,
                "status": "INVALID_AI_REPORT",
                "root": str(root),
                "static": static_result,
                "ai_review": ai_result,
                "findings": [],
                "summary": {"static_findings": len(static_result.get("findings", [])), "ai_findings": 0, "total_findings": 0},
                "note": "AI report validation failed. No combined report was produced; deterministic findings are retained separately.",
            }

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(static_result.get("findings", []), start=1):
        normalized.append({
            "finding_id": item.get("code", f"STATIC_{index}") + ":" + str(item.get("path", "")) + ":" + str(item.get("line", 0)),
            "origin": "static",
            "category": item.get("code", "static-quality"),
            "severity": item.get("severity", "INFO"),
            "message": item.get("message", ""),
            "recommendation": item.get("recommendation"),
            "evidence": {
                "path": item.get("path"),
                "line_start": item.get("line"),
                "line_end": item.get("line"),
                "excerpt": item.get("evidence"),
            } if item.get("path") else None,
            "confidence": None,
            "blocking": bool(static_result.get("policy", {}).get("enforce") and (
                item.get("severity") == "ERROR"
                or (static_result.get("policy", {}).get("fail_on") == "WARNING" and item.get("severity") == "WARNING")
            )),
        })
    ai_findings = []
    if ai_result:
        for item in ai_result.get("findings", []):
            ai_findings.append({
                "finding_id": item["id"],
                "origin": "ai",
                "category": item["category"],
                "severity": item["severity"],
                "message": item["message"],
                "recommendation": item["recommendation"],
                "evidence": {
                    "path": item["path"],
                    "line_start": item["line"],
                    "line_end": item["line_end"],
                    "excerpt": item["evidence"],
                },
                "confidence": item["confidence"],
                "blocking": False,
            })
    combined = normalized + ai_findings
    return {
        "ok": static_result.get("ok", False),
        "status": "PASS" if static_result.get("ok") else "STATIC_QUALITY_GATE_FAILED",
        "schema_version": 1,
        "root": str(root),
        "summary": {
            "static_findings": len(normalized),
            "ai_findings": len(ai_findings),
            "total_findings": len(combined),
            "blocking_findings": sum(item["blocking"] for item in combined),
            "warnings": sum(item["severity"] == "WARNING" for item in combined),
            "errors": sum(item["severity"] == "ERROR" for item in combined),
        },
        "findings": combined,
        "static_quality": {
            "status": static_result.get("status"),
            "ok": static_result.get("ok"),
            "policy": static_result.get("policy"),
            "summary": static_result.get("summary"),
        },
        "ai_review": {
            "status": ai_result.get("status") if ai_result else "NOT_PROVIDED",
            "ok": ai_result.get("ok") if ai_result else None,
            "gate_policy": ai_result.get("gate_policy") if ai_result else {
                "ai_findings_blocking": False,
                "note": "No AI report supplied; AI findings are never blocking.",
            },
        },
        "limitations": [
            "This is a unified presentation contract, not a new gate engine. Static gate outcome remains authoritative.",
            "AI findings remain advisory and cannot make a passing static gate fail.",
            "Static and AI checks have different evidence capabilities; missing evidence is represented as null rather than inferred.",
        ],
    }
