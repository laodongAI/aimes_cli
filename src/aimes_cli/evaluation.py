from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import yaml

HARD_GATE_STATES = {"PASS", "FAIL", "NOT_RUN", "BLOCKED"}


def _load(path: Path) -> Any:
    if not path.is_file():
        raise ValueError(f"Input file does not exist or is not a file: {path}")
    try:
        raw = path.read_text(encoding="utf-8-sig")
        return json.loads(raw) if path.suffix.lower() == ".json" else yaml.safe_load(raw)
    except OSError as exc:
        raise ValueError(f"无法读取 {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: JSON 语法错误（第 {exc.lineno} 行，第 {exc.colno} 列）：{exc.msg}。请检查逗号、引号和括号是否配对。") from exc
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        location = f"第 {mark.line + 1} 行，第 {mark.column + 1} 列" if mark else "位置未知"
        problem = getattr(exc, "problem", None) or str(exc).splitlines()[0]
        raise ValueError(f"{path}: YAML 语法错误（{location}）：{problem}。请检查缩进、冒号后的空格和列表格式。") from exc


def _finding(fs, level, code, message):
    fs.append({"level": level, "code": code, "message": message})


def _report(kind, path, findings, **extra):
    errors = sum(f["level"] == "ERROR" for f in findings)
    warnings = sum(f["level"] == "WARNING" for f in findings)
    return {"schema_version": 1, "validator": f"aimes-evaluation-{kind}", "source": str(path),
            "ok": errors == 0, "summary": {"errors": errors, "warnings": warnings, "findings": len(findings)},
            "findings": findings, **extra}


