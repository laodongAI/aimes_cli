from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Adapter:
    # Legacy fields remain stable for existing CLI and project-config consumers.
    key: str
    label: str
    status: str
    paths: tuple[str, ...]
    description: str
    detection_commands: tuple[str, ...] = ()
    # Host/Harness split and capability contract (registry schema V2).
    host_id: str = "unknown"
    host_type: str = "unknown"
    host_name: str = "Unknown host"
    harness_id: str = "unknown"
    harness_name: str = "Unknown harness"
    execution_modes: tuple[str, ...] = ("unknown",)
    capabilities: tuple[tuple[str, str], ...] = ()


REGISTRY_PATH = Path(__file__).parent / "data" / "adapter-registry.yaml"
VALID_CAPABILITY_STATES = {"native", "template", "manual", "unknown", "unsupported"}


def load_adapter_registry(path: Path = REGISTRY_PATH) -> tuple[dict[str, Adapter], dict[str, Any]]:
    """Load and structurally validate the packaged declarative adapter registry."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError(f"Cannot load AIMES adapter registry {path}: {exc}") from exc

    if not isinstance(raw, dict) or raw.get("schema_version") != 2:
        raise RuntimeError("AIMES adapter registry must be an object with schema_version: 2")
    items = raw.get("adapters")
    if not isinstance(items, list) or not items:
        raise RuntimeError("AIMES adapter registry must contain a non-empty adapters list")

    adapters: dict[str, Adapter] = {}
    for index, item in enumerate(items):
        loc = f"adapters[{index}]"
        if not isinstance(item, dict):
            raise RuntimeError(f"{loc} must be a mapping")
        adapter_id = item.get("id")
        if not isinstance(adapter_id, str) or not adapter_id.strip():
            raise RuntimeError(f"{loc}.id must be a non-empty string")
        if adapter_id in adapters:
            raise RuntimeError(f"Duplicate adapter id: {adapter_id}")
        host, harness = item.get("host"), item.get("harness")
        if not isinstance(host, dict) or not all(isinstance(host.get(k), str) and host[k].strip() for k in ("id", "type", "name")):
            raise RuntimeError(f"{loc}.host must define non-empty id, type and name")
        if not isinstance(harness, dict) or not all(isinstance(harness.get(k), str) and harness[k].strip() for k in ("id", "name")):
            raise RuntimeError(f"{loc}.harness must define non-empty id and name")
        modes = item.get("execution_modes")
        paths = item.get("entry_paths")
        capabilities = item.get("capabilities")
        if not isinstance(modes, list) or not modes or any(not isinstance(x, str) or not x for x in modes):
            raise RuntimeError(f"{loc}.execution_modes must be a non-empty list of strings")
        if not isinstance(paths, list) or not paths or any(not isinstance(x, str) or not x for x in paths):
            raise RuntimeError(f"{loc}.entry_paths must be a non-empty list of strings")
        if not isinstance(capabilities, dict) or any(not isinstance(k, str) or not isinstance(v, str) or v not in VALID_CAPABILITY_STATES for k, v in capabilities.items()):
            raise RuntimeError(f"{loc}.capabilities contains an invalid capability state")
        status = item.get("status")
        if status not in {"template", "manual"}:
            raise RuntimeError(f"{loc}.status must be template or manual")
        label = item.get("name")
        description = item.get("description")
        if not isinstance(label, str) or not label.strip() or not isinstance(description, str):
            raise RuntimeError(f"{loc}.name and description are required")
        commands = item.get("detection_commands", [])
        if not isinstance(commands, list) or any(not isinstance(x, str) or not x for x in commands):
            raise RuntimeError(f"{loc}.detection_commands must be a list of strings")

        adapters[adapter_id] = Adapter(
            key=adapter_id,
            label=label,
            status=status,
            paths=tuple(paths),
            description=description,
            detection_commands=tuple(commands),
            host_id=host["id"],
            host_type=host["type"],
            host_name=host["name"],
            harness_id=harness["id"],
            harness_name=harness["name"],
            execution_modes=tuple(modes),
            capabilities=tuple(sorted(capabilities.items())),
        )
    return adapters, raw


ADAPTERS, ADAPTER_REGISTRY = load_adapter_registry()

ALIASES = {
    "trae": "trae-code", "traecode": "trae-code", "trae-code": "trae-code",
    "vscode-codex": "vscode-codex", "vscode-claude": "vscode-claude-code", "vscode-claude-code": "vscode-claude-code",
    "copilot": "vscode-copilot", "vscode-copilot": "vscode-copilot",
    "zcode": "zcode", "qcode": "qcode", "claude": "claude-code", "claude-code": "claude-code",
    "codex": "codex-cli", "codex-cli": "codex-cli", "chatgpt": "chatgpt-work", "chatgpt-work": "chatgpt-work", "work": "chatgpt-work",
}


def normalize_tools(raw: str | list[str] | None) -> list[str]:
    if not raw:
        return []
    values = raw.split(",") if isinstance(raw, str) else raw
    out = []
    for item in values:
        key = ALIASES.get(item.strip().lower())
        if not key:
            raise ValueError(f"Unknown tool '{item}'. Supported: {', '.join(ADAPTERS)}")
        if key not in out:
            out.append(key)
    return out


def adapter_payload() -> list[dict[str, Any]]:
    """Return stable, JSON-serializable adapter metadata for CLI and integrations."""
    payload = []
    for adapter in ADAPTERS.values():
        payload.append({
            "id": adapter.key,
            "name": adapter.label,
            "status": adapter.status,
            "entry_paths": list(adapter.paths),
            "description": adapter.description,
            "host": {"id": adapter.host_id, "type": adapter.host_type, "name": adapter.host_name},
            "harness": {"id": adapter.harness_id, "name": adapter.harness_name},
            "execution_modes": list(adapter.execution_modes),
            "capabilities": dict(adapter.capabilities),
            "detection_commands": list(adapter.detection_commands),
        })
    return payload
