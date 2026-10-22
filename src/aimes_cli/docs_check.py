from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CORE = "docs/_governance/AIMES-CORE-V1.2.md"
DEFAULT_ENTRY_PATHS = (
    "AGENTS.md",
    "CLAUDE.md",
    ".github/copilot-instructions.md",
    ".trae/rules/00-aimes-governance.md",
)
SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", "dist", "build", ".mypy_cache",
}
LINK_RE = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")
FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,}).*$", re.MULTILINE)


def _finding(findings: list[dict[str, Any]], level: str, code: str, message: str, path: str | None = None, line: int | None = None) -> None:
    item: dict[str, Any] = {"level": level, "code": code, "message": message}
    if path:
        item["path"] = path
    if line is not None:
        item["line"] = line
    findings.append(item)


def _markdown_without_fences(content: str) -> str:
    lines = content.splitlines()
    output: list[str] = []
    fence_char: str | None = None
    fence_len = 0
    for line in lines:
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if match:
            token = match.group(1)
            if fence_char is None:
                fence_char, fence_len = token[0], len(token)
            elif token[0] == fence_char and len(token) >= fence_len:
                fence_char, fence_len = None, 0
            output.append("")
        elif fence_char is not None:
            output.append("")
        else:
            output.append(line)
    return "\n".join(output)


def _load_project_config(root: Path, findings: list[dict[str, Any]]) -> tuple[str, list[str]]:
    config_path = root / ".aimes" / "config.yaml"
    if not config_path.is_file():
        return DEFAULT_CORE, [p for p in DEFAULT_ENTRY_PATHS if (root / p).is_file()]
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8-sig")) or {}
    except (OSError, yaml.YAMLError) as exc:
        _finding(findings, "ERROR", "CONFIG_READ", f"Cannot read .aimes/config.yaml: {exc}", ".aimes/config.yaml")
        return DEFAULT_CORE, [p for p in DEFAULT_ENTRY_PATHS if (root / p).is_file()]
    if not isinstance(data, dict):
        _finding(findings, "ERROR", "CONFIG_TYPE", ".aimes/config.yaml must contain a YAML mapping", ".aimes/config.yaml")
        return DEFAULT_CORE, [p for p in DEFAULT_ENTRY_PATHS if (root / p).is_file()]
    governance = data.get("governance", {})
    core = governance.get("core", DEFAULT_CORE) if isinstance(governance, dict) else DEFAULT_CORE
    if not isinstance(core, str) or not core.strip():
        _finding(findings, "ERROR", "CORE_PATH", "governance.core must be a non-empty project-relative path", ".aimes/config.yaml")
        core = DEFAULT_CORE
    tools = data.get("tools", [])
    entry_paths: list[str] = []
    if not isinstance(tools, list):
        _finding(findings, "ERROR", "TOOLS_TYPE", "tools must be a list in .aimes/config.yaml", ".aimes/config.yaml")
    else:
        for index, tool in enumerate(tools):
            if not isinstance(tool, dict):
                _finding(findings, "ERROR", "TOOL_ENTRY_TYPE", f"tools[{index}] must be a mapping", ".aimes/config.yaml")
                continue
            paths = tool.get("entry_paths", [])
            if not isinstance(paths, list):
                _finding(findings, "ERROR", "ENTRY_PATHS_TYPE", f"tools[{index}].entry_paths must be a list", ".aimes/config.yaml")
                continue
            for path in paths:
                if not isinstance(path, str) or not path.strip():
                    _finding(findings, "ERROR", "ENTRY_PATH_VALUE", f"tools[{index}] has an invalid entry path", ".aimes/config.yaml")
                    continue
                if path not in entry_paths:
                    entry_paths.append(path)
    return core, entry_paths




def _check_project_records_and_env(root: Path, findings: list[dict[str, Any]]) -> None:
    """Check configured task/handoff paths and duplicate keys in the root env example."""
    config_path = root / ".aimes" / "config.yaml"
    if config_path.is_file():
        try:
            config = yaml.safe_load(config_path.read_text(encoding="utf-8-sig")) or {}
        except (OSError, yaml.YAMLError):
            config = {}
        if isinstance(config, dict):
            records = config.get("records", {})
            if isinstance(records, dict):
                for key in ("tasks", "handoff"):
                    value = records.get(key)
                    if value is None or (isinstance(value, str) and not value.strip()):
                        continue
                    if not isinstance(value, str):
                        _finding(findings, "ERROR", "RECORD_PATH_INVALID", f"records.{key} must be a project-relative path", ".aimes/config.yaml")
                        continue
                    normalized = value.strip().replace("\\", "/")
                    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized) or ".." in normalized.split("/"):
                        _finding(findings, "ERROR", "RECORD_PATH_ESCAPE", f"records.{key} must stay inside the project root", ".aimes/config.yaml")
                        continue
                    candidate = (root / normalized).resolve()
                    try:
                        candidate.relative_to(root)
                    except ValueError:
                        _finding(findings, "ERROR", "RECORD_PATH_ESCAPE", f"records.{key} escapes the project root", ".aimes/config.yaml")
                        continue
                    if not candidate.is_file():
                        _finding(findings, "ERROR", "RECORD_PATH_MISSING", f"Configured records.{key} file does not exist: {normalized}", normalized)

    env_example = root / ".env.example"
    if not env_example.is_file():
        return
    try:
        lines = env_example.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        _finding(findings, "WARNING", "ENV_EXAMPLE_READ", f"Cannot read .env.example: {exc}", ".env.example")
        return
    seen: dict[str, int] = {}
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^(?:export\\s+)?([A-Za-z_][A-Za-z0-9_]*)\\s*=", stripped)
        if not match:
            continue
        key = match.group(1)
        if key in seen:
            _finding(findings, "WARNING", "ENV_KEY_DUPLICATE", f"Environment variable {key} is assigned more than once (first at line {seen[key]})", ".env.example", line_no)
        else:
            seen[key] = line_no


