from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .adapters import ADAPTER_REGISTRY, normalize_tools

MAX_CONFIG_BYTES = 1024 * 1024
DETECTOR_VERSION = "1.0"


def _safe_file(root: Path, relative: str) -> tuple[Path | None, str | None]:
    """Resolve a project-relative file without following symlinks outside the project."""
    candidate = root / relative
    try:
        if candidate.is_symlink():
            return None, "symlink_not_followed"
        resolved = candidate.resolve(strict=False)
        if not resolved.is_relative_to(root):
            return None, "path_outside_project"
        if not candidate.exists():
            return None, None
        if not candidate.is_file():
            return None, "not_a_regular_file"
        if candidate.stat().st_size > MAX_CONFIG_BYTES:
            return None, "file_too_large"
        return candidate, None
    except OSError:
        return None, "unreadable"


def _file_evidence(root: Path, relative: str, parser: str = "none") -> dict[str, Any]:
    path, issue = _safe_file(root, relative)
    if issue:
        return {"path": relative, "status": "unknown", "reason": issue}
    if path is None:
        return {"path": relative, "status": "not_present"}
    try:
        raw = path.read_bytes()
    except OSError:
        return {"path": relative, "status": "unknown", "reason": "unreadable"}
    evidence = {
        "path": relative,
        "status": "present",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }
    if parser == "json":
        try:
            parsed = json.loads(raw.decode("utf-8-sig"))
            if not isinstance(parsed, dict):
                raise ValueError("top_level_must_be_object")
            evidence["status"] = "valid"
            evidence["_parsed"] = parsed
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            evidence["status"] = "invalid"
            evidence["reason"] = str(exc)[:240]
    elif parser == "toml":
        try:
            try:
                import tomllib
            except ImportError:
                try:
                    import tomli as tomllib  # type: ignore[no-redef]
                except ImportError:
                    evidence["status"] = "unknown"
                    evidence["reason"] = "toml_parser_unavailable_requires_python_3_11_or_tomli"
                else:
                    parsed = tomllib.loads(raw.decode("utf-8"))
                    evidence["status"] = "valid"
                    evidence["_parsed"] = parsed
            else:
                parsed = tomllib.loads(raw.decode("utf-8"))
                evidence["status"] = "valid"
                evidence["_parsed"] = parsed
        except (UnicodeDecodeError, ValueError) as exc:
            evidence["status"] = "invalid"
            evidence["reason"] = str(exc)[:240]
    return evidence


def _directory_evidence(root: Path, relative: str, required_name: str | None = None) -> dict[str, Any]:
    directory = root / relative
    try:
        if directory.is_symlink():
            return {"path": relative, "status": "unknown", "reason": "symlink_not_followed", "items": []}
        resolved = directory.resolve(strict=False)
        if not resolved.is_relative_to(root):
            return {"path": relative, "status": "unknown", "reason": "path_outside_project", "items": []}
        if not directory.exists():
            return {"path": relative, "status": "not_present", "items": []}
        if not directory.is_dir():
            return {"path": relative, "status": "invalid", "reason": "not_a_directory", "items": []}
        items = []
        children = sorted(directory.iterdir(), key=lambda item: item.name.casefold())
        if required_name == "*.md":
            candidates = [item for item in children if item.is_file() and item.suffix.lower() == ".md"]
            candidates.extend(
                manifest
                for child in children if child.is_dir() and not child.is_symlink()
                for manifest in sorted(child.glob("*.md"))
            )
            for manifest in candidates:
                if manifest.is_symlink() or not manifest.is_file():
                    continue
                try:
                    raw = manifest.read_bytes()
                    if len(raw) > MAX_CONFIG_BYTES:
                        continue
                    items.append({
                        "name": manifest.stem,
                        "manifest": manifest.relative_to(root).as_posix(),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    })
                except OSError:
                    continue
        else:
            for child in children:
                if child.is_symlink() or not child.is_dir():
                    continue
                manifest = child / (required_name or "SKILL.md")
                if manifest.is_symlink() or not manifest.is_file():
                    continue
                try:
                    raw = manifest.read_bytes()
                    if len(raw) > MAX_CONFIG_BYTES:
                        continue
                    items.append({
                        "name": child.name,
                        "manifest": manifest.relative_to(root).as_posix(),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    })
                except OSError:
                    continue
        return {"path": relative, "status": "present", "items": items, "count": len(items)}
    except OSError:
        return {"path": relative, "status": "unknown", "reason": "unreadable", "items": []}


def _integration(name: str, evidence: list[dict[str, Any]], configured: bool, note: str) -> dict[str, Any]:
    clean = []
    for item in evidence:
        clean.append({key: value for key, value in item.items() if key != "_parsed"})
    states = {item.get("status") for item in evidence}
    if "invalid" in states:
        status = "invalid"
    elif "unknown" in states:
        status = "unknown"
    elif configured:
        status = "configured"
    elif "present" in states or "valid" in states:
        status = "present"
    else:
        status = "not_present"
    return {"id": name, "status": status, "evidence": clean, "note": note}


