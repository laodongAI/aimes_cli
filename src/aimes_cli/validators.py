from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

GLOBAL_STATUSES = {
    "DRAFT", "APPROVED", "PLANNED", "IN_PROGRESS", "IMPLEMENTED_UNVERIFIED",
    "VERIFIED", "FAILED", "BLOCKED", "REJECTED", "DEPRECATED", "REMOVED",
    "UNKNOWN", "NOT_APPLICABLE",
}
KNOWLEDGE_MATURITY = {"candidate", "reviewed", "validated", "deprecated"}
REUSE_DECISIONS = {"REUSE", "ADAPT", "TRANSFER_PATTERN", "DO_NOT_REUSE", "NEED_MORE_EVIDENCE"}
RISK_LEVELS = {"low", "medium", "high", "critical"}


def _load(path: Path) -> Any:
    if not path.exists() or not path.is_file():
        raise ValueError(f"Input file does not exist or is not a file: {path}")
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ValueError(f"Cannot read {path}: {exc}") from exc
    try:
        if path.suffix.lower() == ".json":
            return json.loads(raw)
        return yaml.safe_load(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: JSON 语法错误（第 {exc.lineno} 行，第 {exc.colno} 列）：{exc.msg}。请检查逗号、引号和括号是否配对。") from exc
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        location = f"第 {mark.line + 1} 行，第 {mark.column + 1} 列" if mark else "位置未知"
        problem = getattr(exc, "problem", None) or str(exc).splitlines()[0]
        raise ValueError(f"{path}: YAML 语法错误（{location}）：{problem}。请检查缩进、冒号后的空格和列表格式。") from exc


def _is_mapping(value: Any) -> bool:
    return isinstance(value, dict)


def _list(value: Any) -> bool:
    return isinstance(value, list)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _finding(findings: list[dict], level: str, code: str, message: str, path: str | None = None):
    item = {"level": level, "code": code, "message": message}
    if path:
        item["path"] = path
    findings.append(item)


def _result(kind: str, source: Path, findings: list[dict], extra: dict | None = None) -> dict:
    errors = sum(f["level"] == "ERROR" for f in findings)
    warnings = sum(f["level"] == "WARNING" for f in findings)
    out = {
        "schema_version": 1,
        "validator": f"aimes-{kind}-validator",
        "source": str(source),
        "ok": errors == 0,
        "summary": {"errors": errors, "warnings": warnings, "findings": len(findings)},
        "findings": findings,
    }
    if extra:
        out.update(extra)
    return out


def _unknown_keys(data: dict, allowed: set[str], findings: list[dict], label: str):
    for key in sorted(set(data) - allowed):
        _finding(findings, "WARNING", "UNKNOWN_FIELD", f"{label}: unrecognized field '{key}'")


def validate_requirement(path: Path) -> dict:
    data = _load(path)
    findings: list[dict] = []
    if not _is_mapping(data):
        _finding(findings, "ERROR", "ROOT_TYPE", "Requirement cognition record must be a YAML/JSON object")
        return _result("requirement", path, findings)
    allowed = {"schema_version", "record_id", "source_task_id", "status", "business_goal", "actors", "scenarios", "requirements", "constraints", "confirmed_facts", "inferences", "unknowns", "conflicts", "assumptions_proposed", "risks", "project_evidence", "questions_for_owner", "review_result", "approved_by", "approved_at"}
    _unknown_keys(data, allowed, findings, "requirement record")
    for key in ("schema_version", "record_id", "source_task_id", "status", "business_goal", "scenarios", "requirements"):
        if key not in data:
            _finding(findings, "ERROR", "REQUIRED_FIELD", f"Missing required field: {key}")
    if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
        _finding(findings, "ERROR", "SCHEMA_VERSION", "schema_version must be integer 1")
    for key in ("record_id", "source_task_id", "business_goal"):
        if key in data and not _nonempty(data[key]):
            _finding(findings, "ERROR", "FIELD_VALUE", f"{key} must be a non-empty string")
    if not isinstance(data.get("status"), str) or data.get("status") not in GLOBAL_STATUSES:
        _finding(findings, "ERROR", "INVALID_STATUS", f"status must use AIMES status vocabulary: {', '.join(sorted(GLOBAL_STATUSES))}")
    for key in ("actors", "scenarios", "requirements", "constraints", "confirmed_facts", "inferences", "unknowns", "conflicts", "assumptions_proposed", "risks", "project_evidence", "questions_for_owner"):
        if key in data and not _list(data[key]):
            _finding(findings, "ERROR", "FIELD_TYPE", f"{key} must be a list")
    for collection, id_key in (("scenarios", "id"), ("requirements", "id")):
        entries = data.get(collection, [])
        if not _list(entries):
            continue
        seen: set[str] = set()
        for i, entry in enumerate(entries):
            loc = f"{collection}[{i}]"
            if not _is_mapping(entry):
                _finding(findings, "ERROR", "ENTRY_TYPE", f"{loc} must be an object")
                continue
            item_id = entry.get(id_key)
            if not _nonempty(item_id):
                _finding(findings, "ERROR", "ENTRY_ID", f"{loc}.{id_key} must be a non-empty string")
            elif item_id in seen:
                _finding(findings, "ERROR", "DUPLICATE_ID", f"Duplicate {collection} id: {item_id}")
            else:
                seen.add(item_id)
            if collection == "requirements":
                if not _nonempty(entry.get("statement")):
                    _finding(findings, "ERROR", "REQUIREMENT_STATEMENT", f"{loc}.statement is required")
                if not _list(entry.get("acceptance_criteria")) or not entry.get("acceptance_criteria"):
                    _finding(findings, "ERROR", "ACCEPTANCE_CRITERIA", f"{loc}.acceptance_criteria must be a non-empty list")
                if not _list(entry.get("source_refs")):
                    _finding(findings, "ERROR", "SOURCE_REFS", f"{loc}.source_refs must be a list")
    if data.get("status") == "APPROVED":
        if not _nonempty(data.get("approved_by")) or not _nonempty(data.get("approved_at")):
            _finding(findings, "ERROR", "APPROVAL_EVIDENCE", "APPROVED records require approved_by and approved_at")
        if data.get("conflicts"):
            _finding(findings, "ERROR", "UNRESOLVED_CONFLICT", "APPROVED record cannot contain unresolved conflicts")
        if data.get("questions_for_owner"):
            _finding(findings, "WARNING", "OPEN_QUESTIONS", "APPROVED record still lists questions_for_owner; verify they are non-blocking")
    return _result("requirement", path, findings, {"record_id": data.get("record_id"), "status": data.get("status")})


def validate_knowledge(path: Path, root: Path | None = None) -> dict:
    data = _load(path)
    findings: list[dict] = []
    if not _is_mapping(data):
        _finding(findings, "ERROR", "ROOT_TYPE", "Knowledge asset must be a YAML/JSON object")
        return _result("knowledge", path, findings)
    allowed = {"schema_version", "knowledge_id", "title", "type", "summary", "source_refs", "produced_by_task", "baseline_commit", "applicability_conditions", "constraints", "exceptions", "invalidating_conditions", "verification_evidence", "known_defects", "counterexamples", "maintainer", "last_reviewed", "maturity", "related_entities", "superseded_by"}
    _unknown_keys(data, allowed, findings, "knowledge asset")
    required = ("schema_version", "knowledge_id", "title", "type", "summary", "source_refs", "applicability_conditions", "constraints", "exceptions", "invalidating_conditions", "maturity")
    for key in required:
        if key not in data:
            _finding(findings, "ERROR", "REQUIRED_FIELD", f"Missing required field: {key}")
    if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
        _finding(findings, "ERROR", "SCHEMA_VERSION", "schema_version must be integer 1")
    for key in ("knowledge_id", "title", "type", "summary"):
        if key in data and not _nonempty(data[key]):
            _finding(findings, "ERROR", "FIELD_VALUE", f"{key} must be a non-empty string")
    for key in ("source_refs", "applicability_conditions", "constraints", "exceptions", "invalidating_conditions", "verification_evidence", "known_defects", "counterexamples", "related_entities"):
        if key in data and not _list(data[key]):
            _finding(findings, "ERROR", "FIELD_TYPE", f"{key} must be a list")
    if not isinstance(data.get("maturity"), str) or data.get("maturity") not in KNOWLEDGE_MATURITY:
        _finding(findings, "ERROR", "INVALID_MATURITY", f"maturity must be one of: {', '.join(sorted(KNOWLEDGE_MATURITY))}")
    if not _list(data.get("source_refs")) or not data.get("source_refs"):
        _finding(findings, "ERROR", "SOURCE_REQUIRED", "At least one source_refs entry is required")
    if data.get("maturity") in {"reviewed", "validated"} and not data.get("verification_evidence"):
        _finding(findings, "ERROR", "MATURITY_EVIDENCE", f"maturity={data.get('maturity')} requires verification_evidence")
    if data.get("maturity") == "validated" and not _nonempty(data.get("last_reviewed")):
        _finding(findings, "WARNING", "REVIEW_DATE", "validated knowledge should provide last_reviewed")
    if root:
        for i, ref in enumerate(data.get("source_refs", []) if _list(data.get("source_refs")) else []):
            if not isinstance(ref, str) or not ref.strip():
                _finding(findings, "ERROR", "SOURCE_REF_TYPE", f"source_refs[{i}] must be a non-empty path or reference string")
                continue
            # File path validation applies only to explicit local path-like references.
            if ref.startswith(("./", "../")) or "/" in ref or "\\" in ref:
                candidate = (root / ref).resolve()
                try:
                    candidate.relative_to(root.resolve())
                except ValueError:
                    _finding(findings, "ERROR", "PATH_ESCAPE", f"source reference escapes project root: {ref}")
                    continue
                if not candidate.exists():
                    _finding(findings, "WARNING", "SOURCE_NOT_FOUND", f"Local source reference not found: {ref}")
    return _result("knowledge", path, findings, {"knowledge_id": data.get("knowledge_id"), "maturity": data.get("maturity")})


def validate_reuse(path: Path) -> dict:
    data = _load(path)
    findings: list[dict] = []
    if not _is_mapping(data):
        _finding(findings, "ERROR", "ROOT_TYPE", "Reuse decision must be a YAML/JSON object")
        return _result("reuse", path, findings)
    allowed = {"schema_version", "reuse_decision_id", "task_id", "status", "candidate_assets", "comparison", "decision", "rationale", "planned_adaptations", "rejected_alternatives", "verification_plan", "verification_evidence", "approval_required", "approved_by"}
    _unknown_keys(data, allowed, findings, "reuse decision")
    for key in ("schema_version", "reuse_decision_id", "task_id", "status", "candidate_assets", "comparison", "decision", "rationale", "verification_plan"):
        if key not in data:
            _finding(findings, "ERROR", "REQUIRED_FIELD", f"Missing required field: {key}")
    if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
        _finding(findings, "ERROR", "SCHEMA_VERSION", "schema_version must be integer 1")
    if not isinstance(data.get("status"), str) or data.get("status") not in GLOBAL_STATUSES:
        _finding(findings, "ERROR", "INVALID_STATUS", "status must use AIMES global status vocabulary")
    if not isinstance(data.get("decision"), str) or data.get("decision") not in REUSE_DECISIONS:
        _finding(findings, "ERROR", "INVALID_DECISION", f"decision must be one of: {', '.join(sorted(REUSE_DECISIONS))}")
    for key in ("reuse_decision_id", "task_id", "rationale"):
        if key in data and not _nonempty(data[key]):
            _finding(findings, "ERROR", "FIELD_VALUE", f"{key} must be a non-empty string")
    assets = data.get("candidate_assets")
    if not _list(assets) or not assets:
        _finding(findings, "ERROR", "CANDIDATE_ASSET", "candidate_assets must be a non-empty list")
    else:
        for i, asset in enumerate(assets):
            if not _is_mapping(asset) or not _nonempty(asset.get("asset_ref")):
                _finding(findings, "ERROR", "ASSET_REF", f"candidate_assets[{i}] must contain a non-empty asset_ref")
    if not _is_mapping(data.get("comparison")):
        _finding(findings, "ERROR", "COMPARISON", "comparison must be an object")
    if not _list(data.get("verification_plan")) or not data.get("verification_plan"):
        _finding(findings, "ERROR", "VERIFICATION_PLAN", "verification_plan must be a non-empty list")
    if data.get("decision") in {"REUSE", "ADAPT", "TRANSFER_PATTERN"} and not data.get("verification_plan"):
        _finding(findings, "ERROR", "REUSE_NO_VALIDATION", "Reuse/adaptation/pattern transfer requires a verification plan")
    if data.get("approval_required") is True and data.get("status") == "APPROVED" and not _nonempty(data.get("approved_by")):
        _finding(findings, "ERROR", "APPROVAL_EVIDENCE", "Approved reuse decision requiring approval must provide approved_by")
    return _result("reuse", path, findings, {"reuse_decision_id": data.get("reuse_decision_id"), "decision": data.get("decision")})


def _safe_project_path(root: Path, relative: str) -> tuple[Path | None, str | None]:
    if not _nonempty(relative):
        return None, "file path must be a non-empty string"
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None, "path escapes project root"
    return candidate, None


def validate_skill_registry(path: Path, root: Path, skill_id: str | None = None) -> dict:
    data = _load(path)
    findings: list[dict] = []
    if not _is_mapping(data):
        _finding(findings, "ERROR", "ROOT_TYPE", "Skill registry must be a YAML/JSON object")
        return _result("skill", path, findings)
    _unknown_keys(data, {"schema_version", "skills"}, findings, "skill registry")
    if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
        _finding(findings, "ERROR", "SCHEMA_VERSION", "schema_version must be integer 1")
    entries = data.get("skills")
    if not _list(entries):
        _finding(findings, "ERROR", "SKILLS_TYPE", "skills must be a list")
        return _result("skill", path, findings)
    required = {"id", "name", "version", "file", "purpose", "triggers", "inputs", "outputs", "applies_to", "risk_level", "required_capabilities", "forbidden_actions", "prerequisites", "dependencies", "validation_status", "evaluation_suite", "evidence"}
    seen: set[str] = set()
    checked = 0
    for i, item in enumerate(entries):
        if not _is_mapping(item):
            _finding(findings, "ERROR", "SKILL_ENTRY_TYPE", f"skills[{i}] must be an object")
            continue
        sid = item.get("id")
        if skill_id and sid != skill_id:
            continue
        checked += 1
        for key in sorted(required - set(item)):
            _finding(findings, "ERROR", "REQUIRED_FIELD", f"skills[{i}] missing field: {key}")
        _unknown_keys(item, required, findings, f"skill {sid or i}")
        if not _nonempty(sid):
            _finding(findings, "ERROR", "SKILL_ID", f"skills[{i}].id must be a non-empty string")
        elif sid in seen:
            _finding(findings, "ERROR", "DUPLICATE_ID", f"Duplicate skill id: {sid}")
        else:
            seen.add(sid)
        for key in ("name", "version", "file", "purpose"):
            if key in item and not _nonempty(item[key]):
                _finding(findings, "ERROR", "FIELD_VALUE", f"skill {sid}: {key} must be a non-empty string")
        if not isinstance(item.get("risk_level"), str) or item.get("risk_level") not in RISK_LEVELS:
            _finding(findings, "ERROR", "RISK_LEVEL", f"skill {sid}: risk_level must be one of {', '.join(sorted(RISK_LEVELS))}")
        if not isinstance(item.get("validation_status"), str) or item.get("validation_status") not in GLOBAL_STATUSES:
            _finding(findings, "ERROR", "INVALID_STATUS", f"skill {sid}: validation_status must use AIMES global status vocabulary")
        for key in ("triggers", "inputs", "outputs", "applies_to", "required_capabilities", "forbidden_actions", "prerequisites", "dependencies", "evidence"):
            if not _list(item.get(key)):
                _finding(findings, "ERROR", "FIELD_TYPE", f"skill {sid}: {key} must be a list")
        candidate, err = _safe_project_path(root, item.get("file", ""))
        if err:
            _finding(findings, "ERROR", "PATH_ESCAPE", f"skill {sid}: {err}")
        elif candidate and not candidate.is_file():
            _finding(findings, "ERROR", "SKILL_FILE_MISSING", f"skill {sid}: file not found: {item.get('file')}")
        elif candidate:
            try:
                content = candidate.read_text(encoding="utf-8-sig")
                if f"skill_id: {sid}" not in content and f"skill_id: '{sid}'" not in content and f'skill_id: "{sid}"' not in content:
                    _finding(findings, "WARNING", "SKILL_ID_MISMATCH", f"skill file should declare matching skill_id: {sid}", str(candidate))
                for section in ("Purpose", "Trigger conditions", "Required inputs", "Preconditions", "Workflow", "Outputs", "Safety and permissions", "Failure handling", "Completion criteria"):
                    if section.lower() not in content.lower():
                        _finding(findings, "WARNING", "SKILL_SECTION_MISSING", f"skill file is missing recommended section: {section}", str(candidate))
            except OSError as exc:
                _finding(findings, "ERROR", "SKILL_FILE_READ", f"Cannot read skill file: {exc}")
    if skill_id and checked == 0:
        _finding(findings, "ERROR", "SKILL_NOT_FOUND", f"Skill id not found in registry: {skill_id}")
    return _result("skill", path, findings, {"checked_skills": checked, "skill_id_filter": skill_id})
