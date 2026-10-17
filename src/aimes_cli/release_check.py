from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


def _finding(findings: list[dict[str, Any]], level: str, code: str, message: str, path: str | None = None) -> None:
    item: dict[str, Any] = {"level": level, "code": code, "message": message}
    if path:
        item["path"] = path
    findings.append(item)


def validate_release(root: Path) -> dict[str, Any]:
    """Validate source package/readme/core-version compatibility without changing files."""
    root = root.resolve()
    findings: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool | None, message: str, path: str | None = None) -> None:
        checks.append({"name": name, "status": "PASS" if ok is True else "FAIL" if ok is False else "UNKNOWN", "message": message, "path": path})
        if ok is False:
            _finding(findings, "ERROR", "RELEASE_COMPATIBILITY", message, path)
        elif ok is None:
            _finding(findings, "WARNING", "RELEASE_CHECK_UNKNOWN", message, path)

    pyproject = root / "pyproject.toml"
    init_file = root / "src" / "aimes_cli" / "__init__.py"
    readme = root / "README.md"
    core_dir = root / "src" / "aimes_cli" / "templates" / "core"
    build_script = root / "build_windows_exe.ps1"

    package_version = runtime_version = readme_version = governance_version = None
    if pyproject.is_file():
        text = pyproject.read_text(encoding="utf-8-sig")
        project_match = re.search(r"(?ms)^\[project\]\s*(.*?)(?=^\[|\Z)", text)
        version_match = re.search(r'''(?m)^\s*version\s*=\s*["']([^"']+)["']''', project_match.group(1)) if project_match else None
        package_version = version_match.group(1) if version_match else None
        check("package_version_present", package_version is not None, "pyproject.toml [project].version is present.", "pyproject.toml")
    else:
        check("package_version_present", None, "pyproject.toml is absent; source package version cannot be checked.", "pyproject.toml")

    if init_file.is_file():
        text = init_file.read_text(encoding="utf-8-sig")
        version_match = re.search(r'''(?m)^\s*__version__\s*=\s*["']([^"']+)["']''', text)
        gov_match = re.search(r'''(?m)^\s*GOVERNANCE_VERSION\s*=\s*["']([^"']+)["']''', text)
        runtime_version = version_match.group(1) if version_match else None
        governance_version = gov_match.group(1) if gov_match else None
        check("runtime_version_present", runtime_version is not None, "Runtime __version__ is present.", "src/aimes_cli/__init__.py")
        check("governance_version_present", governance_version is not None, "GOVERNANCE_VERSION is present.", "src/aimes_cli/__init__.py")
    else:
        check("runtime_version_present", None, "src/aimes_cli/__init__.py is absent; source package version cannot be checked.", "src/aimes_cli/__init__.py")
        check("governance_version_present", None, "GOVERNANCE_VERSION cannot be checked without source package.", "src/aimes_cli/__init__.py")

    if package_version is not None and runtime_version is not None:
        check("package_runtime_version_match", package_version == runtime_version,
              f"pyproject version={package_version!r}; runtime version={runtime_version!r}.", "pyproject.toml")
    else:
        check("package_runtime_version_match", None, "Package/runtime version comparison is unavailable.")

    if readme.is_file():
        text = readme.read_text(encoding="utf-8-sig")
        match = re.search(r"(?mi)^#.*\(V(\d+\.\d+\.\d+)\)", text)
        readme_version = match.group(1) if match else None
        check("readme_version_present", readme_version is not None, "README title contains a version marker such as (V0.7.9).", "README.md")
    else:
        check("readme_version_present", None, "README.md is absent; documentation version cannot be checked.", "README.md")

    if package_version is not None and readme_version is not None:
        check("readme_package_version_match", package_version == readme_version,
              f"README version={readme_version!r}; package version={package_version!r}.", "README.md")
    else:
        check("readme_package_version_match", None, "README/package version comparison is unavailable.")

    core_files = sorted(core_dir.glob("AIMES-CORE-V*.md")) if core_dir.is_dir() else []
    if governance_version is not None:
        expected_name = f"AIMES-CORE-V{governance_version}.md"
        expected = core_dir / expected_name
        check("governance_core_template_present", expected.is_file(),
              f"Expected packaged governance core template {expected_name}.", str(expected.relative_to(root)))
        check("single_supported_core_template", len(core_files) == 1,
              f"Expected exactly one packaged core template; found {len(core_files)}.", str(core_dir.relative_to(root)))
    else:
        check("governance_core_template_present", None, "Cannot compare governance version to packaged core template.")

    if pyproject.is_file():
        text = pyproject.read_text(encoding="utf-8-sig")
        check("package_data_templates_included", "templates/**/*.md" in text,
              "Package data configuration must include templates/**/*.md.", "pyproject.toml")
        check("package_data_schemas_included", "schemas/*.json" in text,
              "Package data configuration must include schemas/*.json.", "pyproject.toml")
    else:
        check("package_data_templates_included", None, "Package data configuration unavailable.")
        check("package_data_schemas_included", None, "Package data configuration unavailable.")

    if build_script.is_file():
        text = build_script.read_text(encoding="utf-8-sig")
        check("windows_exe_collects_package_data", "--collect-data aimes_cli" in text,
              "Windows EXE build must collect aimes_cli package data so the governance core template is bundled.",
              "build_windows_exe.ps1")
    else:
        check("windows_exe_collects_package_data", None, "Windows EXE build script is absent.", "build_windows_exe.ps1")

    config_path = root / ".aimes" / "config.yaml"
    if config_path.is_file():
        try:
            config = yaml.safe_load(config_path.read_text(encoding="utf-8-sig"))
        except (OSError, yaml.YAMLError) as exc:
            check("project_governance_version", False, f"Cannot parse .aimes/config.yaml: {exc}", ".aimes/config.yaml")
        else:
            gov = config.get("governance", {}) if isinstance(config, dict) else {}
            config_version = gov.get("version") if isinstance(gov, dict) else None
            config_core = gov.get("core") if isinstance(gov, dict) else None
            check("project_governance_version", governance_version is not None and config_version == governance_version,
                  f"Project governance version={config_version!r}; package governance version={governance_version!r}.", ".aimes/config.yaml")
            if isinstance(config_core, str) and config_core.strip():
                core_path = (root / config_core).resolve()
                try:
                    core_path.relative_to(root)
                    within_root = True
                except ValueError:
                    within_root = False
                check("project_core_path", within_root and core_path.is_file(),
                      f"Configured governance core must exist inside project root: {config_core!r}.", ".aimes/config.yaml")
            else:
                check("project_core_path", False, "governance.core must be a non-empty project-relative path.", ".aimes/config.yaml")
    else:
        check("project_governance_version", None, "No .aimes/config.yaml in this root; project/package compatibility was not applicable.")
        check("project_core_path", None, "No .aimes/config.yaml in this root; project core path was not applicable.")

    errors = sum(item["level"] == "ERROR" for item in findings)
    warnings = sum(item["level"] == "WARNING" for item in findings)
    return {
        "schema_version": 1,
        "validator": "aimes-release-compatibility",
        "root": str(root),
        "ok": errors == 0,
        "summary": {"errors": errors, "warnings": warnings, "checks": len(checks), "passed": sum(item["status"] == "PASS" for item in checks), "failed": sum(item["status"] == "FAIL" for item in checks), "unknown": sum(item["status"] == "UNKNOWN" for item in checks)},
        "versions": {"package": package_version, "runtime": runtime_version, "readme": readme_version, "governance_core": governance_version},
        "checks": checks,
        "findings": findings,
        "note": "Read-only compatibility check. It does not build or publish a release.",
    }