def _inspect_codex(root: Path) -> list[dict[str, Any]]:
    instructions = _file_evidence(root, "AGENTS.md")
    skills = _directory_evidence(root, ".agents/skills")
    config = _file_evidence(root, ".codex/config.toml", "toml")
    hooks_file = _file_evidence(root, ".codex/hooks.json", "json")
    config_data = config.get("_parsed", {})
    hooks_configured = isinstance(config_data, dict) and bool(config_data.get("hooks"))
    hooks_json = hooks_file.get("_parsed", {})
    hooks_configured = hooks_configured or (isinstance(hooks_json, dict) and bool(hooks_json))
    mcp_configured = isinstance(config_data, dict) and bool(config_data.get("mcp_servers"))
    agents_configured = isinstance(config_data, dict) and bool(config_data.get("agents"))
    return [
        _integration("instructions", [instructions], False, "AGENTS.md 的存在不证明当前 Codex 会话已加载。"),
        _integration("skills", [skills], skills.get("count", 0) > 0, "检查项目级 .agents/skills/*/SKILL.md；不验证技能触发或执行。"),
        _integration("mcp", [config], mcp_configured, "仅识别项目级 config.toml 中的 mcp_servers；不读取或展示服务器参数。"),
        _integration("hooks", [config, hooks_file], hooks_configured, "只识别 hooks 配置结构；绝不执行 Hook。"),
        _integration("agents", [config], agents_configured, "仅识别 config.toml 的 agents 表；不启动子 Agent。"),
    ]


def _inspect_claude(root: Path) -> list[dict[str, Any]]:
    instructions = _file_evidence(root, "CLAUDE.md")
    settings = _file_evidence(root, ".claude/settings.json", "json")
    mcp = _file_evidence(root, ".mcp.json", "json")
    skills = _directory_evidence(root, ".claude/skills")
    agents_dir = _directory_evidence(root, ".claude/agents", required_name="*.md")
    settings_data = settings.get("_parsed", {})
    mcp_data = mcp.get("_parsed", {})
    hooks_configured = isinstance(settings_data, dict) and bool(settings_data.get("hooks"))
    mcp_configured = isinstance(mcp_data, dict) and bool(mcp_data.get("mcpServers"))
    return [
        _integration("instructions", [instructions], False, "CLAUDE.md 的存在不证明当前 Claude Code 会话已加载。"),
        _integration("skills", [skills], skills.get("count", 0) > 0, "检查项目级 .claude/skills/*/SKILL.md；不验证技能触发或执行。"),
        _integration("mcp", [mcp, settings], mcp_configured, "检查 .mcp.json 与 settings.json 的 MCP 配置结构；不读取或展示服务器参数。"),
        _integration("hooks", [settings], hooks_configured, "只识别 settings.json 的 hooks 配置；绝不执行 Hook。"),
        _integration("agents", [agents_dir], agents_dir.get("count", 0) > 0, "检查项目级 .claude/agents/*/AGENT.md；不启动子 Agent。"),
    ]


def inspect_adapters(root: Path, tools: Iterable[str] | None = None) -> dict[str, Any]:
    """Inspect project-level Codex/Claude integration files without executing tools."""
    root = Path(root).resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Project root is not a directory: {root}")
    selected = normalize_tools(list(tools)) if tools is not None else ["codex-cli", "claude-code"]
    unsupported = [tool for tool in selected if tool not in {"codex-cli", "claude-code"}]
    if unsupported:
        raise ValueError("adapter inspect currently supports codex-cli and claude-code only: " + ", ".join(unsupported))

    records = []
    for tool in selected:
        integrations = _inspect_codex(root) if tool == "codex-cli" else _inspect_claude(root)
        records.append({
            "id": tool,
            "integrations": integrations,
            "summary": {
                state: sum(item["status"] == state for item in integrations)
                for state in ("configured", "present", "not_present", "invalid", "unknown")
            },
        })
    return {
        "schema_version": 1,
        "ok": True,
        "detector": "aimes-project-adapter-inspect",
        "detector_version": DETECTOR_VERSION,
        "registry_version": ADAPTER_REGISTRY.get("registry_version"),
        "project_root": str(root),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "scope": "read-only project files only; configuration values and credentials are not emitted or persisted; no user-level config, command execution, hook execution, agent launch, or runtime loading verification",
        "status_semantics": {
            "configured": "A recognized non-empty integration configuration was found; not proof of runtime activation.",
            "present": "An entry file or directory exists, but configuration could not be confirmed.",
            "not_present": "No recognized project-level entry was found.",
            "invalid": "A recognized structured configuration file failed parsing.",
            "unknown": "The file could not be safely inspected or the required parser was unavailable.",
        },
        "adapters": records,
    }
