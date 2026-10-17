from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .cleanup_audit import audit_temp_registry
from .docs_check import check_docs
from .v03 import validate_trace


METRIC_INFO = {
    "requirement_traceability_rate": "Approved requirements with a valid link to a module or feature / all approved requirements.",
    "feature_implementation_mapping_rate": "Critical/high features linked to implementation or code entities / all critical/high features.",
    "feature_test_mapping_rate": "Critical/high features linked to test entities / all critical/high features.",
    "verification_evidence_completeness_rate": "VERIFIED entities backed by passing evidence references / all VERIFIED entities.",
    "trace_reference_validity_rate": "Trace links whose target entity exists / all trace links.",
    "document_link_validity_rate": "Existing local Markdown link targets / all checked local Markdown links.",
    "handoff_recoverability_rate": "Handoff trials resumed without old chat with valid evidence / all valid handoff trials.",
    "temporary_file_compliance_rate": "Registered in-policy temporary items / all registered and discovered temporary items.",
    "gate_bypass_count": "Count of explicit audit events whose event_type is gate.bypassed.",
}


def _finding(findings: list[dict[str, Any]], level: str, code: str, message: str, path: str | None = None) -> None:
    item: dict[str, Any] = {"level": level, "code": code, "message": message}
    if path:
        item["path"] = path
    findings.append(item)


def _safe_input(root: Path, path: Path | None, label: str, findings: list[dict[str, Any]]) -> Path | None:
    if path is None:
        return None
    resolved = (root / path).resolve() if not path.is_absolute() else path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        _finding(findings, "ERROR", "INPUT_PATH_ESCAPE", f"{label} must be inside the project root.", str(path))
        return None
    if not resolved.is_file():
        _finding(findings, "ERROR", "INPUT_NOT_FOUND", f"{label} does not exist: {path}", str(path))
        return None
    return resolved