def validate_suite(path: Path) -> dict:
    data = _load(path); fs = []
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
        _finding(fs, "ERROR", "SUITE_SHAPE", "Evaluation suite must be an object with a cases list")
        return _report("suite-validation", path, fs, checked_cases=0)
    for key in ("suite_id", "version"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            _finding(fs, "ERROR", "SUITE_METADATA_REQUIRED", f"{key} is required")
    seen = set()
    for i, case in enumerate(data["cases"]):
        loc = f"cases[{i}]"
        if not isinstance(case, dict):
            _finding(fs, "ERROR", "CASE_TYPE", f"{loc} must be an object"); continue
        cid = case.get("case_id")
        if not isinstance(cid, str) or not cid.strip(): _finding(fs, "ERROR", "CASE_ID_REQUIRED", f"{loc}.case_id is required")
        elif cid in seen: _finding(fs, "ERROR", "DUPLICATE_CASE_ID", f"Duplicate case_id: {cid}")
        else: seen.add(cid)
        for key in ("objective", "input", "expected", "scoring"):
            if key not in case: _finding(fs, "ERROR", "CASE_FIELD_REQUIRED", f"{loc}.{key} is required")
        if "input" in case and not isinstance(case["input"], dict): _finding(fs, "ERROR", "CASE_INPUT_TYPE", f"{loc}.input must be an object")
        expected = case.get("expected", {})
        if isinstance(expected, dict):
            for k in ("required_findings", "forbidden_claims", "expected_questions", "acceptance_checks"):
                if k in expected and not isinstance(expected[k], list): _finding(fs, "ERROR", "EXPECTED_FIELD_TYPE", f"{loc}.expected.{k} must be a list")
        scoring = case.get("scoring", {})
        if isinstance(scoring, dict):
            for k in ("hard_gates", "diagnostic_dimensions"):
                if k in scoring and not isinstance(scoring[k], list): _finding(fs, "ERROR", "SCORING_FIELD_TYPE", f"{loc}.scoring.{k} must be a list")
            for gate in scoring.get("hard_gates", []) if isinstance(scoring.get("hard_gates", []), list) else []:
                if not isinstance(gate, (str, dict)): _finding(fs, "ERROR", "HARD_GATE_TYPE", f"{loc} hard gate must be a string or object")
    if not data["cases"]: _finding(fs, "WARNING", "EMPTY_SUITE", "Evaluation suite contains no cases")
    return _report("suite-validation", path, fs, checked_cases=len(data["cases"]), case_ids=sorted(seen), suite_id=data.get("suite_id"), version=data.get("version"))


def validate_run(path: Path) -> dict:
    data = _load(path); fs = []
    if not isinstance(data, dict) or not isinstance(data.get("case_results"), list):
        _finding(fs, "ERROR", "RUN_SHAPE", "Run record must be an object with a case_results list")
        return _report("run-validation", path, fs, checked_cases=0)
    metadata = data.get("metadata")
    if not isinstance(metadata, dict): _finding(fs, "ERROR", "RUN_METADATA_REQUIRED", "metadata object is required")
    else:
        for k in ("run_id", "suite_id", "suite_version", "model", "tool_version", "skill_version", "started_at"):
            if not isinstance(metadata.get(k), str) or not metadata[k].strip(): _finding(fs, "WARNING", "RUN_METADATA_MISSING", f"metadata.{k} should be recorded for reproducibility")
    seen = set()
    for i, item in enumerate(data["case_results"]):
        loc=f"case_results[{i}]"
        if not isinstance(item, dict): _finding(fs,"ERROR","RESULT_TYPE",f"{loc} must be an object"); continue
        cid=item.get("case_id")
        if not isinstance(cid,str) or not cid.strip(): _finding(fs,"ERROR","RESULT_CASE_ID_REQUIRED",f"{loc}.case_id is required")
        elif cid in seen: _finding(fs,"ERROR","DUPLICATE_RESULT_CASE",f"Duplicate result for case {cid}")
        else: seen.add(cid)
        gates=item.get("hard_gates",{})
        if not isinstance(gates,dict): _finding(fs,"ERROR","HARD_GATES_TYPE",f"{loc}.hard_gates must be an object"); gates={}
        for name,state in gates.items():
            if state not in HARD_GATE_STATES: _finding(fs,"ERROR","HARD_GATE_STATE",f"{loc}.hard_gates.{name} must be one of {sorted(HARD_GATE_STATES)}")
        scores=item.get("scores",{})
        if not isinstance(scores,dict): _finding(fs,"ERROR","SCORES_TYPE",f"{loc}.scores must be an object")
        else:
            for name,value in scores.items():
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not 0 <= value <= 1:
                    _finding(fs,"ERROR","SCORE_RANGE",f"{loc}.scores.{name} must be a number from 0 to 1")
        if item.get("status") not in {"PASS","FAIL","BLOCKED","NOT_RUN"}:
            _finding(fs,"ERROR","CASE_RESULT_STATUS",f"{loc}.status must be PASS, FAIL, BLOCKED or NOT_RUN")
        if item.get("status")=="PASS" and any(v != "PASS" for v in gates.values()):
            _finding(fs,"ERROR","PASS_WITH_FAILED_GATE",f"{loc} status PASS contradicts a non-PASS hard gate")
        if item.get("status")=="PASS" and not item.get("evidence_refs"):
            _finding(fs,"WARNING","RESULT_EVIDENCE_MISSING",f"{loc} PASS result should reference evidence")
    return _report("run-validation",path,fs,checked_cases=len(data["case_results"]),case_ids=sorted(seen))



def validate_run_against_suite(suite_path: Path, run_path: Path) -> dict:
    """Validate a recorded run against its fixed suite, including exact case and hard-gate coverage."""
    suite = _load(suite_path)
    run = _load(run_path)
    findings = []

    suite_check = validate_suite(suite_path)
    run_check = validate_run(run_path)
    if not suite_check["ok"]:
        _finding(findings, "ERROR", "SUITE_INVALID", "Evaluation suite failed structural validation")
    if not run_check["ok"]:
        _finding(findings, "ERROR", "RUN_INVALID", "Evaluation run failed structural validation")

    if not isinstance(suite, dict) or not isinstance(suite.get("cases"), list):
        _finding(findings, "ERROR", "SUITE_SHAPE", "Suite must contain a cases list")
        return _report("run-suite-coverage", run_path, findings, suite=str(suite_path), checked_cases=0)
    if not isinstance(run, dict) or not isinstance(run.get("case_results"), list):
        _finding(findings, "ERROR", "RUN_SHAPE", "Run must contain a case_results list")
        return _report("run-suite-coverage", run_path, findings, suite=str(suite_path), checked_cases=0)

    suite_cases = {
        item.get("case_id"): item
        for item in suite["cases"]
        if isinstance(item, dict) and isinstance(item.get("case_id"), str)
    }
    run_cases = {
        item.get("case_id"): item
        for item in run["case_results"]
        if isinstance(item, dict) and isinstance(item.get("case_id"), str)
    }
    expected_ids, actual_ids = set(suite_cases), set(run_cases)
    missing = sorted(expected_ids - actual_ids)
    unexpected = sorted(actual_ids - expected_ids)
    if missing:
        _finding(findings, "ERROR", "SUITE_CASES_MISSING", f"Run is missing suite cases: {', '.join(missing)}")
    if unexpected:
        _finding(findings, "ERROR", "UNEXPECTED_RUN_CASES", f"Run contains cases not in the suite: {', '.join(unexpected)}")

    metadata = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}
    if metadata.get("suite_id") != suite.get("suite_id"):
        _finding(findings, "ERROR", "SUITE_ID_MISMATCH", "Run metadata.suite_id does not match the selected suite")
    if metadata.get("suite_version") != suite.get("version"):
        _finding(findings, "ERROR", "SUITE_VERSION_MISMATCH", "Run metadata.suite_version does not match the selected suite version")

    gate_coverage = []
    for case_id in sorted(expected_ids & actual_ids):
        suite_case, result = suite_cases[case_id], run_cases[case_id]
        scoring = suite_case.get("scoring", {})
        expected_gates = []
        if isinstance(scoring, dict):
            for gate in scoring.get("hard_gates", []) if isinstance(scoring.get("hard_gates", []), list) else []:
                if isinstance(gate, str) and gate.strip():
                    expected_gates.append(gate.strip())
                elif isinstance(gate, dict) and isinstance(gate.get("id"), str) and gate["id"].strip():
                    expected_gates.append(gate["id"].strip())
        recorded = result.get("hard_gates", {})
        recorded_names = set(recorded) if isinstance(recorded, dict) else set()
        missing_gates = sorted(set(expected_gates) - recorded_names)
        unexpected_gates = sorted(recorded_names - set(expected_gates))
        gate_coverage.append({
            "case_id": case_id,
            "expected_gates": sorted(set(expected_gates)),
            "recorded_gates": sorted(recorded_names),
            "missing_gates": missing_gates,
            "unexpected_gates": unexpected_gates,
        })
        if missing_gates:
            _finding(findings, "ERROR", "HARD_GATES_MISSING", f"{case_id} is missing required hard gates: {', '.join(missing_gates)}")
        if unexpected_gates:
            _finding(findings, "WARNING", "UNDECLARED_HARD_GATES", f"{case_id} records gates not declared by the suite: {', '.join(unexpected_gates)}")
        if result.get("status") == "PASS" and not result.get("evidence_refs"):
            _finding(findings, "ERROR", "PASS_EVIDENCE_REQUIRED", f"{case_id} cannot be accepted as PASS without evidence_refs")
        if result.get("status") == "PASS" and any(recorded.get(name) != "PASS" for name in expected_gates):
            _finding(findings, "ERROR", "PASS_WITH_INCOMPLETE_SUITE_GATES", f"{case_id} is PASS but one or more suite hard gates are missing or non-PASS")

    return _report(
        "run-suite-coverage", run_path, findings,
        suite=str(suite_path),
        suite_id=suite.get("suite_id"),
        suite_version=suite.get("version"),
        expected_case_count=len(expected_ids),
        recorded_case_count=len(actual_ids),
        checked_cases=len(expected_ids & actual_ids),
        missing_cases=missing,
        unexpected_cases=unexpected,
        hard_gate_coverage=gate_coverage,
        note="A structurally valid run is not proof that the recorded outcomes are truthful. Keep raw outputs, execution logs, and independently verifiable evidence for each case.",
    )