def check_docs(root: Path, *, max_entry_lines: int = 40) -> dict[str, Any]:
    """Read-only documentation and thin-entry check. It never modifies project files."""
    root = root.resolve()
    findings: list[dict[str, Any]] = []
    if not root.is_dir():
        _finding(findings, "ERROR", "ROOT_NOT_DIRECTORY", f"Project root is not a directory: {root}")
        return _result(root, findings, 0, 0, 0)

    core_rel, entry_paths = _load_project_config(root, findings)
    _check_project_records_and_env(root, findings)
    core_path = (root / core_rel).resolve()
    try:
        core_path.relative_to(root)
    except ValueError:
        _finding(findings, "ERROR", "CORE_PATH_ESCAPE", "Governance core path escapes project root", ".aimes/config.yaml")
        core_path = root / DEFAULT_CORE
    # A generic Markdown repository need not install AIMES governance.
    # Once a config or any registered/native entry exists, the configured core is required.
    governance_installed = (root / ".aimes" / "config.yaml").is_file() or bool(entry_paths)
    if governance_installed and not core_path.is_file():
        _finding(findings, "ERROR", "CORE_MISSING", f"Governance core not found: {core_rel}", core_rel)

    checked_entries = 0
    for rel in entry_paths:
        path = (root / rel).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            _finding(findings, "ERROR", "ENTRY_PATH_ESCAPE", f"Entry path escapes project root: {rel}", rel)
            continue
        if not path.is_file():
            _finding(findings, "ERROR", "ENTRY_MISSING", f"Configured tool entry does not exist: {rel}", rel)
            continue
        checked_entries += 1
        # Only native thin rule-entry files are subject to the line/reference policy.
        # Manual-adapter READMEs are registered entry artifacts, but are not rule files.
        if rel not in DEFAULT_ENTRY_PATHS:
            continue
        try:
            content = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            _finding(findings, "ERROR", "ENTRY_READ", f"Cannot read entry file: {exc}", rel)
            continue
        lines = content.splitlines()
        if len(lines) > max_entry_lines:
            _finding(findings, "ERROR", "ENTRY_TOO_LONG", f"Thin entry has {len(lines)} lines; limit is {max_entry_lines}", rel)
        normalized = content.replace("\\", "/")
        core_name = Path(core_rel).as_posix()
        if core_name not in normalized and core_path.name not in normalized:
            _finding(findings, "ERROR", "CORE_REFERENCE_MISSING", f"Thin entry does not reference governance core {core_rel}", rel)
        if not core_path.is_file():
            continue
        # Validate explicit local Markdown links in the entry itself as part of the all-doc scan below.

    checked_docs = 0
    checked_links = 0
    for md_path in root.rglob("*.md"):
        try:
            rel_path = md_path.relative_to(root)
        except ValueError:
            continue
        if any(part in SKIP_DIRS for part in rel_path.parts):
            continue
        # The packaged governance core contains project-relative links; its intended
        # root is the consuming project, not this source-template directory.
        if "templates" in rel_path.parts and "aimes_cli" in rel_path.parts:
            continue
        checked_docs += 1
        try:
            content = md_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            _finding(findings, "WARNING", "DOC_READ", f"Cannot read Markdown file: {exc}", rel_path.as_posix())
            continue
        visible = _markdown_without_fences(content)
        for match in LINK_RE.finditer(visible):
            raw_target = match.group(1).strip()
            if not raw_target or raw_target.startswith("<"):
                raw_target = raw_target.strip("<>")
            target = raw_target.split()[0].strip("<>") if raw_target else ""
            if not target or target.startswith(("https://", "http://", "mailto:", "tel:", "data:")) or target.startswith("#"):
                continue
            target_path = target.split("#", 1)[0].split("?", 1)[0]
            if not target_path:
                continue
            checked_links += 1
            candidate = (md_path.parent / target_path).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                _finding(findings, "ERROR", "LINK_PATH_ESCAPE", f"Local link escapes project root: {target}", rel_path.as_posix(), content[:match.start()].count("\n") + 1)
                continue
            if not candidate.exists():
                _finding(findings, "ERROR", "BROKEN_LINK", f"Local Markdown link target does not exist: {target}", rel_path.as_posix(), content[:match.start()].count("\n") + 1)

    return _result(root, findings, checked_docs, checked_links, checked_entries)


def _result(root: Path, findings: list[dict[str, Any]], checked_docs: int, checked_links: int, checked_entries: int) -> dict[str, Any]:
    errors = sum(item["level"] == "ERROR" for item in findings)
    warnings = sum(item["level"] == "WARNING" for item in findings)
    return {
        "schema_version": 1,
        "validator": "aimes-docs-check",
        "root": str(root),
        "ok": errors == 0,
        "summary": {
            "errors": errors,
            "warnings": warnings,
            "findings": len(findings),
            "markdown_files_checked": checked_docs,
            "local_links_checked": checked_links,
            "entry_files_checked": checked_entries,
        },
        "findings": findings,
    }
