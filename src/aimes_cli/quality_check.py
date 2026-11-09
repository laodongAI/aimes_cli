from __future__ import annotations

from fnmatch import fnmatch
import os
from pathlib import Path
import re
from typing import Any

import yaml

from .quality_profiles import resolve_quality_profile, _merge
from .project_state import load_mode_registry, read_project_state
from .quality_rules import inspect_project_sources

DEFAULT_CONFIG = {
    "schema_version": 1,
    "enabled": True,
    "enforce": False,
    "fail_on": "ERROR",
    "vue": {
        "max_sfc_lines": {"warning": 400, "error": 600},
        "max_script_lines": {"warning": 250, "error": 400},
        "max_template_lines": {"warning": 250, "error": 400},
        "disallow_direct_http_calls": True,
        "check_prop_mutation": True,
        "check_hardcoded_colors": True,
    },
    "python": {
        "max_file_lines": 800,
        "max_function_lines": 80,
        "max_cyclomatic_complexity": 12,
    },
    "general": {"max_source_file_lines": 1000, "min_coverage_percent": None},
    "exclude": ["node_modules/**", "dist/**", "build/**", ".venv/**", "vendor/**"],
}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", ".pytest_cache", ".mypy_cache"}


def _safe_config(root: Path, profile_id: str | None = None, mode_id: str | None = None) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, Any]]:
    path = (root / ".aimes" / "quality-gates.yaml").resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return dict(DEFAULT_CONFIG), [{"severity": "ERROR", "code": "QUALITY_CONFIG_PATH", "message": "Quality gate config path escapes project root", "path": ".aimes/quality-gates.yaml"}], {}
    if profile_id and mode_id:
        return dict(DEFAULT_CONFIG), [{"severity": "ERROR", "code": "QUALITY_PROFILE_SELECTION", "message": "Specify either profile_id or mode_id, not both", "path": ".aimes/quality-profiles.yaml"}], {}
    selected_mode = mode_id
    if selected_mode is None and profile_id is None:
        try:
            selected_mode = read_project_state(root).get("engineering_mode")
        except (OSError, ValueError) as exc:
            return dict(DEFAULT_CONFIG), [{"severity": "ERROR", "code": "QUALITY_STATE_READ", "message": f"Cannot read project mode state: {exc}", "path": ".aimes/project-state.yaml"}], {}
    selected_profile = profile_id
    if selected_mode:
        try:
            mode_item = load_mode_registry(root).get(selected_mode)
        except (OSError, ValueError) as exc:
            return dict(DEFAULT_CONFIG), [{"severity": "ERROR", "code": "QUALITY_MODE_REGISTRY", "message": str(exc), "path": ".aimes/project-state/engineering-modes.yaml"}], {}
        if mode_item is None:
            return dict(DEFAULT_CONFIG), [{"severity": "ERROR", "code": "QUALITY_UNKNOWN_MODE", "message": f"Unknown engineering mode: {selected_mode}", "path": ".aimes/project-state/engineering-modes.yaml"}], {}
        selected_profile = mode_item.get("quality_profile")
        if not isinstance(selected_profile, str) or not selected_profile:
            return dict(DEFAULT_CONFIG), [{"severity": "ERROR", "code": "QUALITY_PROFILE_MAPPING", "message": f"Engineering mode {selected_mode} has no quality_profile mapping", "path": ".aimes/project-state/engineering-modes.yaml"}], {}
    try:
        profile = resolve_quality_profile(root, selected_profile)
    except (OSError, ValueError) as exc:
        return dict(DEFAULT_CONFIG), [{"severity": "ERROR", "code": "QUALITY_PROFILE_CONFIG", "message": str(exc), "path": ".aimes/quality-profiles.yaml"}], {}
    profile_config = _merge(DEFAULT_CONFIG, profile["overrides"])
    if not path.is_file():
        return profile_config, [], profile
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return profile_config, [{"severity": "ERROR", "code": "QUALITY_CONFIG_READ", "message": f"Cannot read {path}: {exc}", "path": ".aimes/quality-gates.yaml"}], profile
    if not isinstance(raw, dict):
        return profile_config, [{"severity": "ERROR", "code": "QUALITY_CONFIG_TYPE", "message": "Quality gate config must be a YAML mapping", "path": ".aimes/quality-gates.yaml"}], profile
    config = _merge(profile_config, raw)
    vue = raw.get("vue", {})
    if not isinstance(vue, dict):
        return config, [{"severity": "ERROR", "code": "QUALITY_VUE_CONFIG", "message": "vue must be a YAML mapping", "path": ".aimes/quality-gates.yaml"}], profile
    config["vue"] = _merge(profile_config["vue"], vue)
    if type(config["vue"].get("disallow_direct_http_calls")) is not bool:
        return config, [{"severity": "ERROR", "code": "QUALITY_VUE_CONFIG", "message": "vue.disallow_direct_http_calls must be a boolean", "path": ".aimes/quality-gates.yaml"}], profile
    for key in ("max_sfc_lines", "max_script_lines", "max_template_lines"):
        limits = config["vue"].get(key)
        if not isinstance(limits, dict):
            return config, [{"severity": "ERROR", "code": "QUALITY_THRESHOLD_CONFIG", "message": f"vue.{key} must define warning and error thresholds", "path": ".aimes/quality-gates.yaml"}], profile
        warning, error = limits.get("warning"), limits.get("error")
        if type(warning) is not int or type(error) is not int or warning < 1 or error <= warning:
            return config, [{"severity": "ERROR", "code": "QUALITY_THRESHOLD_CONFIG", "message": f"vue.{key} requires positive integer thresholds and error > warning", "path": ".aimes/quality-gates.yaml"}], profile
    for section, limits in {
        "python": {"max_file_lines": 10000, "max_function_lines": 1000, "max_cyclomatic_complexity": 100},
        "general": {"max_source_file_lines": 20000},
    }.items():
        values = config.get(section)
        if not isinstance(values, dict):
            return config, [{"severity": "ERROR", "code": "QUALITY_RULE_CONFIG", "message": f"{section} must be a YAML mapping", "path": ".aimes/quality-gates.yaml"}], profile
        for key, maximum in limits.items():
            value = values.get(key)
            if type(value) is not int or value < 1 or value > maximum:
                return config, [{"severity": "ERROR", "code": "QUALITY_RULE_CONFIG", "message": f"{section}.{key} must be an integer between 1 and {maximum}", "path": ".aimes/quality-gates.yaml"}], profile
    coverage_threshold = config["general"].get("min_coverage_percent")
    if coverage_threshold is not None and (type(coverage_threshold) not in (int, float) or not 0 <= coverage_threshold <= 100):
        return config, [{"severity": "ERROR", "code": "QUALITY_RULE_CONFIG", "message": "general.min_coverage_percent must be between 0 and 100 or null", "path": ".aimes/quality-gates.yaml"}], profile
    for key in ("check_prop_mutation", "check_hardcoded_colors"):
        if type(config["vue"].get(key, True)) is not bool:
            return config, [{"severity": "ERROR", "code": "QUALITY_VUE_CONFIG", "message": f"vue.{key} must be a boolean", "path": ".aimes/quality-gates.yaml"}], profile
    if config.get("fail_on") not in {"WARNING", "ERROR"}:
        return config, [{"severity": "ERROR", "code": "QUALITY_FAIL_ON", "message": "fail_on must be WARNING or ERROR", "path": ".aimes/quality-gates.yaml"}], profile
    if not isinstance(config.get("exclude"), list) or any(not isinstance(x, str) for x in config["exclude"]):
        return config, [{"severity": "ERROR", "code": "QUALITY_EXCLUDE", "message": "exclude must be a list of glob strings", "path": ".aimes/quality-gates.yaml"}], profile
    if type(config.get("enabled")) is not bool or type(config.get("enforce")) is not bool:
        return config, [{"severity": "ERROR", "code": "QUALITY_POLICY_TYPE", "message": "enabled and enforce must be booleans", "path": ".aimes/quality-gates.yaml"}], profile
    return config, [], profile


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