def _metric(metric_id: str, value: float | int | None, numerator: int | None, denominator: int | None, source: str | None, note: str | None = None) -> dict[str, Any]:
    return {
        "id": metric_id,
        "definition": METRIC_INFO[metric_id],
        "value": value,
        "unit": "count" if metric_id == "gate_bypass_count" else "ratio",
        "status": "CALCULATED" if value is not None else "UNKNOWN",
        "numerator": numerator,
        "denominator": denominator,
        "source": source,
        "note": note,
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator > 0 else None


def build_metrics_report(
    root: Path,
    *,
    trace_manifest: Path | None = None,
    temp_registry: Path | None = None,
    handoff_trials: Path | None = None,
    audit_log: Path | None = None,
) -> dict[str, Any]:
    """Calculate only metrics supported by supplied, verifiable project sources."""
    root = root.resolve()
    findings: list[dict[str, Any]] = []
    metrics: dict[str, dict[str, Any]] = {}
    generated_at = datetime.now(timezone.utc).isoformat()

    git = {}
    for key, args in (
        ("branch", ("branch", "--show-current")),
        ("commit", ("rev-parse", "HEAD")),
    ):
        try:
            result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=5, check=False)
            git[key] = result.stdout.strip() if result.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            git[key] = None

    docs = check_docs(root)
    docs_total = int(docs.get("summary", {}).get("local_links_checked", 0))
    docs_errors = sum(item.get("code") in {"BROKEN_LINK", "LINK_PATH_ESCAPE"} for item in docs.get("findings", []))
    docs_valid = max(0, docs_total - docs_errors)
    docs_value = _ratio(docs_valid, docs_total)
    metrics["document_link_validity_rate"] = _metric(
        "document_link_validity_rate", docs_value, docs_valid if docs_value is not None else None,
        docs_total if docs_value is not None else None, "aimes docs check",
        None if docs_value is not None else "No local Markdown links were found; metric remains UNKNOWN rather than 100%.",
    )

    trace_path = _safe_input(root, trace_manifest, "trace_manifest", findings)
    trace_data: dict[str, Any] | None = None
    trace_valid = False
    if trace_path:
        try:
            loaded = yaml.safe_load(trace_path.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict) and isinstance(loaded.get("entities"), list):
                trace_data = loaded
                trace_valid = bool(validate_trace(trace_path, root).get("ok"))
            else:
                _finding(findings, "ERROR", "TRACE_SOURCE_SHAPE", "Trace manifest must contain an entities list.", str(trace_path))
        except (OSError, yaml.YAMLError) as exc:
            _finding(findings, "ERROR", "TRACE_SOURCE_READ", f"Cannot read trace manifest: {exc}", str(trace_path))
    if trace_data is not None and trace_valid:
        entities = [item for item in trace_data["entities"] if isinstance(item, dict) and isinstance(item.get("id"), str)]
        entity_by_id = {item["id"]: item for item in entities}
        total_links = 0
        valid_links = 0
        for entity in entities:
            links = entity.get("links", [])
            if not isinstance(links, list):
                continue
            for link in links:
                total_links += 1
                target = link.get("target") if isinstance(link, dict) else link
                if isinstance(target, str) and target in entity_by_id:
                    valid_links += 1
        metrics["trace_reference_validity_rate"] = _metric(
            "trace_reference_validity_rate", _ratio(valid_links, total_links),
            valid_links if total_links else None, total_links if total_links else None, str(trace_path),
            None if total_links else "No trace links were found; metric remains UNKNOWN.",
        )

        approved_requirements = [e for e in entities if e.get("type") == "requirement" and e.get("status") == "APPROVED"]
        linked_requirements = 0
        for entity in approved_requirements:
            links = entity.get("links", [])
            if isinstance(links, list) and any(
                isinstance((link.get("target") if isinstance(link, dict) else link), str)
                and entity_by_id.get(link.get("target") if isinstance(link, dict) else link, {}).get("type") in {"module", "feature"}
                for link in links
            ):
                linked_requirements += 1
        req_value = _ratio(linked_requirements, len(approved_requirements))
        metrics["requirement_traceability_rate"] = _metric(
            "requirement_traceability_rate", req_value,
            linked_requirements if req_value is not None else None,
            len(approved_requirements) if req_value is not None else None, str(trace_path),
            None if req_value is not None else "No approved requirement entities were found.",
        )

        critical_features = [
            e for e in entities if e.get("type") == "feature"
            and (e.get("critical") is True or str(e.get("criticality", "")).lower() in {"critical", "high"})
        ]
        implementation_mapped = 0
        test_mapped = 0
        for entity in critical_features:
            links = entity.get("links", [])
            targets = []
            if isinstance(links, list):
                for link in links:
                    target = link.get("target") if isinstance(link, dict) else link
                    if isinstance(target, str) and target in entity_by_id:
                        targets.append(entity_by_id[target].get("type"))
            if any(kind in {"implementation", "code"} for kind in targets):
                implementation_mapped += 1
            if "test" in targets:
                test_mapped += 1
        feature_denominator = len(critical_features)
        metrics["feature_implementation_mapping_rate"] = _metric(
            "feature_implementation_mapping_rate", _ratio(implementation_mapped, feature_denominator),
            implementation_mapped if feature_denominator else None, feature_denominator if feature_denominator else None, str(trace_path),
            None if feature_denominator else "No feature entities explicitly marked critical/high; metric remains UNKNOWN.",
        )
        metrics["feature_test_mapping_rate"] = _metric(
            "feature_test_mapping_rate", _ratio(test_mapped, feature_denominator),
            test_mapped if feature_denominator else None, feature_denominator if feature_denominator else None, str(trace_path),
            None if feature_denominator else "No feature entities explicitly marked critical/high; metric remains UNKNOWN.",
        )

        verified = [e for e in entities if e.get("status") == "VERIFIED"]
        evidence_by_id: dict[str, dict[str, Any]] = {}
        evidence_file = trace_data.get("evidence_file")
        if isinstance(evidence_file, str) and evidence_file.strip():
            evidence_path = (root / evidence_file).resolve()
            try:
                evidence_path.relative_to(root)
            except ValueError:
                evidence_path = None
            if evidence_path and evidence_path.is_file():
                try:
                    evidence_data = yaml.safe_load(evidence_path.read_text(encoding="utf-8-sig"))
                    if isinstance(evidence_data, dict) and isinstance(evidence_data.get("evidence"), list):
                        evidence_by_id = {e.get("id"): e for e in evidence_data["evidence"] if isinstance(e, dict) and isinstance(e.get("id"), str)}
                except (OSError, yaml.YAMLError):
                    evidence_by_id = {}
        verified_with_pass = 0
        for entity in verified:
            refs = entity.get("evidence_refs", [])
            if isinstance(refs, list) and refs and all(ref in evidence_by_id and evidence_by_id[ref].get("result") == "PASS" for ref in refs):
                verified_with_pass += 1
        evidence_value = _ratio(verified_with_pass, len(verified))
        metrics["verification_evidence_completeness_rate"] = _metric(
            "verification_evidence_completeness_rate", evidence_value,
            verified_with_pass if evidence_value is not None else None,
            len(verified) if evidence_value is not None else None, str(trace_path),
            None if evidence_value is not None else "No VERIFIED entities were found.",
        )
    else:
        if trace_manifest is not None:
            _finding(findings, "WARNING", "TRACE_METRICS_UNKNOWN", "Trace metrics are UNKNOWN because the trace source is missing, malformed or fails validation.", str(trace_manifest))
        for metric_id in ("trace_reference_validity_rate", "requirement_traceability_rate", "feature_implementation_mapping_rate", "feature_test_mapping_rate", "verification_evidence_completeness_rate"):
            metrics[metric_id] = _metric(metric_id, None, None, None, str(trace_manifest) if trace_manifest else None, "Provide a valid trace manifest with the relevant entity types and evidence.")

    handoff_path = _safe_input(root, handoff_trials, "handoff_trials", findings)
    if handoff_path:
        valid_trials = 0
        recovered = 0
        try:
            data = yaml.safe_load(handoff_path.read_text(encoding="utf-8-sig"))
        except (OSError, yaml.YAMLError) as exc:
            data = None
            _finding(findings, "ERROR", "HANDOFF_TRIALS_READ", f"Cannot read handoff trials: {exc}", str(handoff_path))
        trials = data.get("trials") if isinstance(data, dict) else None
        if not isinstance(trials, list):
            _finding(findings, "ERROR", "HANDOFF_TRIALS_SHAPE", "Handoff trial source must contain a trials list.", str(handoff_path))
        else:
            for index, trial in enumerate(trials):
                if not isinstance(trial, dict) or not isinstance(trial.get("resumed_without_chat"), bool):
                    _finding(findings, "WARNING", "HANDOFF_TRIAL_INVALID", f"trials[{index}] requires boolean resumed_without_chat; excluded from denominator.", str(handoff_path))
                    continue
                evidence_file = trial.get("evidence_file")
                _, evidence_path, error = _safe_input_path(root, evidence_file)
                if error or evidence_path is None:
                    _finding(findings, "WARNING", "HANDOFF_TRIAL_EVIDENCE_MISSING", f"trials[{index}] has no valid evidence_file; excluded from denominator.", str(handoff_path))
                    continue
                valid_trials += 1
                recovered += int(trial["resumed_without_chat"])
        value = _ratio(recovered, valid_trials)
        metrics["handoff_recoverability_rate"] = _metric(
            "handoff_recoverability_rate", value, recovered if value is not None else None,
            valid_trials if value is not None else None, str(handoff_path),
            None if value is not None else "No handoff trials with valid evidence were found.",
        )
    else:
        metrics["handoff_recoverability_rate"] = _metric("handoff_recoverability_rate", None, None, None, None, "Provide a handoff trial registry with evidence files.")

    temp_path = _safe_input(root, temp_registry, "temp_registry", findings)
    if temp_path:
        cleanup = audit_temp_registry(root, temp_path)
        rate = cleanup.get("summary", {}).get("temp_file_compliance_rate")
        total = cleanup.get("summary", {}).get("total_temp_items", 0)
        compliant = cleanup.get("summary", {}).get("compliant_items", 0)
        metrics["temporary_file_compliance_rate"] = _metric(
            "temporary_file_compliance_rate", rate, compliant if rate is not None else None,
            total if rate is not None else None, str(temp_path),
            None if rate is not None else "No registered/discovered temporary items; metric remains UNKNOWN.",
        )
    else:
        metrics["temporary_file_compliance_rate"] = _metric("temporary_file_compliance_rate", None, None, None, None, "Provide .aimes/temp-registry.yaml to calculate this metric.")

    audit_path = _safe_input(root, audit_log, "audit_log", findings)
    if audit_path:
        bypass_count = 0
        valid_events = 0
        for line_number, line in enumerate(audit_path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                _finding(findings, "WARNING", "AUDIT_LINE_INVALID", f"Audit line {line_number} is invalid JSON; skipped.", str(audit_path))
                continue
            if not isinstance(event, dict):
                _finding(findings, "WARNING", "AUDIT_EVENT_TYPE", f"Audit line {line_number} is not an object; skipped.", str(audit_path))
                continue
            valid_events += 1
            bypass_count += int(event.get("event_type") == "gate.bypassed")
        metrics["gate_bypass_count"] = _metric("gate_bypass_count", bypass_count, bypass_count, valid_events, str(audit_path), None)
    else:
        metrics["gate_bypass_count"] = _metric("gate_bypass_count", None, None, None, None, "Provide the audit JSONL log; absence is UNKNOWN, not zero.")

    errors = sum(item["level"] == "ERROR" for item in findings)
    warnings = sum(item["level"] == "WARNING" for item in findings)
    calculated = sum(item["status"] == "CALCULATED" for item in metrics.values())
    unknown = len(metrics) - calculated
    return {
        "schema_version": 1,
        "validator": "aimes-metrics-report",
        "generated_at": generated_at,
        "root": str(root),
        "git": git,
        "ok": errors == 0,
        "summary": {"errors": errors, "warnings": warnings, "metrics_total": len(metrics), "metrics_calculated": calculated, "metrics_unknown": unknown},
        "metrics": list(metrics.values()),
        "source_quality": {
            "docs_check_ok": docs.get("ok"),
            "docs_errors": docs.get("summary", {}).get("errors", 0),
            "trace_source_supplied": trace_manifest is not None,
            "handoff_trials_supplied": handoff_trials is not None,
            "temp_registry_supplied": temp_registry is not None,
            "audit_log_supplied": audit_log is not None,
        },
        "findings": findings,
        "note": "Unknown metrics are not estimated or coerced to zero. Values are calculated only from supplied sources that can be validated.",
    }


def _safe_input_path(root: Path, value: Any) -> tuple[str | None, Path | None, str | None]:
    if not isinstance(value, str) or not value.strip():
        return None, None, "evidence_file must be a non-empty project-relative path"
    path = Path(value)
    resolved = (root / path).resolve() if not path.is_absolute() else path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None, None, "evidence_file escapes project root"
    if not resolved.is_file():
        return value, None, f"evidence_file not found: {value}"
    return value, resolved, None