def build_run_report(path: Path) -> dict:
    data=_load(path)
    if not isinstance(data,dict) or not isinstance(data.get("case_results"),list): raise ValueError("Run record must contain case_results list")
    results=[x for x in data["case_results"] if isinstance(x,dict)]
    counts={s:sum(x.get("status")==s for x in results) for s in ("PASS","FAIL","BLOCKED","NOT_RUN")}
    gate_counts={}
    score_values={}
    for item in results:
        for name,state in (item.get("hard_gates",{}) or {}).items():
            entry=gate_counts.setdefault(name,{s:0 for s in sorted(HARD_GATE_STATES)})
            if state in entry: entry[state]+=1
        for name,value in (item.get("scores",{}) or {}).items():
            if isinstance(value,(int,float)) and not isinstance(value,bool): score_values.setdefault(name,[]).append(value)
    means={k:round(sum(v)/len(v),4) for k,v in sorted(score_values.items()) if v}
    return {"schema_version":1,"report_type":"AIMES_EVALUATION_RUN_REPORT","source":str(path),"metadata":data.get("metadata",{}),"case_count":len(results),"status_counts":counts,"pass_rate":round(counts["PASS"]/len(results),4) if results else None,"hard_gate_counts":gate_counts,"diagnostic_score_means":means,"failed_cases":[x.get("case_id") for x in results if x.get("status")=="FAIL"],"blocked_cases":[x.get("case_id") for x in results if x.get("status")=="BLOCKED"],"note":"分数是诊断指标；任何硬门禁失败都必须单独报告，不可由平均分抵消。"}