def inspect_project_quality(root: Path, profile_id: str | None = None, mode_id: str | None = None, base_ref: str | None = None) -> dict[str, Any]:
    """Read-only, deterministic engineering checks. It never edits project files."""
    root = root.resolve()
    config, findings, profile = _safe_config(root, profile_id=profile_id, mode_id=mode_id)
    config_invalid = bool(findings)
    if not config.get("enabled", True):
        return {"ok": not config_invalid, "status": "CONFIG_ERROR" if config_invalid else "DISABLED", "root": str(root), "summary": {"files_scanned": 0, "findings": len(findings)}, "findings": findings, "policy": {"enforce": False, "fail_on": config.get("fail_on"), "profile": profile}}
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
        script_matches = list(re.finditer(r"<script(?:\s[^>]*)?>([\s\S]*?)</script\s*>", content, flags=re.IGNORECASE))
        for block in ("script", "template"):
            matches = re.findall(rf"<{block}(?:\s[^>]*)?>([\s\S]*?)</{block}\s*>", content, flags=re.IGNORECASE)
            counts[f"max_{block}_lines"] = max((len(match.splitlines()) for match in matches), default=0)
        if vue_config["disallow_direct_http_calls"]:
            call_pattern = re.compile(r"\b(?:fetch\s*\(|axios\s*\.\s*(?:get|post|put|patch|delete|request)\s*\()", re.IGNORECASE)
            for script_match in script_matches:
                script = script_match.group(1)
                absolute_start = script_match.start(1)
                for offset, line_text in enumerate(script.splitlines()):
                    stripped = line_text.strip()
                    if stripped.startswith(("//", "/*", "*", "*/")):
                        continue
                    match = call_pattern.search(line_text)
                    if match:
                        line_number = content.count("\n", 0, absolute_start) + offset + 1
                        findings.append({
                            "severity": "WARNING",
                            "code": "VUE_DIRECT_HTTP_CALL",
                            "path": relative,
                            "line": line_number,
                            "evidence": match.group(0).strip(),
                            "message": "Vue component script performs a direct HTTP request. Move transport and endpoint handling into a reusable API service; keep the component focused on UI state and orchestration.",
                        })
        for code, key, label, recommendation in rules:
            value = counts[key]
            limits = vue_config[key]
            severity = "ERROR" if value > limits["error"] else "WARNING" if value > limits["warning"] else None
            if severity:
                findings.append({"severity": severity, "code": code, "path": relative, "line": 1, "metric": value, "threshold": limits[severity.lower()], "message": f"{label}: {value} lines (threshold {limits[severity.lower()]}). {recommendation}"})
    source_findings, source_counts = inspect_project_sources(root, config, config.get("exclude", []), base_ref=base_ref)
    findings.extend(source_findings)
    fail_on = config.get("fail_on", "ERROR")
    blocking = any(item.get("severity") == "ERROR" or (fail_on == "WARNING" and item.get("severity") == "WARNING") for item in findings)
    errors = sum(item.get("severity") == "ERROR" for item in findings)
    warnings = sum(item.get("severity") == "WARNING" for item in findings)
    enforced = config.get("enforce") is True
    return {
        "ok": not config_invalid and not (enforced and blocking),
        "status": "CONFIG_ERROR" if config_invalid else "FAIL" if enforced and blocking else "PASS_WITH_FINDINGS" if findings else "PASS",
        "root": str(root),
        "summary": {"files_scanned": len(vue_files), **source_counts, "errors": errors, "warnings": warnings, "findings": len(findings)},
        "policy": {"enforce": enforced, "fail_on": fail_on, "config": ".aimes/quality-gates.yaml", "profile": profile},
        "findings": findings,
        "limitations": [
            "Vue checks detect SFC size, direct HTTP calls, obvious prop mutation, and literal colors; they cannot prove component responsibility, semantic reuse, complete Props/Emits contracts, Composable suitability, or visual conformance.",
            "Python AST checks detect selected complexity, mutable defaults, broad exception handling, hard-coded credential-like literals, and direct persistence calls in decorated route handlers; they do not prove the full dependency graph or transaction correctness.",
            "General checks currently provide source-size metrics. Dependency vulnerability databases, measured test coverage, semantic duplication, and public API compatibility require dedicated evidence providers and are not claimed as implemented.",
            "Static findings are heuristics; review evidence before enabling blocking enforcement."
        ],
    }
