from __future__ import annotations

from fnmatch import fnmatch
import os
from pathlib import Path
import re
from typing import Any

import yaml

DEFAULT_CONFIG = {
    "schema_version": 1,
    "enabled": True,
    "enforce": False,
    "fail_on": "ERROR",
    "vue": {
        "max_sfc_lines": {"warning": 400, "error": 600},
        "max_script_lines": {"warning": 250, "error": 400},
        "max_template_lines": {"warning": 250, "error": 400},
    },
    "exclude": ["node_modules/**", "dist/**", "build/**", ".venv/**", "vendor/**"],
}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", ".pytest_cache", ".mypy_cache"}


def _safe_config(root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    path = root / ".aimes" / "quality-gates.yaml"
    if not path.is_file():
        return dict(DEFAULT_CONFIG), []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return dict(DEFAULT_CONFIG), [{"severity": "ERROR", "code": "QUALITY_CONFIG_READ", "message": f"Cannot read {path}: {exc}", "path": ".aimes/quality-gates.yaml"}]
    if not isinstance(raw, dict):
        return dict(DEFAULT_CONFIG), [{"severity": "ERROR", "code": "QUALITY_CONFIG_TYPE", "message": "Quality gate config must be a YAML mapping", "path": ".aimes/quality-gates.yaml"}]
    config = {**DEFAULT_CONFIG, **raw}
    vue = raw.get("vue", {})
    if not isinstance(vue, dict):
        return config, [{"severity": "ERROR", "code": "QUALITY_VUE_CONFIG", "message": "vue must be a YAML mapping", "path": ".aimes/quality-gates.yaml"}]
    config["vue"] = {**DEFAULT_CONFIG["vue"], **vue}
    for key in ("max_sfc_lines", "max_script_lines", "max_template_lines"):
        limits = config["vue"].get(key)
        if not isinstance(limits, dict):
            return config, [{"severity": "ERROR", "code": "QUALITY_THRESHOLD_CONFIG", "message": f"vue.{key} must define warning and error thresholds", "path": ".aimes/quality-gates.yaml"}]
        warning, error = limits.get("warning"), limits.get("error")
        if type(warning) is not int or type(error) is not int or warning < 1 or error <= warning:
            return config, [{"severity": "ERROR", "code": "QUALITY_THRESHOLD_CONFIG", "message": f"vue.{key} requires positive integer thresholds and error > warning", "path": ".aimes/quality-gates.yaml"}]
    if config.get("fail_on") not in {"WARNING", "ERROR"}:
        return config, [{"severity": "ERROR", "code": "QUALITY_FAIL_ON", "message": "fail_on must be WARNING or ERROR", "path": ".aimes/quality-gates.yaml"}]
    if not isinstance(config.get("exclude"), list) or any(not isinstance(x, str) for x in config["exclude"]):
        return config, [{"severity": "ERROR", "code": "QUALITY_EXCLUDE", "message": "exclude must be a list of glob strings", "path": ".aimes/quality-gates.yaml"}]
    if type(config.get("enabled")) is not bool or type(config.get("enforce")) is not bool:
        return config, [{"severity": "ERROR", "code": "QUALITY_POLICY_TYPE", "message": "enabled and enforce must be booleans", "path": ".aimes/quality-gates.yaml"}]
    return config, []


def _is_excluded(relative: str, patterns: list[str]) -> bool:
    normalized = relative.replace("\\", "/")
    parts = normalized.split("/")
    if any(part in SKIP_DIRS for part in parts):
        return True
    return any(fnmatch(normalized, pattern) or fnmatch(normalized, pattern.rstrip("/") + "/**") for pattern in patterns)


def _iter_vue_files(root: Path, patterns: list[str]):
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        dirs[:] = [
            name for name in dirs
            if name not in SKIP_DIRS
            and not (current_path / name).is_symlink()
            and not _is_excluded((current_path / name).relative_to(root).as_posix(), patterns)
        ]
        for name in files:
            path = current_path / name
            if name.lower().endswith(".vue") and not path.is_symlink():
                relative = path.relative_to(root).as_posix()
                if not _is_excluded(relative, patterns):
                    yield relative, path


def inspect_project_quality(root: Path) -> dict[str, Any]:
    """Read-only, deterministic engineering checks. It never edits project files."""
    root = root.resolve()
    config, findings = _safe_config(root)
    config_invalid = bool(findings)
    if not config.get("enabled", True):
        return {"ok": not config_invalid, "status": "CONFIG_ERROR" if config_invalid else "DISABLED", "root": str(root), "summary": {"files_scanned": 0, "findings": len(findings)}, "findings": findings, "policy": {"enforce": False, "fail_on": config.get("fail_on")}}
    vue_files = list(_iter_vue_files(root, config["exclude"]))
    vue_config = config["vue"]
    rules = (
        ("SFC_LINES", "max_sfc_lines", "Vue SFC total lines", "Split large components by business responsibility; keep Page/View focused on orchestration."),
        ("SCRIPT_LINES", "max_script_lines", "Vue script block lines", "Move reusable stateful logic into a Composable and business operations into services."),
        ("TEMPLATE_LINES", "max_template_lines", "Vue template block lines", "Extract cohesive business regions into focused child components."),
    )
    for relative, path in sorted(vue_files):
        try:
            content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            findings.append({"severity": "WARNING", "code": "SFC_READ", "path": relative, "message": f"Unable to read Vue SFC: {exc}"})
            continue
        counts = {"max_sfc_lines": len(content.splitlines())}
        for block in ("script", "template"):
            matches = re.findall(rf"<{block}(?:\s[^>]*)?>([\s\S]*?)</{block}\s*>", content, flags=re.IGNORECASE)
            counts[f"max_{block}_lines"] = max((len(match.splitlines()) for match in matches), default=0)
        for code, key, label, recommendation in rules:
            value = counts[key]
            limits = vue_config[key]
            severity = "ERROR" if value > limits["error"] else "WARNING" if value > limits["warning"] else None
            if severity:
                findings.append({"severity": severity, "code": code, "path": relative, "line": 1, "metric": value, "threshold": limits[severity.lower()], "message": f"{label}: {value} lines (threshold {limits[severity.lower()]}). {recommendation}"})
    fail_on = config.get("fail_on", "ERROR")
    blocking = any(item.get("severity") == "ERROR" or (fail_on == "WARNING" and item.get("severity") == "WARNING") for item in findings)
    errors = sum(item.get("severity") == "ERROR" for item in findings)
    warnings = sum(item.get("severity") == "WARNING" for item in findings)
    enforced = config.get("enforce") is True
    return {
        "ok": not config_invalid and not (enforced and blocking),
        "status": "CONFIG_ERROR" if config_invalid else "FAIL" if enforced and blocking else "PASS_WITH_FINDINGS" if findings else "PASS",
        "root": str(root),
        "summary": {"files_scanned": len(vue_files), "errors": errors, "warnings": warnings, "findings": len(findings)},
        "policy": {"enforce": enforced, "fail_on": fail_on, "config": ".aimes/quality-gates.yaml"},
        "findings": findings,
        "limitations": ["This initial deterministic profile checks Vue SFC size only; it does not infer semantic duplication, component reuse, or architecture correctness."],
    }
