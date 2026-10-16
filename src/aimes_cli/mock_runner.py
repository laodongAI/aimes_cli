from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import yaml


def _load(path: Path) -> Any:
    if not path.is_file():
        raise ValueError(f"Input file does not exist or is not a file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")) if path.suffix.lower() == ".json" else yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"Cannot parse {path}: {exc}") from exc


def run_mock(suite_path: Path, responses_path: Path, selected_ids: list[str] | None = None) -> dict:
    """Run deterministic lexical checks against supplied fixtures; not a model-quality evaluation."""
    suite = _load(suite_path)
    fixture = _load(responses_path)
    if not isinstance(suite, dict) or not isinstance(suite.get("cases"), list):
        raise ValueError("Evaluation suite must contain a cases list")
    if not isinstance(fixture, dict) or not isinstance(fixture.get("responses"), dict):
        raise ValueError("Mock responses file must contain a responses mapping")
    cases = [c for c in suite["cases"] if isinstance(c, dict) and (selected_ids is None or c.get("case_id") in selected_ids)]
    if selected_ids:
        missing = sorted(set(selected_ids) - {c.get("case_id") for c in cases})
        if missing:
            raise ValueError("Unknown case_id(s): " + ", ".join(missing))
    results = []
    for case in cases:
        cid = case.get("case_id", "UNKNOWN")
        response_entry = fixture["responses"].get(cid)
        if not isinstance(response_entry, dict) or not isinstance(response_entry.get("text"), str):
            results.append({"case_id": cid, "status": "NOT_RUN", "hard_gates": {}, "scores": {}, "evidence_refs": [], "reason": "No mock response fixture supplied"})
            continue
        text = response_entry["text"]
        expected = case.get("expected", {}) if isinstance(case.get("expected"), dict) else {}
        required = [x for x in expected.get("required_findings", []) if isinstance(x, str)]
        forbidden = [x for x in expected.get("forbidden_claims", []) if isinstance(x, str)]
        missing_required = [x for x in required if x.casefold() not in text.casefold()]
        found_forbidden = [x for x in forbidden if x.casefold() in text.casefold()]
        checks = len(required) + len(forbidden)
        passed = not missing_required and not found_forbidden
        score = round((checks - len(missing_required) - len(found_forbidden)) / checks, 4) if checks else 1.0
        gates = {f"required_phrase_{i+1}": ("FAIL" if item in missing_required else "PASS") for i, item in enumerate(required)}
        gates.update({f"forbidden_phrase_absent_{i+1}": ("FAIL" if item in found_forbidden else "PASS") for i, item in enumerate(forbidden)})
        results.append({
            "case_id": cid,
            "status": "PASS" if passed else "FAIL",
            "hard_gates": gates,
            "scores": {"lexical_contract_coverage": score},
            "evidence_refs": [str(responses_path)],
            "diagnostics": {"missing_required_phrases": missing_required, "found_forbidden_phrases": found_forbidden,
                            "check_type": "case-insensitive exact-substring; does not assess semantic equivalence"},
        })
    now = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": 1,
        "metadata": {"run_id": "mock-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"),
                     "suite_id": suite.get("suite_id", "UNKNOWN"), "suite_version": str(suite.get("version", "UNKNOWN")),
                     "model": "mock-fixture-not-a-model", "tool_version": "aimes-cli/0.5.2", "skill_version": "fixture-defined",
                     "started_at": now, "execution_mode": "MOCK_FIXTURE", "model_evaluation": False},
        "case_results": results,
        "limitations": ["这是对预置文本夹具的确定性字面匹配，不调用模型。", "结果仅验证评测管道和基本词面检查，不代表真实模型质量或语义契约符合率。", "PASS 仅表示字面检查通过。"],
    }