def compare_runs(baseline_path: Path, candidate_path: Path) -> dict:
    b=_load(baseline_path); c=_load(candidate_path)
    if not isinstance(b,dict) or not isinstance(b.get("case_results"),list): raise ValueError("Baseline run must contain case_results list")
    if not isinstance(c,dict) or not isinstance(c.get("case_results"),list): raise ValueError("Candidate run must contain case_results list")
    def index(data): return {x.get("case_id"):x for x in data["case_results"] if isinstance(x,dict) and isinstance(x.get("case_id"),str)}
    bi,ci=index(b),index(c); common=sorted(set(bi)&set(ci)); findings=[]
    added=sorted(set(ci)-set(bi)); removed=sorted(set(bi)-set(ci))
    regressions=[]; improvements=[]; gate_changes=[]; score_deltas={}
    for cid in common:
        old,new=bi[cid],ci[cid]
        if old.get("status")=="PASS" and new.get("status")!="PASS": regressions.append({"case_id":cid,"from":old.get("status"),"to":new.get("status")})
        if old.get("status")!="PASS" and new.get("status")=="PASS": improvements.append({"case_id":cid,"from":old.get("status"),"to":"PASS"})
        for gate in sorted(set(old.get("hard_gates",{}))|set(new.get("hard_gates",{}))):
            a=old.get("hard_gates",{}).get(gate,"NOT_RECORDED"); z=new.get("hard_gates",{}).get(gate,"NOT_RECORDED")
            if a!=z:
                change={"case_id":cid,"gate":gate,"baseline":a,"candidate":z}; gate_changes.append(change)
                if a=="PASS" and z!="PASS": _finding(findings,"ERROR","HARD_GATE_REGRESSION",f"{cid} hard gate {gate} regressed from PASS to {z}")
        for dim in sorted(set(old.get("scores",{}))&set(new.get("scores",{}))):
            a,z=old["scores"][dim],new["scores"][dim]
            if isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(z,(int,float)) and not isinstance(z,bool): score_deltas.setdefault(dim,[]).append(z-a)
    return {"schema_version":1,"report_type":"AIMES_EVALUATION_REGRESSION_REPORT","baseline":str(baseline_path),"candidate":str(candidate_path),"ok":not any(f["level"]=="ERROR" for f in findings),"common_case_count":len(common),"added_cases":added,"removed_cases":removed,"status_regressions":regressions,"status_improvements":improvements,"hard_gate_changes":gate_changes,"diagnostic_score_mean_delta":{k:round(sum(v)/len(v),4) for k,v in sorted(score_deltas.items()) if v},"findings":findings,"note":"比较结果只反映已记录的运行结果；案例集不同、环境不同或证据不完整时，不应直接归因于 Skill/模型改动。"}
